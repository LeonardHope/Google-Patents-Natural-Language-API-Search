"""
Publications Search - Query patents.publications (main table) on BigQuery.

This is the largest table (166M rows, 2.74 TB) and the only one with:
- Full-text claims and descriptions (US patents only)
- International patents (17+ countries)
- Harmonized assignee/inventor names
- Patent family data

COST WARNING: Every query against this table is carefully controlled.
All functions select only needed columns and include LIMIT.
The bigquery_client dry-run check catches expensive queries before execution.

Key patterns:
- Nested fields (claims_localized, title_localized, etc.) require UNNEST
- Dates are INTEGER in YYYYMMDD format (not SQL DATE)
- assignee_harmonized has .name and .country_code subfields
"""

import re
import sys
import json
import argparse
from google.cloud.bigquery import ScalarQueryParameter
from bigquery_client import get_client, BigQueryError, PUBLIC_PROJECT

PUB = f"`{PUBLIC_PROJECT}.patents.publications`"


def search_claims_fulltext(keyword: str, keyword2: str = None,
                           country_code: str = "US", grant_after: int = None,
                           limit: int = 20, force: bool = False) -> list:
    """Search full-text claims in the publications table.

    More expensive than patentsview.claim but supports international patents
    and can combine with other filters (assignee, date, CPC).

    Args:
        keyword: Primary search term for claims text (case-insensitive).
        keyword2: Optional second keyword (AND logic).
        country_code: Country filter (default 'US'). Use None for all countries.
        grant_after: Minimum grant date as YYYYMMDD integer (e.g., 20200101).
        limit: Max results (default 20, max 50).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with publication_number, title, filing_date, grant_date.
    """
    limit = min(limit, 50)

    claim_conditions = ["LOWER(claim.text) LIKE LOWER(@keyword)"]
    params = [ScalarQueryParameter("keyword", "STRING", f"%{keyword}%")]

    if keyword2:
        claim_conditions.append("LOWER(claim.text) LIKE LOWER(@keyword2)")
        params.append(ScalarQueryParameter("keyword2", "STRING", f"%{keyword2}%"))
    claim_where = " AND ".join(claim_conditions)

    outer_conditions = []
    if country_code:
        outer_conditions.append("country_code = @country_code")
        params.append(ScalarQueryParameter("country_code", "STRING", country_code.upper()))
    if grant_after:
        outer_conditions.append("grant_date > @grant_after")
        params.append(ScalarQueryParameter("grant_after", "INT64", grant_after))

    outer_where = (" AND " + " AND ".join(outer_conditions)) if outer_conditions else ""

    sql = f"""
    SELECT
      publication_number,
      ANY_VALUE(title.text) AS title,
      ANY_VALUE(filing_date) AS filing_date,
      ANY_VALUE(grant_date) AS grant_date
    FROM
      {PUB},
      UNNEST(title_localized) AS title
    WHERE
      EXISTS (
        SELECT 1 FROM UNNEST(claims_localized) AS claim
        WHERE {claim_where}
      )
      AND title.language = 'en'
      {outer_where}
    GROUP BY publication_number
    ORDER BY ANY_VALUE(grant_date) DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_description(keyword: str, keyword2: str = None,
                       country_code: str = "US", limit: int = 20,
                       force: bool = False) -> list:
    """Search patent descriptions/specifications.

    Args:
        keyword: Primary search term for description text (case-insensitive).
        keyword2: Optional second keyword (AND logic).
        country_code: Country filter (default 'US').
        limit: Max results (default 20, max 50).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with publication_number, title, filing_date.
    """
    limit = min(limit, 50)

    desc_conditions = ["LOWER(d.text) LIKE LOWER(@keyword)"]
    params = [ScalarQueryParameter("keyword", "STRING", f"%{keyword}%")]

    if keyword2:
        desc_conditions.append("LOWER(d.text) LIKE LOWER(@keyword2)")
        params.append(ScalarQueryParameter("keyword2", "STRING", f"%{keyword2}%"))
    desc_where = " AND ".join(desc_conditions)

    country_filter = ""
    if country_code:
        country_filter = "AND country_code = @country_code"
        params.append(ScalarQueryParameter("country_code", "STRING", country_code.upper()))

    sql = f"""
    SELECT
      publication_number,
      ANY_VALUE(title.text) AS title,
      ANY_VALUE(filing_date) AS filing_date
    FROM
      {PUB},
      UNNEST(title_localized) AS title
    WHERE
      EXISTS (
        SELECT 1 FROM UNNEST(description_localized) AS d
        WHERE {desc_where}
      )
      AND title.language = 'en'
      {country_filter}
    GROUP BY publication_number
    ORDER BY ANY_VALUE(filing_date) DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_by_assignee(assignee_name: str, country_code: str = None,
                       limit: int = 25, force: bool = False) -> list:
    """Search patents by assignee name using the publications table.

    Better than patentsview for international patents since it includes
    harmonized names across jurisdictions.

    Args:
        assignee_name: Company name (case-insensitive partial match).
        country_code: Optional country filter.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with publication_number, assignee, title, dates.
    """
    limit = min(limit, 100)
    params = [ScalarQueryParameter("assignee_name", "STRING", f"%{assignee_name.upper()}%")]

    country_filter = ""
    if country_code:
        country_filter = "AND p.country_code = @country_code"
        params.append(ScalarQueryParameter("country_code", "STRING", country_code.upper()))

    sql = f"""
    SELECT
      p.publication_number,
      p.country_code,
      ANY_VALUE(a.name) AS assignee_name,
      ANY_VALUE(title.text) AS title,
      ANY_VALUE(p.filing_date) AS filing_date,
      ANY_VALUE(p.grant_date) AS grant_date
    FROM
      {PUB} p,
      UNNEST(p.assignee_harmonized) AS a,
      UNNEST(p.title_localized) AS title
    WHERE
      UPPER(a.name) LIKE @assignee_name
      AND title.language = 'en'
      {country_filter}
    GROUP BY p.publication_number, p.country_code
    ORDER BY ANY_VALUE(p.grant_date) DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_by_keyword(keyword: str, keyword2: str = None,
                      country_code: str = None, grant_after: int = None,
                      limit: int = 25, force: bool = False) -> list:
    """Search patents by keyword in title and abstract.

    Cheaper than full-text claims search since title/abstract are smaller fields.

    Args:
        keyword: Search term for title/abstract (case-insensitive).
        keyword2: Optional second keyword (AND logic).
        country_code: Optional country filter.
        grant_after: Minimum grant date as YYYYMMDD.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with publication_number, title, abstract snippet, dates.
    """
    limit = min(limit, 100)
    params = [ScalarQueryParameter("keyword", "STRING", f"%{keyword}%")]

    # Use EXISTS for abstract matching to avoid cross-join with title
    keyword2_abstract_clause = ""
    if keyword2:
        params.append(ScalarQueryParameter("keyword2", "STRING", f"%{keyword2}%"))
        keyword2_abstract_clause = "AND LOWER(ab.text) LIKE LOWER(@keyword2)"

    extra_conditions = []
    if country_code:
        extra_conditions.append("country_code = @country_code")
        params.append(ScalarQueryParameter("country_code", "STRING", country_code.upper()))
    if grant_after:
        extra_conditions.append("grant_date > @grant_after")
        params.append(ScalarQueryParameter("grant_after", "INT64", grant_after))
    extra_where = (" AND " + " AND ".join(extra_conditions)) if extra_conditions else ""

    # Match keyword in title OR abstract, using EXISTS for abstract to avoid cross-join
    keyword2_title_clause = ""
    if keyword2:
        keyword2_title_clause = "AND LOWER(title.text) LIKE LOWER(@keyword2)"

    sql = f"""
    SELECT
      publication_number,
      country_code,
      ANY_VALUE(title.text) AS title,
      ANY_VALUE(filing_date) AS filing_date,
      ANY_VALUE(grant_date) AS grant_date
    FROM
      {PUB},
      UNNEST(title_localized) AS title
    WHERE
      title.language = 'en'
      AND (
        (LOWER(title.text) LIKE LOWER(@keyword) {keyword2_title_clause})
        OR EXISTS (
          SELECT 1 FROM UNNEST(abstract_localized) AS ab
          WHERE ab.language = 'en'
            AND LOWER(ab.text) LIKE LOWER(@keyword)
            {keyword2_abstract_clause}
        )
      )
      {extra_where}
    GROUP BY publication_number, country_code
    ORDER BY ANY_VALUE(grant_date) DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_international(country_code: str, keyword: str = None,
                         assignee: str = None, grant_after: int = None,
                         limit: int = 25, force: bool = False) -> list:
    """Search international (non-US) patents.

    Only the publications table has international patent data.

    Args:
        country_code: Country code (e.g., 'EP', 'JP', 'WO', 'CN', 'KR').
        keyword: Optional keyword for title search (case-insensitive).
        assignee: Optional assignee name filter (case-insensitive).
        grant_after: Minimum grant date as YYYYMMDD.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with publication_number, title, assignee, dates.
    """
    limit = min(limit, 100)

    conditions = ["country_code = @country_code", "title.language = 'en'"]
    params = [ScalarQueryParameter("country_code", "STRING", country_code.upper())]

    if keyword:
        conditions.append("LOWER(title.text) LIKE LOWER(@keyword)")
        params.append(ScalarQueryParameter("keyword", "STRING", f"%{keyword}%"))
    if grant_after:
        conditions.append("grant_date > @grant_after")
        params.append(ScalarQueryParameter("grant_after", "INT64", grant_after))

    assignee_join = ""
    if assignee:
        assignee_join = ", UNNEST(assignee_harmonized) AS a"
        conditions.append("UPPER(a.name) LIKE @assignee_name")
        params.append(ScalarQueryParameter("assignee_name", "STRING", f"%{assignee.upper()}%"))

    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      publication_number,
      country_code,
      kind_code,
      ANY_VALUE(title.text) AS title,
      ANY_VALUE(filing_date) AS filing_date,
      ANY_VALUE(grant_date) AS grant_date
    FROM
      {PUB},
      UNNEST(title_localized) AS title
      {assignee_join}
    WHERE
      {where}
    GROUP BY publication_number, country_code, kind_code
    ORDER BY ANY_VALUE(grant_date) DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def get_patent_detail(publication_number: str, force: bool = False) -> list:
    """Get detailed info for a specific patent by publication number.

    Args:
        publication_number: Full publication number (e.g., 'US-10000000-B2').
            Also accepts just '10000000' — will be normalized to US format.
        force: If True, bypass cost threshold after user approval.

    Returns:
        List with single patent dict including title, abstract, dates, inventors, assignees, CPC.
    """
    pn = publication_number.strip().replace(",", "")
    # Normalize bare numbers to US format
    if not any(c.isalpha() for c in pn.replace("-", "")):
        pn = f"US-{pn}-B2"
    elif pn.startswith("US") and "-" not in pn:
        # Handle "US10000000B2" -> "US-10000000-B2"
        m = re.match(r'(US)(\d+)(.*)', pn)
        if m:
            pn = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m.group(3) else f"{m.group(1)}-{m.group(2)}-B2"

    params = [ScalarQueryParameter("pub_number", "STRING", pn)]

    # Single query to get all detail including title and abstract
    sql = f"""
    SELECT
      p.publication_number,
      p.country_code,
      p.kind_code,
      p.application_number,
      p.filing_date,
      p.grant_date,
      p.priority_date,
      p.family_id,
      p.inventor,
      p.assignee,
      p.pct_number,
      ANY_VALUE(title.text) AS title,
      ANY_VALUE(SUBSTR(ab.text, 1, 500)) AS abstract_text
    FROM {PUB} p,
      UNNEST(p.title_localized) AS title,
      UNNEST(p.abstract_localized) AS ab
    WHERE p.publication_number = @pub_number
      AND title.language = 'en'
      AND ab.language = 'en'
    GROUP BY
      p.publication_number, p.country_code, p.kind_code,
      p.application_number, p.filing_date, p.grant_date,
      p.priority_date, p.family_id, p.inventor, p.assignee,
      p.pct_number
    LIMIT 1
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def count_by_assignee_cpc(cpc_prefix: str, limit: int = 20,
                          force: bool = False) -> list:
    """Analytics: Top assignees in a CPC classification.

    Args:
        cpc_prefix: CPC code prefix (e.g., 'H04L', 'G06N').
        limit: Number of top assignees (default 20).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with assignee_name, patent_count.
    """
    limit = min(limit, 50)
    params = [ScalarQueryParameter("cpc_prefix", "STRING", f"{cpc_prefix.upper().strip()}%")]
    sql = f"""
    SELECT
      a.name AS assignee_name,
      COUNT(DISTINCT publication_number) AS patent_count
    FROM
      {PUB},
      UNNEST(assignee_harmonized) AS a,
      UNNEST(cpc) AS c
    WHERE
      c.code LIKE @cpc_prefix
      AND country_code = 'US'
      AND a.name != ''
    GROUP BY assignee_name
    ORDER BY patent_count DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def filing_trends(keyword: str = None, cpc_prefix: str = None,
                  assignee: str = None, country_code: str = "US",
                  force: bool = False) -> list:
    """Analytics: Patent filing trends by year.

    At least one of keyword, cpc_prefix, or assignee must be provided.

    Args:
        keyword: Optional keyword filter (title search, case-insensitive).
        cpc_prefix: Optional CPC code prefix filter.
        assignee: Optional assignee name filter (case-insensitive).
        country_code: Country filter (default 'US').
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of dicts with filing_year and patent_count, ordered by year.
    """
    params = [ScalarQueryParameter("country_code", "STRING", country_code.upper())]
    conditions = ["country_code = @country_code"]
    joins = ""

    if keyword:
        joins += ", UNNEST(title_localized) AS title"
        conditions.append("LOWER(title.text) LIKE LOWER(@keyword)")
        conditions.append("title.language = 'en'")
        params.append(ScalarQueryParameter("keyword", "STRING", f"%{keyword}%"))
    if cpc_prefix:
        joins += ", UNNEST(cpc) AS c"
        conditions.append("c.code LIKE @cpc_prefix")
        params.append(ScalarQueryParameter("cpc_prefix", "STRING", f"{cpc_prefix.upper()}%"))
    if assignee:
        joins += ", UNNEST(assignee_harmonized) AS a"
        conditions.append("UPPER(a.name) LIKE @assignee_name")
        params.append(ScalarQueryParameter("assignee_name", "STRING", f"%{assignee.upper()}%"))

    if not (keyword or cpc_prefix or assignee):
        raise BigQueryError("At least one filter (keyword, cpc_prefix, or assignee) is required for filing_trends.")

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
      CAST(FLOOR(filing_date / 10000) AS INT64) AS filing_year,
      COUNT(DISTINCT publication_number) AS patent_count
    FROM
      {PUB}
      {joins}
    WHERE
      {where}
      AND filing_date > 19900101
    GROUP BY filing_year
    ORDER BY filing_year
    LIMIT 50
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search patents.publications on BigQuery")
    parser.add_argument("--force", action="store_true",
                        help="Bypass cost threshold (use after reviewing estimate)")
    sub = parser.add_subparsers(dest="command")

    p_claims = sub.add_parser("claims", help="Full-text claims search")
    p_claims.add_argument("keyword")
    p_claims.add_argument("--keyword2", "-k2")
    p_claims.add_argument("--country", "-c", default="US")
    p_claims.add_argument("--after", type=int)
    p_claims.add_argument("--limit", "-n", type=int, default=20)

    p_desc = sub.add_parser("description", help="Description/specification search")
    p_desc.add_argument("keyword")
    p_desc.add_argument("--keyword2", "-k2")
    p_desc.add_argument("--country", "-c", default="US")
    p_desc.add_argument("--limit", "-n", type=int, default=20)

    p_assignee = sub.add_parser("assignee", help="Search by assignee (international)")
    p_assignee.add_argument("name")
    p_assignee.add_argument("--country", "-c")
    p_assignee.add_argument("--limit", "-n", type=int, default=25)

    p_keyword = sub.add_parser("keyword", help="Search title/abstract")
    p_keyword.add_argument("keyword")
    p_keyword.add_argument("--keyword2", "-k2")
    p_keyword.add_argument("--country", "-c")
    p_keyword.add_argument("--after", type=int)
    p_keyword.add_argument("--limit", "-n", type=int, default=25)

    p_intl = sub.add_parser("international", help="Search international patents")
    p_intl.add_argument("country_code")
    p_intl.add_argument("--keyword", "-k")
    p_intl.add_argument("--assignee", "-a")
    p_intl.add_argument("--after", type=int)
    p_intl.add_argument("--limit", "-n", type=int, default=25)

    p_detail = sub.add_parser("detail", help="Get patent detail")
    p_detail.add_argument("publication_number")

    p_top = sub.add_parser("top-assignees", help="Top assignees in CPC class")
    p_top.add_argument("cpc_prefix")
    p_top.add_argument("--limit", "-n", type=int, default=20)

    p_trends = sub.add_parser("trends", help="Filing trends by year")
    p_trends.add_argument("--keyword", "-k")
    p_trends.add_argument("--cpc", dest="cpc_prefix")
    p_trends.add_argument("--assignee", "-a")
    p_trends.add_argument("--country", "-c", default="US")

    args = parser.parse_args()

    if args.command == "claims":
        results = search_claims_fulltext(args.keyword, keyword2=args.keyword2,
                                          country_code=args.country, grant_after=args.after,
                                          limit=args.limit, force=args.force)
    elif args.command == "description":
        results = search_description(args.keyword, keyword2=args.keyword2,
                                      country_code=args.country, limit=args.limit,
                                      force=args.force)
    elif args.command == "assignee":
        results = search_by_assignee(args.name, country_code=args.country,
                                      limit=args.limit, force=args.force)
    elif args.command == "keyword":
        results = search_by_keyword(args.keyword, keyword2=args.keyword2,
                                     country_code=args.country, grant_after=args.after,
                                     limit=args.limit, force=args.force)
    elif args.command == "international":
        results = search_international(args.country_code, keyword=args.keyword,
                                        assignee=args.assignee, grant_after=args.after,
                                        limit=args.limit, force=args.force)
    elif args.command == "detail":
        results = get_patent_detail(args.publication_number, force=args.force)
    elif args.command == "top-assignees":
        results = count_by_assignee_cpc(args.cpc_prefix, limit=args.limit,
                                         force=args.force)
    elif args.command == "trends":
        results = filing_trends(keyword=args.keyword, cpc_prefix=args.cpc_prefix,
                                 assignee=args.assignee, country_code=args.country,
                                 force=args.force)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(results, indent=2, default=str))
