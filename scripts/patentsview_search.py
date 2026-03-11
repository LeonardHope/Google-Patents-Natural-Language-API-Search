"""
PatentsView BigQuery Search - Query patentsview.* tables on BigQuery.

These tables are cheaper and more granular than patents.publications.
Use for: individual claims search, assignee lookups, inventor lookups, CPC searches.

Actual BigQuery schemas (differ from PatentsView REST API):
    patentsview.claim            — patent_id, text, sequence, dependent
    patentsview.patent           — id, number, title, date, abstract, type, num_claims
    patentsview.assignee         — id, organization
    patentsview.patent_assignee  — patent_id, assignee_id (junction)
    patentsview.inventor         — id, name_first, name_last
    patentsview.patent_inventor  — patent_id, inventor_id (junction)
    patentsview.cpc_current      — patent_id, group_id, subsection_id, subgroup_id, section_id
"""

import sys
import json
import argparse
from google.cloud.bigquery import ScalarQueryParameter
from bigquery_client import get_client, BigQueryError, PUBLIC_PROJECT

PV = f"`{PUBLIC_PROJECT}.patentsview"


def search_claims(keyword: str, keyword2: str = None, limit: int = 20,
                  patent_id: str = None, force: bool = False) -> list:
    """Search individual patent claims for keywords.

    This is the cheapest way to search claim text — uses the patentsview.claim
    table instead of the full publications table.

    Args:
        keyword: Primary search term (case-insensitive LIKE match).
        keyword2: Optional second keyword (AND logic).
        limit: Max results (default 20, max 100).
        patent_id: Optional patent ID to search within.
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with patent_id, sequence, text.
    """
    limit = min(limit, 100)
    conditions = ["LOWER(text) LIKE LOWER(@keyword)"]
    params = [ScalarQueryParameter("keyword", "STRING", f"%{keyword}%")]

    if keyword2:
        conditions.append("LOWER(text) LIKE LOWER(@keyword2)")
        params.append(ScalarQueryParameter("keyword2", "STRING", f"%{keyword2}%"))
    if patent_id:
        conditions.append("patent_id = @patent_id")
        params.append(ScalarQueryParameter("patent_id", "STRING", patent_id))

    where = " AND ".join(conditions)
    sql = f"""
    SELECT patent_id, sequence, text
    FROM {PV}.claim`
    WHERE {where}
    ORDER BY patent_id DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_by_assignee(assignee_name: str, limit: int = 25,
                       force: bool = False) -> list:
    """Find patents by assignee/company name.

    Uses patent_assignee junction table to join assignee with patent.

    Args:
        assignee_name: Company name (case-insensitive partial match).
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with patent_id, organization, title, date.
    """
    limit = min(limit, 100)
    params = [ScalarQueryParameter("assignee_name", "STRING", f"%{assignee_name.upper()}%")]
    sql = f"""
    SELECT
      pa.patent_id,
      a.organization,
      p.title,
      p.date
    FROM {PV}.patent_assignee` pa
    JOIN {PV}.assignee` a ON pa.assignee_id = a.id
    JOIN {PV}.patent` p ON pa.patent_id = p.id
    WHERE UPPER(a.organization) LIKE @assignee_name
    ORDER BY p.date DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_by_inventor(last_name: str, first_name: str = None, limit: int = 25,
                       force: bool = False) -> list:
    """Find patents by inventor name.

    Uses patent_inventor junction table to join inventor with patent.

    Args:
        last_name: Inventor last name (case-insensitive).
        first_name: Optional first name for narrower search.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with patent_id, inventor names, title, date.
    """
    limit = min(limit, 100)
    conditions = ["UPPER(i.name_last) = @last_name"]
    params = [ScalarQueryParameter("last_name", "STRING", last_name.upper())]

    if first_name:
        conditions.append("UPPER(i.name_first) = @first_name")
        params.append(ScalarQueryParameter("first_name", "STRING", first_name.upper()))

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
      pi.patent_id,
      i.name_first,
      i.name_last,
      p.title,
      p.date
    FROM {PV}.patent_inventor` pi
    JOIN {PV}.inventor` i ON pi.inventor_id = i.id
    JOIN {PV}.patent` p ON pi.patent_id = p.id
    WHERE {where}
    ORDER BY p.date DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_by_cpc(cpc_code: str, limit: int = 25, force: bool = False) -> list:
    """Find patents by CPC classification code.

    Args:
        cpc_code: CPC code prefix (e.g., 'H04L' or 'G06N3/08'). Matches with LIKE prefix%.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with patent_id, cpc codes, title, date.
    """
    limit = min(limit, 100)
    cpc_clean = cpc_code.upper().strip()
    params = [ScalarQueryParameter("cpc_prefix", "STRING", f"{cpc_clean}%")]
    sql = f"""
    SELECT
      c.patent_id,
      c.group_id,
      c.subgroup_id,
      p.title,
      p.date
    FROM {PV}.cpc_current` c
    JOIN {PV}.patent` p ON c.patent_id = p.id
    WHERE c.group_id LIKE @cpc_prefix
       OR c.subgroup_id LIKE @cpc_prefix
    ORDER BY p.date DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def get_patent(patent_id: str, force: bool = False) -> list:
    """Look up a specific patent by ID.

    Args:
        patent_id: Patent number (e.g., '10000000'). Cleaned automatically.
        force: If True, bypass cost threshold after user approval.

    Returns:
        List with single patent dict (or empty).
    """
    clean = patent_id.replace(",", "").replace("US", "").replace(" ", "").strip()
    params = [ScalarQueryParameter("patent_id", "STRING", clean)]
    sql = f"""
    SELECT
      p.id AS patent_id,
      p.number,
      p.title,
      p.date,
      p.abstract,
      p.type,
      p.num_claims
    FROM {PV}.patent` p
    WHERE p.id = @patent_id
    LIMIT 1
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search patentsview tables on BigQuery")
    parser.add_argument("--force", action="store_true",
                        help="Bypass cost threshold (use after reviewing estimate)")
    sub = parser.add_subparsers(dest="command")

    p_claims = sub.add_parser("claims", help="Search claim text")
    p_claims.add_argument("keyword")
    p_claims.add_argument("--keyword2", "-k2")
    p_claims.add_argument("--limit", "-n", type=int, default=20)

    p_assignee = sub.add_parser("assignee", help="Search by assignee")
    p_assignee.add_argument("name")
    p_assignee.add_argument("--limit", "-n", type=int, default=25)

    p_inventor = sub.add_parser("inventor", help="Search by inventor")
    p_inventor.add_argument("last_name")
    p_inventor.add_argument("--first", "-f")
    p_inventor.add_argument("--limit", "-n", type=int, default=25)

    p_cpc = sub.add_parser("cpc", help="Search by CPC code")
    p_cpc.add_argument("code")
    p_cpc.add_argument("--limit", "-n", type=int, default=25)

    p_patent = sub.add_parser("patent", help="Look up a patent")
    p_patent.add_argument("patent_id")

    args = parser.parse_args()

    if args.command == "claims":
        results = search_claims(args.keyword, keyword2=args.keyword2,
                                limit=args.limit, force=args.force)
    elif args.command == "assignee":
        results = search_by_assignee(args.name, limit=args.limit, force=args.force)
    elif args.command == "inventor":
        results = search_by_inventor(args.last_name, first_name=args.first,
                                     limit=args.limit, force=args.force)
    elif args.command == "cpc":
        results = search_by_cpc(args.code, limit=args.limit, force=args.force)
    elif args.command == "patent":
        results = get_patent(args.patent_id, force=args.force)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(results, indent=2, default=str))
