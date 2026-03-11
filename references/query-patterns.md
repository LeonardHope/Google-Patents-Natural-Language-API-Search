# Tested Query Patterns

## Claims Search (patentsview.claim — cheap)

```sql
SELECT patent_id, sequence, text
FROM `patents-public-data.patentsview.claim`
WHERE text LIKE '%blockchain%'
  AND text LIKE '%authentication%'
LIMIT 20
```

## Claims Search (publications — expensive, but supports more filters)

```sql
SELECT
  publication_number,
  ANY_VALUE(title.text) AS title,
  ANY_VALUE(filing_date) AS filing_date,
  ANY_VALUE(grant_date) AS grant_date
FROM `patents-public-data.patents.publications`,
  UNNEST(title_localized) AS title
WHERE
  EXISTS (
    SELECT 1 FROM UNNEST(claims_localized) AS claim
    WHERE claim.text LIKE '%machine learning%'
      AND claim.text LIKE '%natural language%'
  )
  AND title.language = 'en'
  AND country_code = 'US'
  AND grant_date > 20200101
GROUP BY publication_number
ORDER BY grant_date DESC
LIMIT 20
```

## Assignee Search (publications — international)

```sql
SELECT
  publication_number, country_code,
  ANY_VALUE(a.name) AS assignee_name,
  ANY_VALUE(title.text) AS title,
  ANY_VALUE(grant_date) AS grant_date
FROM `patents-public-data.patents.publications`,
  UNNEST(assignee_harmonized) AS a,
  UNNEST(title_localized) AS title
WHERE UPPER(a.name) LIKE '%ATARI%'
  AND title.language = 'en'
GROUP BY publication_number, country_code
ORDER BY grant_date DESC
LIMIT 20
```

## Keyword in Title/Abstract

```sql
SELECT
  publication_number, country_code,
  ANY_VALUE(title.text) AS title,
  ANY_VALUE(SUBSTR(abstract.text, 1, 300)) AS abstract_snippet,
  ANY_VALUE(grant_date) AS grant_date
FROM `patents-public-data.patents.publications`,
  UNNEST(title_localized) AS title,
  UNNEST(abstract_localized) AS abstract
WHERE title.language = 'en'
  AND abstract.language = 'en'
  AND (LOWER(title.text) LIKE '%wireless charging%'
       OR LOWER(abstract.text) LIKE '%wireless charging%')
GROUP BY publication_number, country_code
ORDER BY grant_date DESC
LIMIT 25
```

## Top Assignees by CPC Code

```sql
SELECT
  a.name AS assignee_name,
  COUNT(DISTINCT publication_number) AS patent_count
FROM `patents-public-data.patents.publications`,
  UNNEST(assignee_harmonized) AS a,
  UNNEST(cpc) AS c
WHERE c.code LIKE 'G06N%'
  AND country_code = 'US'
  AND a.name != ''
GROUP BY assignee_name
ORDER BY patent_count DESC
LIMIT 20
```

## Filing Trends by Year

```sql
SELECT
  CAST(FLOOR(filing_date / 10000) AS INT64) AS filing_year,
  COUNT(DISTINCT publication_number) AS patent_count
FROM `patents-public-data.patents.publications`,
  UNNEST(cpc) AS c
WHERE c.code LIKE 'H04L%'
  AND country_code = 'US'
  AND filing_date > 19900101
GROUP BY filing_year
ORDER BY filing_year
LIMIT 50
```

## International Patents

```sql
SELECT
  publication_number, country_code, kind_code,
  ANY_VALUE(title.text) AS title,
  ANY_VALUE(grant_date) AS grant_date
FROM `patents-public-data.patents.publications`,
  UNNEST(title_localized) AS title
WHERE country_code = 'EP'
  AND title.language = 'en'
  AND LOWER(title.text) LIKE '%wireless charging%'
GROUP BY publication_number, country_code, kind_code
ORDER BY grant_date DESC
LIMIT 25
```

## Single Patent Detail

```sql
SELECT
  publication_number, country_code, kind_code,
  application_number, filing_date, grant_date,
  priority_date, family_id, inventor, assignee, pct_number
FROM `patents-public-data.patents.publications`
WHERE publication_number = 'US-10000000-B2'
LIMIT 1
```
