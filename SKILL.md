---
name: google-patent-search
description: >
  Search Google Patents using BigQuery for full-text claims search, description/specification
  search, international patents, similar patent discovery, and large-scale patent analytics.

  Use this skill when the user wants to:
  - Search patent claims text: "search claims for...", "claims mentioning...", "find claims about..."
  - Search patent descriptions/specifications: "search description for...", "specification mentions..."
  - Find international patents: "European patents", "Japanese patents", "PCT applications",
    "patents filed in China/Korea/Germany", non-US country codes
  - Find similar patents: "similar patents to...", "patents like...", "related patents"
  - Search Google Patents specifically: "search Google Patents for..."
  - Run patent analytics: "top assignees in CPC...", "patent filing trends", "how many patents..."
  - Search by assignee across jurisdictions: "Samsung's worldwide patents"

  Do NOT use this skill for:
  - Patent number lookups or basic patent info (use uspto-patent-search)
  - Prosecution status or file wrapper documents (use uspto-patent-search)
  - PTAB proceedings or IPR/PGR status (use uspto-patent-search)
  - Patent assignment chain of title (use uspto-patent-search)
  - Office action rejections or examiner citations (use uspto-patent-search)
  - PDF document downloads (use uspto-patent-search)
argument-hint: "[search query]"
---

# Google Patent Search Skill

## Overview

This skill provides SQL-level access to Google Patents Public Datasets on BigQuery — 166M+ patent
publications from 17+ countries. It complements the `uspto-patent-search` skill by offering
full-text claims/description search, international patent coverage, and large-scale analytics.

You have 5 search modules, each targeting different BigQuery tables:

| Module | Script | Best For |
|--------|--------|----------|
| PatentsView (BQ) | `patentsview_search.py` | Individual claims search, assignee/inventor lookup (cheap) |
| Publications | `publications_search.py` | Full-text claims/description, international patents, keyword search |
| Research | `research_search.py` | Similar patents, Google's AI-extracted terms |
| Prosecution | `prosecution_search.py` | Assignments, litigation, PTAB, PEDS, ITC (via BigQuery) |
| Format | `format_results.py` | Human-readable result formatting |

---

## Setup

Before running any queries, verify the user has BigQuery access configured.

Run `get_started.py` from the skill's root directory (the directory containing this SKILL.md file):

```bash
python3 get_started.py
```

