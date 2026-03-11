"""
Prosecution Search - Query USPTO OCE tables on BigQuery.

Tables:
    uspto_oce_assignment.* — Patent assignments/ownership transfers
    uspto_oce_litigation.* — Patent litigation records
    uspto_oce_office_actions.* — Office action data
    uspto_ptab.* — PTAB trial data (IPR, PGR, CBM)
    uspto_peds.* — Patent Examination Data System
    usitc_investigations.* — ITC Section 337 investigations
"""

import sys
import json
import argparse
from google.cloud.bigquery import ScalarQueryParameter
from bigquery_client import get_client, BigQueryError, PUBLIC_PROJECT

PP = PUBLIC_PROJECT


def search_assignments(patent_number: str = None, assignee: str = None,
                       limit: int = 25, force: bool = False) -> list:
    """Search patent assignment records.

    Args:
        patent_number: Optional patent number to look up.
        assignee: Optional assignee name to search.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of assignment record dicts.
    """
    limit = min(limit, 100)
    conditions = []
    params = []

    if patent_number:
        clean = patent_number.replace(",", "").replace("US", "").strip()
        conditions.append("d.grant_doc_num = @patent_number")
        params.append(ScalarQueryParameter("patent_number", "STRING", clean))

    if assignee:
        conditions.append("UPPER(ee.ee_name) LIKE @assignee_name")
        params.append(ScalarQueryParameter("assignee_name", "STRING", f"%{assignee.upper()}%"))

    if not conditions:
        raise BigQueryError("At least one of patent_number or assignee is required.")

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
      d.grant_doc_num AS patent_id,
      a.reel_no,
      a.frame_no,
      ee.ee_name,
      o.or_name,
      a.convey_text,
      a.record_dt AS recorded_date
    FROM `{PP}.uspto_oce_assignment.assignment` a
    JOIN `{PP}.uspto_oce_assignment.assignee` ee ON a.rf_id = ee.rf_id
    JOIN `{PP}.uspto_oce_assignment.assignor` o ON a.rf_id = o.rf_id
    JOIN `{PP}.uspto_oce_assignment.documentid` d ON a.rf_id = d.rf_id
    WHERE {where}
    ORDER BY a.record_dt DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_litigation(patent_number: str = None, party: str = None,
                      limit: int = 25, force: bool = False) -> list:
    """Search patent litigation records.

    Args:
        patent_number: Optional patent number involved in litigation.
        party: Optional party name to search.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of litigation record dicts.
    """
    limit = min(limit, 100)
    conditions = []
    params = []

    if patent_number:
        clean = patent_number.replace(",", "").replace("US", "").strip()
        conditions.append("CAST(patent_id AS STRING) = @patent_number")
        params.append(ScalarQueryParameter("patent_number", "STRING", clean))

    if party:
        conditions.append(
            "(UPPER(plaintiff) LIKE @party_name OR UPPER(defendant) LIKE @party_name)"
        )
        params.append(ScalarQueryParameter("party_name", "STRING", f"%{party.upper()}%"))

    if not conditions:
        raise BigQueryError("At least one of patent_number or party is required.")

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
      case_id,
      patent_id,
      plaintiff,
      defendant,
      filed_date,
      terminated_date,
      outcome
    FROM `{PP}.uspto_oce_litigation.litigation`
    WHERE {where}
    ORDER BY filed_date DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_ptab(patent_number: str = None, petitioner: str = None,
                trial_type: str = None, limit: int = 25,
                force: bool = False) -> list:
    """Search PTAB trial data.

    Args:
        patent_number: Optional patent number challenged at PTAB.
        petitioner: Optional petitioner name.
        trial_type: Optional trial type ('IPR', 'PGR', 'CBM').
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of PTAB trial record dicts.
    """
    limit = min(limit, 100)
    conditions = []
    params = []

    if patent_number:
        clean = patent_number.replace(",", "").replace("US", "").strip()
        conditions.append("CAST(patent_number AS STRING) = @patent_number")
        params.append(ScalarQueryParameter("patent_number", "STRING", clean))

    if petitioner:
        conditions.append("UPPER(petitioner_party_name) LIKE @petitioner_name")
        params.append(ScalarQueryParameter("petitioner_name", "STRING", f"%{petitioner.upper()}%"))

    if trial_type:
        conditions.append("UPPER(type) = @trial_type")
        params.append(ScalarQueryParameter("trial_type", "STRING", trial_type.upper()))

    if not conditions:
        raise BigQueryError("At least one filter is required for PTAB search.")

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
      trial_number,
      patent_number,
      type,
      status,
      petitioner_party_name,
      patent_owner_name,
      filing_date,
      institution_decision_date,
      fwd_date
    FROM `{PP}.uspto_ptab.trials`
    WHERE {where}
    ORDER BY filing_date DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_peds(application_number: str = None, patent_number: str = None,
                limit: int = 10, force: bool = False) -> list:
    """Search Patent Examination Data System (prosecution status).

    Args:
        application_number: Application number (e.g., '16123456').
        patent_number: Granted patent number.
        limit: Max results (default 10).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of PEDS record dicts.
    """
    limit = min(limit, 50)
    conditions = []
    params = []

    if application_number:
        clean = application_number.replace("/", "").replace(",", "").strip()
        conditions.append("appl_id = @appl_id")
        params.append(ScalarQueryParameter("appl_id", "STRING", clean))

    if patent_number:
        clean = patent_number.replace(",", "").replace("US", "").strip()
        conditions.append("patent_number = @patent_number")
        params.append(ScalarQueryParameter("patent_number", "STRING", clean))

    if not conditions:
        raise BigQueryError("At least one of application_number or patent_number is required.")

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
      appl_id,
      patent_number,
      app_filing_date,
      patent_issue_date,
      app_status,
      app_status_date,
      patent_title,
      app_type
    FROM `{PP}.uspto_peds.applications`
    WHERE {where}
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


