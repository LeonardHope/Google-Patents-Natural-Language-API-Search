"""
Research Search - Query google_patents_research.publications on BigQuery.

This table contains Google's AI-generated analysis:
- Similar documents (document similarity scores)
- Machine translations of titles/abstracts
- Extracted top terms

Use for: finding similar patents, translated patent data.
"""

import sys
import json
import argparse
from google.cloud.bigquery import ScalarQueryParameter
from bigquery_client import get_client, BigQueryError, PUBLIC_PROJECT

RESEARCH = f"`{PUBLIC_PROJECT}.google_patents_research.publications`"


def find_similar_patents(publication_number: str, limit: int = 20,
                         force: bool = False) -> list:
    """Find patents similar to a given patent using Google's similarity data.

    Args:
        publication_number: Patent to find similar docs for (e.g., 'US-10000000-B2').
        limit: Max results (default 20).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with similar publication numbers and similarity info.
    """
    limit = min(limit, 50)
    pn = publication_number.strip()
    params = [ScalarQueryParameter("pub_number", "STRING", pn)]

    sql = f"""
    SELECT
      publication_number,
      top_terms,
      url
    FROM {RESEARCH}
    WHERE publication_number = @pub_number
    LIMIT 1
    """
    client = get_client()
    results = client.run_query(sql, query_params=params, force=force)

    if not results:
        return []

    # The research table has similar_documents as an array
    # Try to get similar documents
    params2 = [
        ScalarQueryParameter("pub_number", "STRING", pn),
        ScalarQueryParameter("limit", "INT64", limit),
    ]
    sql2 = f"""
    SELECT
      sd.publication_number AS similar_publication_number,
      sd.application_number AS similar_application_number
    FROM {RESEARCH},
      UNNEST(similar_documents) AS sd
    WHERE publication_number = @pub_number
    LIMIT {limit}
    """
    try:
        similar = client.run_query(sql2, query_params=params2, force=force)
        return similar
    except BigQueryError:
        # similar_documents field may not exist in all versions
        return results


def search_by_top_terms(term: str, limit: int = 20,
                        force: bool = False) -> list:
    """Search patents by Google's extracted top terms.

    Args:
        term: Term to search for in top_terms field (case-insensitive).
        limit: Max results (default 20).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with publication_number, top_terms.
    """
    limit = min(limit, 50)
    params = [ScalarQueryParameter("term", "STRING", f"%{term}%")]

    sql = f"""
    SELECT
      publication_number,
      top_terms,
      url
    FROM {RESEARCH}
    WHERE EXISTS (
      SELECT 1 FROM UNNEST(top_terms) AS t
      WHERE LOWER(t.text) LIKE LOWER(@term)
    )
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search google_patents_research on BigQuery")
    parser.add_argument("--force", action="store_true",
                        help="Bypass cost threshold (use after reviewing estimate)")
    sub = parser.add_subparsers(dest="command")

    p_similar = sub.add_parser("similar", help="Find similar patents")
    p_similar.add_argument("publication_number")
    p_similar.add_argument("--limit", "-n", type=int, default=20)

    p_terms = sub.add_parser("terms", help="Search by top terms")
    p_terms.add_argument("term")
    p_terms.add_argument("--limit", "-n", type=int, default=20)

    args = parser.parse_args()

    if args.command == "similar":
        results = find_similar_patents(args.publication_number, limit=args.limit,
                                        force=args.force)
    elif args.command == "terms":
        results = search_by_top_terms(args.term, limit=args.limit, force=args.force)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(results, indent=2, default=str))
