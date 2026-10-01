"""Phase 6 — Job Search Copilot.

Tools for job hunting workflow:
  - Open job sites in correct Chrome profile
  - Track application status (stored in SQLite)
  - Interview prep mode (opens notes + LeetCode + calendar)
  - Resume quick-open
  - Company research (Google search + LinkedIn)
"""
from __future__ import annotations
import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from database import db
from shared.schemas import ActionResult

JOB_SITES = {
    "jobright": "https://jobright.ai",
    "glassdoor": "https://www.glassdoor.com/Job/index.htm",
    "linkedin jobs": "https://www.linkedin.com/jobs",
    "wellfound": "https://wellfound.com/jobs",
    "levels fyi": "https://www.levels.fyi/jobs",
}

DEFAULT_CHROME_PROFILE = "Profile 4"  # roszhan.2684@gmail.com


# ─── Application tracker ──────────────────────────────────────────────────────

def log_application(company: str, role: str, url: str = "", status: str = "applied") -> str:
    """Log a job application to SQLite."""
    app_id = str(uuid.uuid4())
    db.execute(
        """INSERT OR IGNORE INTO job_applications(id, company, role, url, status, applied_at)
           VALUES(?,?,?,?,?,datetime('now'))""",
        (app_id, company, role, url, status),
    )
    return app_id


def get_applications(status: str | None = None) -> list[dict]:
    q = "SELECT * FROM job_applications ORDER BY applied_at DESC"
    params: tuple = ()
    if status:
        q = "SELECT * FROM job_applications WHERE status=? ORDER BY applied_at DESC"
        params = (status,)
    try:
        rows = db.fetchall(q, params)
        return [dict(r) for r in rows]
    except Exception:
        return []


def update_application_status(company: str, status: str) -> bool:
    try:
        db.execute(
            "UPDATE job_applications SET status=?, updated_at=datetime('now') WHERE LOWER(company)=LOWER(?)",
            (status, company),
        )
        return True
    except Exception:
        return False


# ─── Actions ──────────────────────────────────────────────────────────────────

def open_job_sites() -> ActionResult:
    """Open all job sites in Chrome with job profile."""
    from modules.automation.chrome_profiles import open_url_groups_in_chrome
    urls = list(JOB_SITES.values())[:3]  # top 3
    opened = open_url_groups_in_chrome({1: urls}, profile_identifier="roszhan.2684@gmail.com")
    return ActionResult(success=opened > 0, output=f"Opened {opened} job sites, Boss.")


def research_company(company: str) -> ActionResult:
    """Open Google + LinkedIn search for a company."""
    import urllib.parse
    q = urllib.parse.quote_plus(company)
    urls = [
        f"https://www.google.com/search?q={q}+software+engineer+jobs",
        f"https://www.linkedin.com/search/results/companies/?keywords={q}",
    ]
    for url in urls:
        subprocess.run(["open", url], capture_output=True)
    return ActionResult(success=True, output=f"Researching {company}, Boss.")


def open_resume() -> ActionResult:
    """Open the resume file directly."""
    from modules.automation.file_search import resolve_file
    path = resolve_file("resume", "pdf")
    if path and Path(path).exists():
        subprocess.run(["open", path], capture_output=True)
        return ActionResult(success=True, output=path)
    return ActionResult(success=False, error="Resume not found. Say 'open my resume' to set the alias.")


def interview_prep() -> ActionResult:
    """Full interview prep mode."""
    steps = [
        ("open_app", "Notes"),
        ("open_url", "https://leetcode.com"),
        ("open_url", "https://www.levels.fyi"),
    ]
    for action, target in steps:
        if action == "open_app":
            subprocess.run(["open", "-a", target], capture_output=True)
        else:
            subprocess.run(["open", target], capture_output=True)
    return ActionResult(success=True, output="Interview prep mode activated, Boss.")
