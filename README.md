# Google Patent Search

A Claude Code skill for searching Google Patents using plain English. Ask questions in natural language and get results from 166M+ patent publications across 17+ countries — powered by BigQuery under the hood.

## What This Skill Does

This skill lets you search patent data using natural language. You ask questions in plain English, and the skill translates them into optimized BigQuery queries, runs them, and presents the results. It complements the existing **[USPTO Patent Search](https://github.com/LeonardHope/USPTO-MyODP-and-PatentsView-Natural-Language-API-Search)** skill by adding capabilities that REST APIs can't provide:

- **Full-text claims search** — "find patents with claims mentioning blockchain and authentication"
- **Description/specification search** — "search descriptions for quantum error correction"
- **International patents** — "find European patents about wireless charging"
- **Similar patent discovery** — "what patents are similar to US-10000000-B2?"
- **Large-scale analytics** — "who are the top filers in CPC G06N?"

## When Each Skill Fires

### This skill (Google Patent Search) auto-triggers on:
- "search claims for authentication methods"
- "find European patents about wireless charging"
- "patents similar to US-10000000-B2"
- "top assignees in CPC H04L"
- "search Google Patents for blockchain"

### USPTO Patent Search auto-triggers on:
- "what's the status of application 16/123,456?"
- "download the file history for patent 11,887,351"
- "has patent 10,000,000 been challenged at PTAB?"
- "who owns patent 9,876,543?"
- "find patents by inventor John Smith" (defaults to USPTO)

### How they complement each other

| Capability | Google Patent Search | USPTO Patent Search |
|---|---|---|
| Claims text search | Yes (full-text) | No |
| International patents | 17+ countries | US only |
| Similar patents | Google AI similarity | No |
| Patent analytics | Yes | Limited |
| Live prosecution status | No (snapshots) | Yes (live API) |
| PDF downloads | No | Yes |
| Office action details | Snapshots | Live API |
| Setup required | GCP + gcloud | API keys only |

**Rule of thumb**: Use Google Patent Search for *discovering and analyzing* patents. Use USPTO Patent Search for *specific patent lookups and prosecution data*.

## Data Freshness

This skill queries Google's BigQuery public patent datasets, which are **periodic snapshots** — not the same live index that powers patents.google.com. This means results may differ from what you see on the Google Patents website:

| Dataset | BigQuery Freshness | Google Patents Web |
|---|---|---|
| Patent publications (titles, abstracts, claims) | Updated periodically (check [Google's dataset page](https://console.cloud.google.com/bigquery?p=patents-public-data) for latest) | Live |
| Assignee names | Reflects original filing only — does **not** include subsequent assignments | Incorporates assignment records, shows current owner |
| USPTO assignment records | **Frozen at Feb 2017** — severely outdated | Live |
| PatentsView tables | Updated periodically (~quarterly) | N/A |

**Key implication for assignee searches:** If a patent was filed by individual inventors and later assigned to a company, BigQuery will show the inventors as assignees while Google Patents web will show the company. For the most current assignee information, use the `uspto-patent-search` skill (which queries live USPTO APIs) or search patents.google.com directly.

## Installation

### Prerequisites
- [Claude Code](https://claude.com/claude-code) CLI installed
- Google Cloud account (free)
- Google Cloud project with BigQuery API enabled
- `gcloud` CLI installed

### Step 1: Clone the repo

```bash
git clone https://github.com/LeonardHope/Google-Patents-Natural-Language-API-Search.git
cd Google-Patents-Natural-Language-API-Search
```

### Step 2: Install the Claude Code skill

Symlink the entire repo into your Claude Code skills directory so all paths resolve automatically:

```bash
ln -s "$(pwd)" ~/.claude/skills/google-patent-search
```

This creates a symlink so Claude Code can find both the SKILL.md and the scripts directory. If you move the repo later, just re-run this command from the new location.

### Step 3: Set up Google Cloud / BigQuery

```bash
# Install gcloud CLI
brew install --cask google-cloud-sdk

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Authenticate
gcloud auth application-default login
```

### Step 4: Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Verify setup

```bash
python3 get_started.py
```

### Cost

- **Free tier**: 1 TB/month of queries — no credit card or billing account needed
- **Beyond the free tier**: $6.25 per TB. Add a [billing account](https://console.cloud.google.com/billing) to your Google Cloud project and queries automatically continue past 1 TB at this rate. There is no manual threshold to raise — billing kicks in once the free tier is exhausted.
- Built-in cost guardrails: queries over 5 GB require explicit approval, showing you the estimated cost as a percentage of the free tier before running
- Typical query costs:
  - Assignee/inventor/CPC searches: 500 MB - 2 GB
  - Keyword searches (title/abstract): 1 - 5 GB
  - Full-text claims searches: 40 - 150 GB (a single claims search can use 5-15% of the free tier)

## Usage

### Explicit invocation
```
/google-patent-search claims mentioning blockchain and authentication
/google-patent-search European patents about wireless charging
/google-patent-search top assignees in CPC G06N
```

### Natural language (auto-triggers)
```
"search claims for machine learning and natural language processing"
"find Japanese patents about battery technology"
"what patents are similar to US-10000000-B2?"
"show filing trends for AI patents"
```

## Architecture

```
scripts/
├── bigquery_client.py       # Auth, cost estimation, safety guardrails
├── patentsview_search.py    # Cheap patentsview.* table queries
├── publications_search.py   # Main publications table (full-text, international)
├── research_search.py       # Google AI similarity & translations
├── prosecution_search.py    # Assignments, litigation, PTAB, PEDS, ITC
└── format_results.py        # Human-readable formatting
```

Every query flows through `bigquery_client.py` which enforces:
1. **Query validation** — rejects unsafe or unbounded queries
2. **Dry-run cost check** — estimates data scanned before executing
3. **Hard cost cap** — refuses expensive queries (configurable threshold)
