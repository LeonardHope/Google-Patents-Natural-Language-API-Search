"""
BigQuery Patent Search Client - Auth, cost estimation, and safety guardrails.

Provides a unified client for querying Google Patents Public Datasets on BigQuery.
Handles authentication (Application Default Credentials), dry-run cost estimation,
and SQL safety validation.

Authentication:
    Uses Application Default Credentials via `gcloud auth application-default login`.
    Project ID is auto-detected from gcloud config or GCP_PROJECT_ID env var.

Cost Protection (4 layers):
    1. Prevention: Functions select only needed columns, always include LIMIT
    2. Detection: Every query dry-runs first to show estimated scan size
    3. Defense: SQL validation rejects dangerous patterns (SELECT *, missing LIMIT)
    4. Avoidance: Decision matrix routes to cheaper tables first
"""

import os
import re
import sys
import subprocess
import logging
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    from google.cloud import bigquery
except ImportError:
    print("Error: 'google-cloud-bigquery' is required. Install with: pip install -r requirements.txt")
    sys.exit(1)

logger = logging.getLogger("bigquery_client")

# Default max bytes: 5GB. Override with BQ_MAX_BYTES env var.
# The free tier allows 1 TB/month. Most patentsview queries scan 500MB-1GB;
# claims searches can scan up to 38 GB; publications queries can scan 50-130 GB.
DEFAULT_MAX_BYTES = 5_000_000_000

# 1GB: warn user about cost (uses decimal units to match BigQuery billing)
WARN_THRESHOLD = 1_000_000_000

# Public dataset project
PUBLIC_PROJECT = "patents-public-data"

