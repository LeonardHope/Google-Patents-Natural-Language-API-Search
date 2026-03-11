#!/usr/bin/env python3
"""
Setup verification script for Google Patent Search skill.

Checks:
1. google-cloud-bigquery is installed
2. gcloud CLI is available
3. Application Default Credentials are configured
4. GCP project ID is detectable
5. Can query the patents-public-data public dataset
"""

import os
import sys
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
VENV_DIR = SKILL_DIR / ".venv"
REQUIREMENTS = SKILL_DIR / "requirements.txt"


def check_mark(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def check_venv():
    """Ensure virtual environment exists and dependencies are installed."""
    if not VENV_DIR.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    pip = VENV_DIR / "bin" / "pip"
    if not pip.exists():
        pip = VENV_DIR / "Scripts" / "pip"  # Windows

    print("Installing dependencies...")
    subprocess.run([str(pip), "install", "-q", "-r", str(REQUIREMENTS)], check=True)
    print()


def check_gcloud() -> bool:
    """Check if gcloud CLI is installed."""
    try:
        result = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_adc() -> bool:
    """Check if Application Default Credentials exist."""
    adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    return adc_path.exists()


def check_project() -> str:
    """Get the configured GCP project ID."""
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
    return None


def check_bigquery(project_id: str) -> bool:
    """Test a simple BigQuery query against the public dataset."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project_id)
        sql = """
        SELECT publication_number
        FROM `patents-public-data.patents.publications`
        WHERE publication_number = 'US-10000000-B2'
        LIMIT 1
        """
        rows = list(client.query(sql).result())
        return len(rows) > 0
    except Exception as e:
        print(f"  BigQuery error: {e}")
        return False


def main():
    print("Google Patent Search — Setup Verification")
    print("=" * 50)

    # Step 1: Virtual environment
    print("\n1. Virtual environment & dependencies")
    check_venv()

    # Add venv to path for imports
    venv_site = VENV_DIR / "lib"
    if venv_site.exists():
        for d in venv_site.iterdir():
            sp = d / "site-packages"
            if sp.exists():
                sys.path.insert(0, str(sp))

    # Step 2: gcloud CLI
    print("2. Google Cloud CLI")
    gcloud_ok = check_gcloud()
    print(f"   gcloud CLI: {check_mark(gcloud_ok)}")
    if not gcloud_ok:
        print("   Install: brew install --cask google-cloud-sdk")
        print("   Or: https://cloud.google.com/sdk/docs/install")

    # Step 3: Application Default Credentials
    print("\n3. Application Default Credentials")
    adc_ok = check_adc()
    print(f"   ADC configured: {check_mark(adc_ok)}")
    if not adc_ok:
        print("   Run: gcloud auth application-default login")

    # Step 4: Project ID
    print("\n4. GCP Project ID")
    project_id = check_project()
    print(f"   Project: {project_id or 'NOT SET'}")
    if not project_id:
        print("   Run: gcloud config set project YOUR_PROJECT_ID")

    # Step 5: BigQuery connectivity
    print("\n5. BigQuery connectivity")
    if project_id and adc_ok:
        bq_ok = check_bigquery(project_id)
        print(f"   Can query public patents data: {check_mark(bq_ok)}")
    else:
        bq_ok = False
        print("   Skipped (need ADC and project ID first)")

    # Summary
    print("\n" + "=" * 50)
    all_ok = gcloud_ok and adc_ok and project_id and bq_ok
    if all_ok:
        print("All checks passed. Ready to search patents!")
        return 0
    else:
        print("[SETUP_REQUIRED] Fix the issues above and re-run this script.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
