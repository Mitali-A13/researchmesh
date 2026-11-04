import os, sys, tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(
    MISTRAL_API_KEY="d",
    TAVILY_API_KEY="d",
    SECRET_KEY="test-secret",
    DATABASE_URL=f"sqlite:///{_db}",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.db.database import SessionLocal
from backend.db.models import ReportCheck, ReportIteration

c = TestClient(app)


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
    with patch("backend.routes.research.generate_research", return_value=fake_ok):
        r = c.post("/research", json={"topic": "AI in healthcare"}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["sources"] == [{"id": 1}]

    hist = c.get("/history", headers=h).json()["history"]
    assert len(hist) == 1
    saved = c.get(f"/history/{hist[0]['id']}", headers=h).json()["history"]
    assert "## Sources" in saved["report"]  # sources persist inside the saved report

    # the critic's score for every round is stored in its own table
    with SessionLocal() as db:
        rows = db.query(ReportIteration).order_by(ReportIteration.round).all()
        assert [(row.round, row.score) for row in rows] == [(1, 5), (2, 8)]

        # the citation-check numbers are stored too
        check = db.query(ReportCheck).one()
        assert (check.claims_total, check.checked, check.supported) == (12, 10, 8)
        assert (check.partial, check.unsupported, check.uncited_sentences) == (1, 1, 3)
        assert (
            check.invalid_citations,
            check.unused_sources,
            check.figures_not_found,
        ) == (1, 2, 2)
        assert check.llm_used is True

    # deleting the report deletes its scores and its check too
    assert c.delete(f"/history/{hist[0]['id']}", headers=h).status_code == 200
    with SessionLocal() as db:
        assert db.query(ReportIteration).count() == 0
        assert db.query(ReportCheck).count() == 0

    # a report without verification data still saves fine
    fake_no_check = {**fake_ok, "verification": None}
    with patch("backend.routes.research.generate_research", return_value=fake_no_check):
        assert (
            c.post("/research", json={"topic": "no check topic"}, headers=h).status_code
            == 200
        )
    with SessionLocal() as db:
        assert db.query(ReportCheck).count() == 0

    # pipeline failure returns a clean message
    fake_fail = {"status": "failed", "error": "No search results found for this topic."}
    with patch("backend.routes.research.generate_research", return_value=fake_fail):
        r = c.post("/research", json={"topic": "zzzz qqqq"}, headers=h)
    assert (
        r.status_code == 500
        and r.json()["detail"] == "No search results found for this topic."
    )
