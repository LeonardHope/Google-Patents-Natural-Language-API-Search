# Cost Reference

## BigQuery Pricing

- **Free tier**: 1 TB/month of query processing (no credit card required)
- **Beyond free tier**: $6.25 per TB (on-demand pricing)
- **Storage**: Public dataset storage is free (hosted by Google)

## Table Sizes

| Table | Approximate Size | Row Count |
|---|---|---|
| `patents.publications` | 2.74 TB | 166M+ |
| `google_patents_research.publications` | ~200 GB | ~120M |
| `patentsview.claim` | ~5 GB | ~100M |
| `patentsview.patent` | ~2 GB | ~8M |
| `patentsview.assignee` | ~500 MB | ~8M |
| `patentsview.inventor` | ~1 GB | ~18M |
| `patentsview.cpc_current` | ~1 GB | ~30M |
| `uspto_oce_assignment.assignments` | ~2 GB | ~10M |
| `uspto_ptab.trials` | ~100 MB | ~20K |
| `uspto_peds.applications` | ~5 GB | ~15M |

## Estimated Cost Per Query Type

| Query Type | Table | Est. Scan | Monthly Budget Impact |
|---|---|---|---|
| Claims search (patentsview) | `patentsview.claim` | ~5 GB | 200 queries = 1 TB |
| Claims search (full-text) | `patents.publications` | ~131 GB | 7-8 queries = 1 TB |
| Assignee search (patentsview) | `patentsview.assignee` | ~500 MB | 2000 queries = 1 TB |
| Assignee search (publications) | `patents.publications` | ~50 GB | 20 queries = 1 TB |
| Keyword title/abstract | `patents.publications` | ~30 GB | 33 queries = 1 TB |
| Similar patents | `google_patents_research` | ~10 GB | 100 queries = 1 TB |
| Filing trends | `patents.publications` | ~20-50 GB | 20-50 queries = 1 TB |
| Single patent lookup | `patents.publications` | ~1 MB | Negligible |
| PTAB search | `uspto_ptab.trials` | ~100 MB | Negligible |
| Assignment search | `uspto_oce_assignment` | ~2 GB | 500 queries = 1 TB |

## Cost Tips

1. **Always use patentsview tables when possible** — they're 100-500x cheaper than publications
2. **Filter by country_code** — cuts scan size proportional to country's share of data
3. **Use LIMIT** — doesn't reduce scan cost but prevents huge result transfers
4. **Select specific columns** — BigQuery is columnar; fewer columns = less data scanned
5. **Avoid scanning claims_localized/description_localized** — these are the largest columns
6. **Queries are cached** — identical queries within 24 hours are free

## Guardrail Thresholds (configurable via BQ_MAX_BYTES)

| Scan Size | Behavior |
|---|---|
| < 1 GB | Silent — runs immediately |
| 1 GB - 5 GB | Warning printed to stderr |
| > 5 GB | **Refused** — suggests narrower filters |

Override: Set `BQ_MAX_BYTES=10000000000` in `.env` to allow up to 10 GB.

## Actual Measured Costs (BigQuery patentsview tables)

| Query | Measured Scan |
|---|---|
| `patentsview.claim` full text search | ~38 GB |
| `patentsview.patent` single lookup | ~611 MB |
| `patentsview.patent_assignee` + joins | ~1 GB |
| `patents.publications` single lookup by pub_number | ~2.6 GB |

Note: BigQuery patentsview tables are larger than the PatentsView REST API data
because BigQuery scans entire columns regardless of WHERE filters.
