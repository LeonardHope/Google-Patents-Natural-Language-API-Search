# Google Patents BigQuery Setup Guide

> **How to set up programmatic access to Google's patent data using BigQuery — for natural language patent search tools, analytics, and AI-powered patent research.**

## Overview

Google does not offer a direct REST API for Google Patents (patents.google.com). However, Google makes its patent data available through **Google Patents Public Datasets** on **BigQuery** — Google's serverless data warehouse.

This gives you SQL-based access to **166+ million patent publications** from 17+ countries, including **full-text claims and descriptions for US patents**. Combined with an AI layer (like Claude), you can build natural language search tools that query specific patent fields — such as searching for terms within claims text — with full control over the search logic.

### Why BigQuery over third-party APIs?

| Feature | BigQuery | Third-party (SerpApi, etc.) |
|---|---|---|
| Data source | Official Google patent data | Scrapes patents.google.com |
| Claims-level search | Yes — direct SQL on claims text | No — searches all fields together |
| Cost | 1 TB/month free | 250 searches/mo free, then $75+/mo |
| Robustness | Google-maintained, stable SQL interface | Breaks if Google changes HTML |
| Customization | Full SQL control over queries | Limited to API parameters |

### What you'll need

- A Google account
- A Google Cloud project (free to create)
- BigQuery API enabled (free)
- Google Cloud CLI (`gcloud`) installed
- No billing required for the free tier (1 TB/month of queries)

---

## Step 1: Install the Google Cloud CLI

The Google Cloud CLI (`gcloud`) is used for authentication and project management. This is the recommended approach — it works for all users regardless of organization security policies.

### macOS (Homebrew)

```bash
brew install --cask google-cloud-sdk
```

### macOS / Linux (manual)

```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL  # restart your shell
```

### Windows

Download the installer from: https://cloud.google.com/sdk/docs/install

### Verify installation

```bash
gcloud --version
```

---

## Step 2: Access the Google Cloud Console

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Sign in with your Google account
3. If prompted, accept the Google Cloud Terms of Service

---

## Step 3: Create a New Project

A Google Cloud project is the container for all your resources, including BigQuery access.