If setup is needed, guide the user through:
1. Install gcloud CLI: `brew install --cask google-cloud-sdk`
2. Set project: `gcloud config set project YOUR_PROJECT_ID`
3. Authenticate: `gcloud auth application-default login`
4. Install deps: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`

---

## How to Handle User Requests

### Step 1: Parse the Natural Language

Identify:
- **Search type**: Claims text, description text, keyword/title, assignee, inventor, CPC, analytics
- **Scope**: US only vs international, single patent vs broad search
- **Filters**: Date range, country, assignee, CPC code, keywords

### Step 2: Choose the Right Table (Decision Matrix)

Use this matrix — check top to bottom, use the first match:

| User wants to... | Key signals | Use this script + function |
|---|---|---|
| Search individual claim text | "claims mentioning", "claim 1 says" | `patentsview_search.search_claims()` |
| Full-text claims + other filters | "claims about X by Company Y" | `publications_search.search_claims_fulltext()` |
| Search descriptions/specifications | "description mentions", "specification" | `publications_search.search_description()` |
| Find patents by assignee (US only, cheap) | company name, "patents by" | **See assignee caveat below** |
| Find patents by assignee (international) | company + non-US country | **See assignee caveat below** |
| Find patents by inventor | person name, "invented by" | `patentsview_search.search_by_inventor()` |
| Search by CPC classification | CPC code, "class H04L" | `patentsview_search.search_by_cpc()` |
| Keyword search (title/abstract) | technology terms, general keyword | `publications_search.search_by_keyword()` |
| International patent search | country name, EP/WO/JP/CN/KR | `publications_search.search_international()` |
| Find similar patents | "similar to", "patents like" | `research_search.find_similar_patents()` |
| Top assignees in a field | "top companies in", "who files most" | `publications_search.count_by_assignee_cpc()` |
| Filing trends over time | "trends", "filings per year" | `publications_search.filing_trends()` |
| Patent detail lookup | specific publication number | `publications_search.get_patent_detail()` |
| Assignment history (BigQuery) | "ownership", "assigned to" (historical) | `prosecution_search.search_assignments()` |
| Litigation records | "sued", "litigation", "infringement" | `prosecution_search.search_litigation()` |
| PTAB challenges (BigQuery) | "IPR", "PTAB" (historical data) | `prosecution_search.search_ptab()` |
| ITC investigations | "ITC", "Section 337", "import ban" | `prosecution_search.search_itc()` |

### Assignee Search Caveat

**BigQuery assignee data is unreliable for finding patents owned by a company.** The `assignee` and
`assignee_harmonized` fields in BigQuery reflect the **original filing** only — not subsequent
assignments. If a patent was filed by individual inventors and later assigned to a company, BigQuery
will still show the inventors as assignees. Additionally, the USPTO assignment tables in BigQuery
are **frozen at February 2017** and will not reflect any transfers after that date.

**What to do when the user searches by assignee:**

1. **Before running the query**, tell the user:
   > "BigQuery assignee data only reflects the original filing and may miss patents that were
   > later assigned to this company. For more complete assignee results, I can search using the
   > USPTO Patent Search skill instead, which uses live USPTO assignment records. Would you like
   > me to use that instead?"

2. If the user wants to proceed with BigQuery anyway:
   - US only: use `patentsview_search.search_by_assignee()`
   - International: use `publications_search.search_by_assignee()`
   - Always include a note in the results that the list may be incomplete

3. If the user wants more complete results, use the `uspto-patent-search` skill instead.

**Cost-first routing**: Always prefer cheaper tables when they can answer the question:
- `patentsview.claim` (~small) over `claims_localized` in publications (~131GB)
- `patentsview.assignee` over `assignee_harmonized` in publications
- Only use `patents.publications` when you need full-text, international data, or combined filters

### Step 3: Run the Query

All scripts are in the `scripts/` subdirectory relative to the skill root (the directory containing this SKILL.md file). Import and call:

```python
import sys, os
# Use the directory containing SKILL.md as the base
scripts_dir = os.path.join(os.path.dirname(os.path.abspath("SKILL.md")), "scripts")
sys.path.insert(0, scripts_dir)
from patentsview_search import search_claims
results = search_claims("blockchain", keyword2="authentication")
```

Or run via CLI from the scripts directory:
```bash
cd scripts/
python3 patentsview_search.py claims blockchain --keyword2 authentication
```

### Step 4: Format and Present Results

Use the formatters:
```python
from format_results import format_patent_list, format_patent_detail
print(format_patent_list(results, source="claims"))
```

Or format manually following these principles:
- Lead with the answer, not the data
- Show publication_number, title, date, assignee
- Note total count and whether more results exist
- Mention cost if the query was expensive (shown in stderr)

### Step 5: Cost Awareness

Every query goes through a dry-run cost check. The free tier allows **1 TB/month** of queries.

**Thresholds:**
- **< 1 GB**: Silent — runs immediately
- **1-5 GB**: Warning printed to stderr, runs automatically
- **> 5 GB**: **Blocked** — you must ask the user before proceeding

**When a query exceeds 5 GB**, do NOT silently raise the limit. Instead:

1. Use `client.estimate_cost(sql)` to get the cost estimate
2. Tell the user the cost in plain terms:
   > "This search would scan **X GB**, which is **Y%** of the 1 TB/month free tier.
   > Would you like to proceed?"
3. If the user approves, re-run with `client.run_query(sql, force=True)`
4. If the user declines, suggest ways to reduce cost:
   - Add a `country_code` filter (e.g., `country_code = 'US'`)
   - Use a cheaper table (patentsview instead of publications)
   - Add date range filters
   - Use more specific keywords

**Note:** Full-text claims and description searches inherently scan large amounts of data
(~40-150 GB). This is expected — these are the skill's most powerful features. Just make
sure the user knows the cost before running them.

---

## Data Freshness Warning

BigQuery patent data is a **periodic snapshot**, not the live index that powers patents.google.com.

**Critical limitation for assignee searches:** The BigQuery `assignee` and `assignee_harmonized` fields
reflect the **original filing** only. If a patent was filed by individual inventors and later assigned
to a company, BigQuery still shows the inventors — not the company. The USPTO assignment tables in
BigQuery are **frozen at February 2017** and severely outdated.

When returning assignee search results, always mention this caveat. If the user needs current
ownership data, suggest using the `uspto-patent-search` skill (live USPTO APIs) or searching
patents.google.com directly.

---

## When to Use This Skill vs. USPTO Patent Search

| Capability | This skill (Google Patents BQ) | USPTO Patent Search |
|---|---|---|
| Claims text search | Full-text SQL search | Not available |
| Description text search | Full-text SQL search | Not available |
| International patents | 17+ countries | US only |
| Similar patents | Google AI similarity | Not available |
| Patent analytics | SQL aggregations | Limited |
| Real-time prosecution status | Stale (periodic snapshots) | Live API |
| PDF document download | Not available | Yes |
| Office action text/rejections | Stale snapshots | Live API |
| PTAB live status | Stale snapshots | Live API |
| No setup required | Needs GCP + gcloud | Just API keys |

**Rule of thumb**: Use this skill for *searching and discovering* patents. Use USPTO skill for
*specific patent lookups and prosecution data*.

---

## Multi-Step Patterns

### Technology Landscape Analysis
1. `publications_search.count_by_assignee_cpc("G06N")` → top AI patent filers
2. `publications_search.filing_trends(cpc_prefix="G06N")` → trends over time
3. Pick top assignees → `publications_search.search_by_assignee("Google")` for details

### International Portfolio Search
1. `publications_search.search_by_assignee("Samsung", country_code="US")` → US patents
2. `publications_search.search_by_assignee("Samsung", country_code="EP")` → European patents
3. Compare coverage

### Claims Deep Dive
1. `patentsview_search.search_claims("blockchain")` → quick, cheap scan
2. If need more filters: `publications_search.search_claims_fulltext("blockchain", keyword2="authentication", grant_after=20200101)`

---

## Error Handling

- **BigQueryError with [SETUP_REQUIRED]**: Guide user through `get_started.py`
- **Query refused (too expensive)**: Suggest narrower filters or cheaper table
- **Dry run failed**: Usually a SQL syntax issue — check the query
- **No results**: Try broader search terms, different table, or check spelling

---

## Security

- No API keys stored — uses Application Default Credentials from gcloud
- Queries against public datasets only (no user data access)
- All SQL goes through validation before execution
- Cost guardrails prevent runaway queries