def search_itc(patent_number: str = None, respondent: str = None,
               limit: int = 25, force: bool = False) -> list:
    """Search ITC Section 337 investigations.

    Args:
        patent_number: Optional patent number involved.
        respondent: Optional respondent name.
        limit: Max results (default 25).
        force: If True, bypass cost threshold after user approval.

    Returns:
        List of ITC investigation dicts.
    """
    limit = min(limit, 100)
    conditions = []
    params = []

    if patent_number:
        clean = patent_number.replace(",", "").replace("US", "").strip()
        conditions.append("CAST(patent_id AS STRING) = @patent_number")
        params.append(ScalarQueryParameter("patent_number", "STRING", clean))

    if respondent:
        conditions.append("UPPER(respondent) LIKE @respondent_name")
        params.append(ScalarQueryParameter("respondent_name", "STRING", f"%{respondent.upper()}%"))

    if not conditions:
        raise BigQueryError("At least one of patent_number or respondent is required.")

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
      investigation_number,
      patent_id,
      complainant,
      respondent,
      date_filed,
      date_terminated,
      outcome
    FROM `{PP}.usitc_investigations.investigations_337`
    WHERE {where}
    ORDER BY date_filed DESC
    LIMIT {limit}
    """
    client = get_client()
    return client.run_query(sql, query_params=params, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search USPTO prosecution data on BigQuery")
    parser.add_argument("--force", action="store_true",
                        help="Bypass cost threshold (use after reviewing estimate)")
    sub = parser.add_subparsers(dest="command")

    p_assign = sub.add_parser("assignments", help="Search assignments")
    p_assign.add_argument("--patent", "-p")
    p_assign.add_argument("--assignee", "-a")
    p_assign.add_argument("--limit", "-n", type=int, default=25)

    p_lit = sub.add_parser("litigation", help="Search litigation")
    p_lit.add_argument("--patent", "-p")
    p_lit.add_argument("--party")
    p_lit.add_argument("--limit", "-n", type=int, default=25)

    p_ptab = sub.add_parser("ptab", help="Search PTAB trials")
    p_ptab.add_argument("--patent", "-p")
    p_ptab.add_argument("--petitioner")
    p_ptab.add_argument("--type", "-t", dest="trial_type")
    p_ptab.add_argument("--limit", "-n", type=int, default=25)

    p_peds = sub.add_parser("peds", help="Search PEDS")
    p_peds.add_argument("--app", "-a", dest="application_number")
    p_peds.add_argument("--patent", "-p", dest="patent_number")
    p_peds.add_argument("--limit", "-n", type=int, default=10)

    p_itc = sub.add_parser("itc", help="Search ITC investigations")
    p_itc.add_argument("--patent", "-p")
    p_itc.add_argument("--respondent", "-r")
    p_itc.add_argument("--limit", "-n", type=int, default=25)

    args = parser.parse_args()

    if args.command == "assignments":
        results = search_assignments(patent_number=args.patent, assignee=args.assignee,
                                      limit=args.limit, force=args.force)
    elif args.command == "litigation":
        results = search_litigation(patent_number=args.patent, party=args.party,
                                     limit=args.limit, force=args.force)
    elif args.command == "ptab":
        results = search_ptab(patent_number=args.patent, petitioner=args.petitioner,
                               trial_type=args.trial_type, limit=args.limit,
                               force=args.force)
    elif args.command == "peds":
        results = search_peds(application_number=args.application_number,
                               patent_number=args.patent_number, limit=args.limit,
                               force=args.force)
    elif args.command == "itc":
        results = search_itc(patent_number=args.patent, respondent=args.respondent,
                              limit=args.limit, force=args.force)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(results, indent=2, default=str))
