# Key Table Schemas

## patents.publications (166M rows, 2.74 TB)

The main table. Only source for full-text claims/descriptions and international patents.

| Column | Type | Notes |
|---|---|---|
| `publication_number` | STRING | e.g., `US-10000000-B2` |
| `application_number` | STRING | |
| `country_code` | STRING | `US`, `EP`, `WO`, `JP`, `CN`, `KR`, etc. |
| `kind_code` | STRING | `B2` (granted), `A1` (published app), etc. |
| `title_localized` | RECORD(REPEATED) | `.text`, `.language` |
| `abstract_localized` | RECORD(REPEATED) | `.text`, `.language` |
| `claims_localized` | RECORD(REPEATED) | `.text`, `.language` — **US only** |
| `description_localized` | RECORD(REPEATED) | `.text`, `.language` — **US only** |
| `publication_date` | INTEGER | YYYYMMDD format |
| `filing_date` | INTEGER | YYYYMMDD format |
| `grant_date` | INTEGER | YYYYMMDD format |
| `priority_date` | INTEGER | YYYYMMDD format |
| `inventor` | STRING(REPEATED) | Raw inventor names |
| `inventor_harmonized` | RECORD(REPEATED) | `.name`, `.country_code` |
| `assignee` | STRING(REPEATED) | Raw assignee names |
| `assignee_harmonized` | RECORD(REPEATED) | `.name`, `.country_code` |
| `cpc` | RECORD(REPEATED) | `.code`, `.inventive`, `.first` |
| `ipc` | RECORD(REPEATED) | `.code` |
| `citation` | RECORD(REPEATED) | `.publication_number`, `.type`, `.category` |
| `family_id` | STRING | Patent family identifier |
| `pct_number` | STRING | PCT application number |

## patentsview.claim

| Column | Type | Notes |
|---|---|---|
| `uuid` | STRING | Unique claim ID |
| `patent_id` | STRING | e.g., `10000000` |
| `text` | STRING | Full claim text |
| `dependent` | STRING | Dependent claim ref (NULL = independent) |
| `sequence` | STRING | Claim sequence/number |
| `exemplary` | STRING | |

## patentsview.patent

| Column | Type | Notes |
|---|---|---|
| `id` | STRING | Patent ID (e.g., `10000000`) |
| `number` | STRING | Patent number |
| `title` | STRING | Patent title |
| `abstract` | STRING | Patent abstract |
| `date` | STRING | Grant date |
| `type` | STRING | utility, design, plant, reissue |
| `kind` | STRING | Kind code |
| `country` | STRING | Country code |
| `num_claims` | INTEGER | Number of claims |

## patentsview.assignee (join via patent_assignee)

| Column | Type | Notes |
|---|---|---|
| `id` | STRING | Assignee ID |
| `organization` | STRING | Organization name |
| `type` | FLOAT | Assignee type |
| `name_first` | STRING | First name (individuals) |
| `name_last` | STRING | Last name (individuals) |

## patentsview.patent_assignee (junction table)

| Column | Type | Notes |
|---|---|---|
| `patent_id` | STRING | Links to patent.id |
| `assignee_id` | STRING | Links to assignee.id |
| `location_id` | STRING | |

## patentsview.inventor (join via patent_inventor)

| Column | Type | Notes |
|---|---|---|
| `id` | STRING | Inventor ID |
| `name_first` | STRING | First name |
| `name_last` | STRING | Last name |

## patentsview.patent_inventor (junction table)

| Column | Type | Notes |
|---|---|---|
| `patent_id` | STRING | Links to patent.id |
| `inventor_id` | STRING | Links to inventor.id |

## google_patents_research.publications

| Column | Type | Notes |
|---|---|---|
| `publication_number` | STRING | |
| `top_terms` | RECORD(REPEATED) | `.text`, `.score` |
| `url` | STRING | Google Patents URL |

## Key USPTO BigQuery Tables

| Table | Key columns |
|---|---|
| `uspto_oce_assignment.assignment` | `rf_id`, `convey_text`, `record_dt`, `reel_no`, `frame_no` |
| `uspto_oce_litigation.litigation` | `case_id`, `patent_id`, `plaintiff`, `defendant`, `filed_date` |
| `uspto_ptab.trials` | `trial_number`, `patent_number`, `type`, `status`, `petitioner_party_name` |
| `uspto_peds.applications` | `appl_id`, `patent_number`, `app_status`, `patent_title` |
| `usitc_investigations.investigations_337` | `investigation_number`, `patent_id`, `complainant`, `respondent` |
