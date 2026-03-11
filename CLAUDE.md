# Google Patent Search — Developer Guidance

## Architecture

This skill queries Google Patents Public Datasets on BigQuery (`patents-public-data` project).
All queries go through `bigquery_client.py` which enforces:
1. SQL validation (no SELECT *, must have LIMIT and WHERE on expensive tables)
2. Dry-run cost estimation before every query
3. Hard cost cap (default 5GB, configurable via BQ_MAX_BYTES)

## Key Patterns

### BigQuery table references
All tables are in `patents-public-data`. Use backtick-quoted full paths:
```sql
`patents-public-data.patents.publications`
`patents-public-data.patentsview.claim`
```

### UNNEST for nested/repeated fields
The publications table uses RECORD(REPEATED) fields. Always UNNEST:
```sql
SELECT publication_number, title.text
FROM `patents-public-data.patents.publications`,
  UNNEST(title_localized) AS title
WHERE title.language = 'en'
```

### Date fields are integers
Dates are YYYYMMDD integers (not DATE type): `grant_date > 20200101`

### Cost-conscious queries
- Always select specific columns, never `SELECT *`
- Always include LIMIT
- Filter by country_code early to reduce scan
- Prefer patentsview.claim over claims_localized in publications
- Use dry-run to check cost before executing
- Queries > 5GB are blocked by default — use `force=True` only after user approval
- Use `client.estimate_cost(sql)` to check cost without executing

## Adding New Query Functions

1. Add function to the appropriate search module
2. Follow the pattern: accept parameters, build SQL with safety constraints, call `client.run_query(sql)`
3. Always include LIMIT and WHERE clauses
4. Add CLI entry point in the `if __name__ == "__main__"` block
5. Add a formatter case in `format_results.py` if needed
6. Update the decision matrix in SKILL.md

## Testing

Run individual modules from the command line:
```bash
cd scripts/
python3 patentsview_search.py claims blockchain --limit 5
python3 publications_search.py assignee "Google" --country US --limit 5
python3 bigquery_client.py  # connectivity check
```
