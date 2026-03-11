"""
Result formatting utilities for Google Patent BigQuery responses.

Converts BigQuery result rows (list of dicts) into human-readable text summaries.
"""

import json
import csv
import io
from typing import Optional


def _format_date(date_val) -> str:
    """Format a YYYYMMDD integer date to readable format."""
    if not date_val:
        return "N/A"
    s = str(date_val)
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def format_patent_list(rows: list, source: str = "publications") -> str:
    """Format a list of patent results.

    Args:
        rows: List of result dicts from BigQuery.
        source: 'publications', 'patentsview', 'claims', 'assignments', 'ptab'.

    Returns:
        Human-readable formatted text.
    """
    if not rows:
        return "No results found."

    lines = [f"Found {len(rows)} result(s):\n"]

    if source == "publications":
        for i, r in enumerate(rows, 1):
            pub_num = r.get("publication_number", "N/A")
            title = r.get("title", "No title")
            cc = r.get("country_code", "")
            filing = _format_date(r.get("filing_date"))
            grant = _format_date(r.get("grant_date"))
            assignee = r.get("assignee_name", "")

            lines.append(f"  {i}. {pub_num} — {title}")
            date_line = f"     Filed: {filing}"
            if grant != "N/A":
                date_line += f" | Granted: {grant}"
            if cc:
                date_line += f" | Country: {cc}"
            lines.append(date_line)
            if assignee:
                lines.append(f"     Assignee: {assignee}")
            lines.append("")

    elif source == "patentsview":
        for i, r in enumerate(rows, 1):
            pat_id = r.get("patent_id", "N/A")
            title = r.get("title", r.get("patent_title", "No title"))
            date = r.get("date", r.get("patent_date", "N/A"))
            assignee = r.get("organization", r.get("assignee_organization", ""))

            lines.append(f"  {i}. US {pat_id} — {title}")
            lines.append(f"     Date: {date}")
            if assignee:
                lines.append(f"     Assignee: {assignee}")
            lines.append("")

    elif source == "claims":
        for i, r in enumerate(rows, 1):
            pat_id = r.get("patent_id", "N/A")
            claim_num = r.get("sequence", r.get("claim_number", "?"))
            text = r.get("text", r.get("claim_text", ""))
            # Truncate long claim text
            if len(text) > 300:
                text = text[:300].rsplit(" ", 1)[0] + "..."

            lines.append(f"  {i}. US {pat_id}, Claim {claim_num}")
            lines.append(f"     {text}")
            lines.append("")

    elif source == "assignments":
        for i, r in enumerate(rows, 1):
            pat_id = r.get("patent_id", "N/A")
            ee = r.get("ee_name", "N/A")
            or_name = r.get("or_name", "N/A")
            convey = r.get("convey_text", "")
            recorded = r.get("recorded_date", "N/A")

            lines.append(f"  {i}. Patent {pat_id} — Recorded: {recorded}")
            lines.append(f"     From: {or_name}")
            lines.append(f"     To:   {ee}")
            if convey:
                lines.append(f"     Type: {convey}")
            lines.append("")

    elif source == "ptab":
        for i, r in enumerate(rows, 1):
            trial = r.get("trial_number", "N/A")
            pat = r.get("patent_number", "N/A")
            trial_type = r.get("type", "N/A")
            status = r.get("status", "N/A")
            petitioner = r.get("petitioner_party_name", "N/A")
            owner = r.get("patent_owner_name", "N/A")
            filed = r.get("filing_date", "N/A")

            lines.append(f"  {i}. {trial} ({trial_type})")
            lines.append(f"     Patent: US {pat} | Status: {status}")
            lines.append(f"     Filed: {filed}")
            lines.append(f"     Petitioner: {petitioner}")
            lines.append(f"     Patent Owner: {owner}")
            lines.append("")

    elif source == "trends":
        lines = [f"Filing trends ({len(rows)} years):\n"]
        for r in rows:
            year = r.get("filing_year", "?")
            count = r.get("patent_count", 0)
            bar = "#" * min(count // 10, 50)
            lines.append(f"  {year}: {count:>6,}  {bar}")
        lines.append("")

    elif source == "top-assignees":
        lines = [f"Top assignees ({len(rows)} shown):\n"]
        for i, r in enumerate(rows, 1):
            name = r.get("assignee_name", "N/A")
            count = r.get("patent_count", 0)
            lines.append(f"  {i}. {name}: {count:,} patents")
        lines.append("")

    return "\n".join(lines)


def format_patent_detail(rows: list) -> str:
    """Format detailed patent info.

    Args:
        rows: Single-element list from get_patent_detail.

    Returns:
        Detailed formatted text.
    """
    if not rows:
        return "No patent found."

    r = rows[0]
    lines = [
        f"Patent: {r.get('publication_number', 'N/A')}",
        "=" * 50,
        f"Title:       {r.get('title', 'N/A')}",
        f"Country:     {r.get('country_code', 'N/A')} ({r.get('kind_code', '')})",
        f"Application: {r.get('application_number', 'N/A')}",
        f"Filed:       {_format_date(r.get('filing_date'))}",
        f"Granted:     {_format_date(r.get('grant_date'))}",
        f"Priority:    {_format_date(r.get('priority_date'))}",
        f"Family ID:   {r.get('family_id', 'N/A')}",
    ]

    if r.get("pct_number"):
        lines.append(f"PCT:         {r['pct_number']}")

    inventors = r.get("inventor", [])
    if inventors:
        inv_str = ", ".join(inventors[:5])
        if len(inventors) > 5:
            inv_str += f" (+{len(inventors) - 5} more)"
        lines.append(f"Inventors:   {inv_str}")

    assignees = r.get("assignee", [])
    if assignees:
        lines.append(f"Assignees:   {', '.join(assignees)}")

    abstract = r.get("abstract_text", "")
    if abstract:
        lines.append(f"\nAbstract:\n{abstract}")

    return "\n".join(lines)


def _csv_safe(value) -> str:
    """Convert a value to a CSV-safe string."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


def to_csv(rows: list, fields: list = None) -> str:
    """Convert rows to CSV string."""
    if not rows:
        return "No records to export."
    if fields is None:
        fields = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_safe(v) for k, v in row.items()})
    return output.getvalue()


def to_json(rows: list, pretty: bool = True) -> str:
    """Convert rows to JSON string."""
    return json.dumps(rows, indent=2 if pretty else None, default=str)


if __name__ == "__main__":
    # Quick test
    sample = [
        {
            "publication_number": "US-10000000-B2",
            "title": "Coherent LADAR using intra-pixel quadrature detection",
            "filing_date": 20140606,
            "grant_date": 20180619,
            "country_code": "US",
        }
    ]
    print(format_patent_list(sample))
