import os, sys, tempfile, time

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(
    MISTRAL_API_KEY="d",
    TAVILY_API_KEY="d",
    SECRET_KEY="test-secret-key-for-pytest-1234",
    DATABASE_URL=f"sqlite:///{_db}",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.db.database import SessionLocal
from backend.db.models import ReportCheck, ReportIteration

c = TestClient(app)


def wait_for_job(job_id, headers, timeout=10):
    """Poll the job like the frontend does, until it is completed or failed."""
    end = time.time() + timeout
    while time.time() < end:
        body = c.get(f"/research/jobs/{job_id}", headers=headers).json()
        if body["job"]["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("the job did not finish in time")


def run_research(topic, fake, headers):
    """Start a report (the pipeline is replaced by `fake`) and wait for it."""
    with patch("backend.services.jobs.generate_research", return_value=fake):
        r = c.post("/research", json={"topic": topic}, headers=headers)
        assert r.status_code == 202, r.text
        return r, wait_for_job(r.json()["job"]["id"], headers)


def test_flow():
    assert c.get("/").json()["success"]
    assert (
        c.post(
            "/signup",
            json={"name": "Mitali", "email": "m@x.com", "password": "secret1"},
        ).status_code
        == 201
    )
    tok = c.post("/login", json={"email": "m@x.com", "password": "secret1"}).json()[
        "access_token"
    ]
    h = {"Authorization": f"Bearer {tok}"}

    # no token -> blocked
    assert c.post("/research", json={"topic": "abc def"}).status_code in (401, 403)

    fake_ok = {
        "status": "success",
        "report": "Body [1]\n\n## Sources\n- **[1]** [A](https://a.com)",
        "feedback": "Score: 8/10",
        "sources": [{"id": 1}],
        "warnings": [],
        "error": None,
        "scores": [5, 8],
        "revisions": 1,
        "verification": {
            "claims_total": 12,
            "uncited_sentences": 3,
            "invalid_citations": [7],
            "unused_sources": [4, 5],
            "figures_not_found": 2,
            "llm_used": True,
            "checked": 10,
            "supported": 8,
            "partial": 1,
            "unsupported": 1,
            "support_rate": 0.8,
            "flagged": [],
            "notes": [],
        },
    }
    r, body = run_research("AI in healthcare", fake_ok, h)
    assert body["job"]["status"] == "completed" and body["data"]["sources"] == [
        {"id": 1}
    ]

    hist = c.get("/history", headers=h).json()["history"]
    assert len(hist) == 1
    assert body["job"]["history_id"] == hist[0]["id"]
    history_id = hist[0]["id"]
    saved = c.get(f"/history/{history_id}", headers=h).json()["history"]
    assert "## Sources" in saved["report"]  # sources persist inside the saved report

    # the critic's score for every round is stored in its own table
    with SessionLocal() as db:
        rows = (
            db.query(ReportIteration)
            .filter(ReportIteration.history_id == history_id)
            .order_by(ReportIteration.round)
            .all()
        )
        assert [(row.round, row.score) for row in rows] == [(1, 5), (2, 8)]

        # the citation-check numbers are stored too
        check = db.query(ReportCheck).filter(ReportCheck.history_id == history_id).one()
        assert (check.claims_total, check.checked, check.supported) == (12, 10, 8)
        assert (check.partial, check.unsupported, check.uncited_sentences) == (1, 1, 3)
        assert (
            check.invalid_citations,
            check.unused_sources,
            check.figures_not_found,
        ) == (1, 2, 2)
        assert check.llm_used is True

    # deleting the report deletes its scores and its check too
    assert c.delete(f"/history/{history_id}", headers=h).status_code == 200
    with SessionLocal() as db:
        assert db.query(ReportIteration).filter_by(history_id=history_id).count() == 0
        assert db.query(ReportCheck).filter_by(history_id=history_id).count() == 0

    # a report without verification data still saves fine
    fake_no_check = {**fake_ok, "verification": None}
    _, body = run_research("no check topic", fake_no_check, h)
    assert body["job"]["status"] == "completed"
    with SessionLocal() as db:
        assert (
            db.query(ReportCheck)
            .filter_by(history_id=body["job"]["history_id"])
            .count()
            == 0
        )

    # pipeline failure ends as a failed job with a clean message
    fake_fail = {"status": "failed", "error": "No search results found for this topic."}
    _, body = run_research("zzzz qqqq", fake_fail, h)
    assert body["job"]["status"] == "failed"
    assert body["job"]["error"] == "No search results found for this topic."
    assert "data" not in body