1. In the Google Cloud Console, click the **project selector** dropdown at the top of the page (it may say "Select a project" or show an existing project name)
2. In the dialog that appears, click **New Project**
3. Enter a project name (e.g., `patent-search`)
4. The Project ID will be auto-generated — you can customize it if you want (you'll use this ID in API calls later)
5. For Organization, select your organization or leave as "No organization"
6. Click **Create**
7. Wait for the notification that the project has been created, then select it from the project dropdown

> **Note your Project ID** — you'll need it later. It looks something like `patent-search-123456`. You can always find it in the project settings.

---

## Step 4: Enable the BigQuery API

BigQuery API is typically enabled by default for new projects, but verify:

1. In the Cloud Console, navigate to **APIs & Services > Library** (or go directly to `console.cloud.google.com/apis/library/bigquery.googleapis.com`)
2. Search for **"BigQuery API"**
3. If it shows "API Enabled" with a green checkmark, you're all set
4. If not, click **Enable**

---

## Step 5: Access the Google Patents Public Dataset

The patent data lives in a public BigQuery project called `patents-public-data`. You don't need to copy or import anything — you query it directly.

### Via the Marketplace (recommended for first-time setup)

1. Go to the [Google Patents Public Data Marketplace page](https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data)
2. Click **View data set**
3. This opens BigQuery with the `patents-public-data` project visible in the Explorer panel

### Via direct URL

You can also navigate directly to BigQuery and query the public tables by their full path (e.g., `` `patents-public-data.patents.publications` ``) without any setup.

---

## Step 6: Set Up Authentication for Programmatic Access

To query BigQuery from code (Python, Node.js, etc.), you need to authenticate.

### Application Default Credentials (Recommended)

This approach uses your Google account credentials stored locally. It works for everyone — including users in organizations that restrict service account key creation.

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Authenticate for application default credentials
gcloud auth application-default login
```

This will open a browser window. Sign in with your Google account and click **Allow**. Your credentials are saved to `~/.config/gcloud/application_default_credentials.json` automatically.

> **Note:** Your Google account needs BigQuery permissions on the project. If you created the project, you're the Owner and already have full access. If someone else created the project, you'll need at least **BigQuery Job User** and **BigQuery Data Viewer** roles.

### Service Account Key (Alternative for server deployments)

If you need to deploy to a server or CI/CD environment where interactive login isn't possible:

1. Go to **IAM & Admin > Service Accounts** in the Cloud Console
2. Click **+ Create Service Account**
3. Name it (e.g., `patent-search-service`)
4. Grant roles: **BigQuery Job User** + **BigQuery Data Viewer**
5. Go to the **Keys** tab and click **Add Key > Create New Key > JSON**

> **Note:** Some organizations block service account key creation via the `iam.disableServiceAccountKeyCreation` org policy. If you encounter this, use Application Default Credentials instead, or ask your org admin to grant an exception. Google recommends ADC over service account keys for security.

---

## Step 7: Verify Access from Python

### Install the client library

```bash
pip install google-cloud-bigquery
```

### Run a test query

```python
from google.cloud import bigquery

client = bigquery.Client(project="YOUR_PROJECT_ID")

query = """
SELECT publication_number, country_code, kind_code
FROM `patents-public-data.patents.publications`
WHERE publication_number = 'US-10000000-B2'
LIMIT 1
"""

results = client.query(query).result()

for row in results:
    print(f"Patent: {row.publication_number} ({row.country_code}, {row.kind_code})")
```

Expected output:
```
Patent: US-10000000-B2 (US, B2)
```

If you see this, you're all set.

---

## Available Datasets

The `patents-public-data` project contains far more than just the main publications table. Here's a complete inventory:

### Core Patent Data

| Table | Description | Use case |
|---|---|---|
| `patents.publications` | 166M+ worldwide patent publications with US full text (166M rows, 2.74 TB) | General patent search, claims text search, bibliographic lookups |
| `google_patents_research.publications` | Google's AI analysis: machine translations, extracted top terms | Translated abstracts, keyword extraction |

### USPTO Detailed Data (PatentsView)

The `patentsview` dataset contains **90+ individual tables** with granular USPTO data:

| Table | Description | Use case |
|---|---|---|
| `patentsview.claim` | Individual claims broken out separately | Claim-level search (much cheaper than scanning full-text claims) |
| `patentsview.patent` | Patent metadata | Basic lookups |
| `patentsview.assignee` | Assignee/owner data | Company patent portfolios |
| `patentsview.inventor` | Inventor data | Inventor searches |
| `patentsview.cpc_current` | Current CPC classifications | Technology area searches |
| `patentsview.figures` | Figure/drawing info | Drawing analysis |
| `patentsview.application` | Application data | Prosecution tracking |

### USPTO Office of Chief Economist Data

| Dataset | Description | Use case |
|---|---|---|
| `uspto_oce_assignment.*` | Patent assignment/ownership transfers | Tracking ownership changes |
| `uspto_oce_claims.*` | Claims analysis data | Claims research |
| `uspto_oce_litigation.*` | Patent litigation records | Litigation history |
| `uspto_oce_office_actions.*` | Office action data | Prosecution history |

### Other Datasets

| Dataset | Description | Use case |
|---|---|---|
| `uspto_peds.*` | Patent Examination Data System | Prosecution status |
| `uspto_ptab.*` | PTAB trial data (IPR, PGR, CBM) | Post-grant challenges |
| `usitc_investigations.*` | ITC Section 337 investigations | Import/trade disputes |
| `cpc.definitions` | CPC classification hierarchy | Understanding classification codes |
| `marec.publications` | MAREC corpus (EP, WO, JP, US) | European/international patents |

### Choosing the right table

For building a natural language search tool, the best table depends on the query type:

| Query type | Best table | Why |
|---|---|---|
| "Find patents where claim 1 mentions X" | `patentsview.claim` | Individual claims, can target specific claim numbers, cheaper to scan |
| "Who owns US patent 10,000,000 now?" | `uspto_oce_assignment` | Assignment/transfer history |
| "Has patent X been challenged at PTAB?" | `uspto_ptab.trials` | PTAB proceedings data |
| "Find all patents assigned to Atari" | `patents.publications` | Broad bibliographic search with assignee field |
| "Patents about machine learning in CPC G06N" | `patents.publications` | Classification + keyword search |
| "Search claims for 'blockchain' AND 'authentication'" | `patents.publications` | Full-text claims search (US only) |

---

## Understanding the Main Table Schema

The main table `patents-public-data.patents.publications` is a single flat table (not relational). Key columns:

| Column | Type | Description |
|---|---|---|
| `publication_number` | STRING | Unique patent identifier (e.g., `US-10000000-B2`) |
| `application_number` | STRING | Application number |
| `country_code` | STRING | Country code (e.g., `US`, `EP`, `WO`) |
| `kind_code` | STRING | Kind code (e.g., `B2` for granted patent) |
| `title_localized` | RECORD (REPEATED) | Patent title with `.text` and `.language` fields |
| `abstract_localized` | RECORD (REPEATED) | Patent abstract with `.text` and `.language` fields |
| `claims_localized` | RECORD (REPEATED) | Full claims text (**US patents only**) with `.text` and `.language` fields |
| `description_localized` | RECORD (REPEATED) | Full description/specification text (**US patents only**) |
| `publication_date` | INTEGER | Publication date as YYYYMMDD |
| `filing_date` | INTEGER | Filing date as YYYYMMDD |
| `grant_date` | INTEGER | Grant date as YYYYMMDD |
| `priority_date` | INTEGER | Priority date as YYYYMMDD |
| `inventor` | STRING (REPEATED) | Inventor names |
| `inventor_harmonized` | RECORD (REPEATED) | Harmonized inventor names with country |
| `assignee` | STRING (REPEATED) | Assignee/owner names |
| `assignee_harmonized` | RECORD (REPEATED) | Harmonized assignee names with country |
| `examiner` | RECORD (REPEATED) | Patent examiner info |
| `cpc` | RECORD (REPEATED) | CPC classification codes |
| `ipc` | RECORD (REPEATED) | IPC classification codes |
| `uspc` | RECORD (REPEATED) | US Patent Classification codes |
| `citation` | RECORD (REPEATED) | Patent and non-patent citations |
| `family_id` | STRING | Patent family identifier |
| `pct_number` | STRING | PCT application number |

> **Important:** Date fields are stored as INTEGER in YYYYMMDD format, not as SQL DATE types. For example, January 15, 2024 is stored as `20240115`.

> **Important:** Full-text fields (claims, description) are only available for US patents. Non-US patents have bibliographic data only (title, abstract, dates, inventors, assignees, classifications).

---

## Example Queries

### Search for terms in patent claims

```sql
SELECT
  publication_number,
  ANY_VALUE(title.text) AS title,
  ANY_VALUE(filing_date) AS filing_date,
  ANY_VALUE(grant_date) AS grant_date
FROM
  `patents-public-data.patents.publications`,
  UNNEST(title_localized) AS title
WHERE
  country_code = 'US'
  AND EXISTS (
    SELECT 1 FROM UNNEST(claims_localized) AS claim
    WHERE claim.text LIKE '%machine learning%'
    AND claim.text LIKE '%natural language%'
  )
  AND grant_date > 20200101
GROUP BY publication_number
ORDER BY grant_date DESC
LIMIT 20
```

### Find patents by assignee

```sql
SELECT
  publication_number,
  country_code,
  filing_date,
  grant_date,
  assignee
FROM
  `patents-public-data.patents.publications`
WHERE
  EXISTS (
    SELECT 1 FROM UNNEST(assignee) AS a
    WHERE UPPER(a) LIKE '%ATARI%'
  )
  AND country_code = 'US'
LIMIT 20
```

### Find individual claims containing specific terms (cheaper)

```sql
SELECT
  patent_id,
  sequence,
  text
FROM
  `patents-public-data.patentsview.claim`
WHERE
  text LIKE '%blockchain%'
  AND text LIKE '%authentication%'
LIMIT 20
```

---

## Cost Management

- **Free tier:** 1 TB of query processing per month (no credit card required)
- **Beyond free tier:** $6.25 per TB
- **Storage:** The public dataset is stored by Google at no cost to you

### Tips to minimize costs

- **Check estimated data size** before running a query (shown in the BigQuery query editor's green bar at the bottom)
- **Use `LIMIT` clauses** during development
- **Filter by `country_code`** early in your query to reduce data scanned
- **Use `patentsview.claim`** for claims searches instead of the full-text `claims_localized` field — it's much cheaper
- **Select only the columns you need** — BigQuery charges by data scanned, and the full table is 2.74 TB
- **Avoid `SELECT *`** on the publications table

---

## Useful Links

- [Google Patents Public Datasets on BigQuery Marketplace](https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data)
- [Dataset Documentation & Examples (GitHub)](https://github.com/google/patents-public-data)
- [Table Schema Reference](https://github.com/google/patents-public-data/blob/master/tables/dataset_Google%20Patents%20Public%20Datasets.md)
- [BigQuery Public Datasets Documentation](https://cloud.google.com/bigquery/public-data)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [Claim Text Extraction Example Notebook](https://github.com/google/patents-public-data/blob/master/examples/claim-text/claim_text_extraction.ipynb)
- [Google Cloud CLI Installation](https://cloud.google.com/sdk/docs/install)
- [Patents Public Data Mailing List](mailto:patents-public-data@googlegroups.com)

---

## License

Google Patents Public Data is provided by IFI CLAIMS Patent Services and Google, licensed under [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).