# Aggregate functions that produce bounded result sets without LIMIT
_AGGREGATE_FUNCTIONS = re.compile(
    r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(', re.IGNORECASE
)


class BigQueryError(Exception):
    """Raised when a BigQuery operation fails."""

    def __init__(self, message: str, query: str = None, estimated_bytes: int = None):
        super().__init__(message)
        self.query = query
        self.estimated_bytes = estimated_bytes


def _get_project_id() -> str:
    """Detect GCP project ID from env var or gcloud config."""
    project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        return project
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    raise BigQueryError(
        "[SETUP_REQUIRED] Could not detect GCP project ID.\n"
        "Run: gcloud config set project YOUR_PROJECT_ID\n"
        "Or set GCP_PROJECT_ID in your .env file."
    )


def _get_max_bytes() -> int:
    """Get the maximum allowed bytes per query."""
    env_val = os.environ.get("BQ_MAX_BYTES")
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass
    return DEFAULT_MAX_BYTES


def _format_bytes(num_bytes: int) -> str:
    """Format byte count to human-readable string (decimal units to match BigQuery billing)."""
    if num_bytes < 1_000:
        return f"{num_bytes} B"
    elif num_bytes < 1_000_000:
        return f"{num_bytes / 1_000:.1f} KB"
    elif num_bytes < 1_000_000_000:
        return f"{num_bytes / 1_000_000:.1f} MB"
    else:
        return f"{num_bytes / 1_000_000_000:.2f} GB"


def validate_sql(sql: str) -> list:
    """Validate SQL for safety. Returns list of issues (empty = OK).

    Checks for:
    - SELECT * (scans entire row, very expensive on publications table)
    - Missing LIMIT clause (unless query uses aggregate functions without GROUP BY)
    - Missing WHERE clause on expensive tables
    """
    issues = []
    sql_upper = sql.upper().strip()

    # Check for SELECT *
    if re.search(r'\bSELECT\s+\*', sql_upper):
        issues.append("SELECT * is not allowed — specify only the columns you need to reduce cost.")

    # Check for LIMIT — skip if query uses aggregates without GROUP BY
    # (e.g., SELECT COUNT(*) FROM ... WHERE ... returns exactly 1 row)
    has_aggregate = bool(_AGGREGATE_FUNCTIONS.search(sql))
    has_group_by = "GROUP BY" in sql_upper
    if "LIMIT" not in sql_upper:
        if not has_aggregate or has_group_by:
            issues.append("Query must include a LIMIT clause to cap result size.")

    # Check for WHERE on expensive tables — match in FROM/JOIN clauses only
    expensive_tables = ["patents.publications", "google_patents_research.publications"]
    for table in expensive_tables:
        # Match the table name preceded by FROM or JOIN (with optional backticks/project prefix)
        pattern = r'(?:FROM|JOIN)\s+`?[\w-]*\.?' + re.escape(table) + r'`?'
        if re.search(pattern, sql, re.IGNORECASE):
            if "WHERE" not in sql_upper:
                issues.append(f"Queries against {table} must include a WHERE clause to limit data scanned.")

    return issues


class BigQueryClient:
    """Client for querying Google Patents Public Datasets on BigQuery.

    Provides dry-run cost estimation and safety guardrails around every query.
    """

    def __init__(self, project_id: str = None):
        self.project_id = project_id or _get_project_id()
        self.client = bigquery.Client(project=self.project_id)
        self.max_bytes = _get_max_bytes()

    def dry_run(self, sql: str, query_params: list = None) -> int:
        """Estimate bytes that will be scanned by a query.

        Args:
            sql: The SQL query to estimate.
            query_params: Optional list of bigquery.ScalarQueryParameter for parameterized queries.

        Returns:
            Estimated bytes to be processed.

        Raises:
            BigQueryError: If the query is invalid.
        """
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        if query_params:
            job_config.query_parameters = query_params
        try:
            job = self.client.query(sql, job_config=job_config)
            return job.total_bytes_processed
        except Exception as e:
            raise BigQueryError(f"Dry run failed: {e}", query=sql)

    def estimate_cost(self, sql: str, query_params: list = None) -> dict:
        """Estimate the cost of a query without executing it.

        Args:
            sql: The SQL query to estimate.
            query_params: Optional list of bigquery.ScalarQueryParameter for parameterized queries.

        Returns:
            Dict with estimated_bytes, formatted size, pct_of_free_tier,
            exceeds_threshold, and a human-readable summary.
        """
        estimated_bytes = self.dry_run(sql, query_params=query_params)
        formatted = _format_bytes(estimated_bytes)
        free_tier_bytes = 1_000_000_000_000  # 1 TB
        pct = (estimated_bytes / free_tier_bytes) * 100

        return {
            "estimated_bytes": estimated_bytes,
            "formatted": formatted,
            "pct_of_free_tier": round(pct, 1),
            "exceeds_threshold": estimated_bytes > self.max_bytes,
            "summary": (
                f"This query will scan {formatted} "
                f"({pct:.1f}% of the 1 TB/month free tier)."
            ),
        }

    def run_query(self, sql: str, query_params: list = None,
                  skip_validation: bool = False,
                  force: bool = False, max_bytes_override: int = None) -> list:
        """Run a SQL query with safety checks.

        Performs SQL validation, dry-run cost estimation, and then executes.

        Args:
            sql: The SQL query to execute.
            query_params: Optional list of bigquery.ScalarQueryParameter for parameterized queries.
            skip_validation: Skip SQL pattern validation (still does dry-run).
            force: If True, execute even if the query exceeds the cost threshold.
                   Use this when the user has explicitly approved the cost.
            max_bytes_override: Temporarily override max_bytes for this query only.

        Returns:
            List of result rows as dicts.

        Raises:
            BigQueryError: If validation fails or query is too expensive
                           (unless force=True).
        """
        effective_max = max_bytes_override if max_bytes_override is not None else self.max_bytes

        # Step 1: SQL pattern validation
        if not skip_validation:
            issues = validate_sql(sql)
            if issues:
                raise BigQueryError(
                    "Query rejected by safety check:\n" + "\n".join(f"  - {i}" for i in issues),
                    query=sql
                )

        # Step 2: Dry-run cost estimation
        estimated_bytes = self.dry_run(sql, query_params=query_params)
        formatted = _format_bytes(estimated_bytes)
        pct = (estimated_bytes / 1_000_000_000_000) * 100

        if estimated_bytes > effective_max and not force:
            raise BigQueryError(
                f"Query would scan {formatted} ({pct:.1f}% of the 1 TB/month free tier).\n"
                f"Threshold: {_format_bytes(effective_max)}.\n"
                f"To proceed, re-run with force=True after user approval.",
                query=sql,
                estimated_bytes=estimated_bytes
            )

        if estimated_bytes > WARN_THRESHOLD:
            logger.warning(
                f"Query will scan {formatted} "
                f"[Cost: {pct:.1f}% of 1 TB/month free tier]"
            )
        else:
            logger.info(f"Query will scan {formatted}")

        # Step 3: Execute
        try:
            job_config = bigquery.QueryJobConfig()
            if query_params:
                job_config.query_parameters = query_params
            job = self.client.query(sql, job_config=job_config)
            results = job.result()
            rows = [dict(row) for row in results]
            return rows
        except Exception as e:
            raise BigQueryError(f"Query execution failed: {e}", query=sql)

    def check_connection(self) -> dict:
        """Verify BigQuery connectivity and auth.

        Returns:
            Dict with connection status info.
        """
        try:
            sql = f"""
            SELECT title
            FROM `{PUBLIC_PROJECT}.patentsview.patent`
            WHERE id = '10000000'
            LIMIT 1
            """
            rows = self.run_query(
                sql, skip_validation=True,
                max_bytes_override=10_000_000_000
            )
            return {
                "status": "OK",
                "project_id": self.project_id,
                "can_query_public_data": True,
                "test_result": rows,
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "project_id": self.project_id,
                "error": str(e),
            }


# Module-level singleton
_client = None


def get_client() -> BigQueryClient:
    """Get or create the BigQuery client singleton."""
    global _client
    if _client is None:
        _client = BigQueryClient()
    return _client


if __name__ == "__main__":
    client = get_client()
    result = client.check_connection()
    print(f"Project ID: {result['project_id']}")
    print(f"Status: {result['status']}")
    if result["status"] == "ERROR":
        print(f"Error: {result['error']}")
        print("\n[SETUP_REQUIRED] Run: python3 get_started.py")
        sys.exit(1)
    else:
        print("BigQuery connection verified.")
