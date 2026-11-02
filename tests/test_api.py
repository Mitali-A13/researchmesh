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
    }
    with patch("backend.routes.research.generate_research", return_value=fake_ok):
        r = c.post("/research", json={"topic": "AI in healthcare"}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["sources"] == [{"id": 1}]

    hist = c.get("/history", headers=h).json()["history"]
    assert len(hist) == 1
    saved = c.get(f"/history/{hist[0]['id']}", headers=h).json()["history"]
    assert (
        "## Sources" in saved["report"]
    )  # sources persist in history with no DB change

    # pipeline failure returns a clean message
    fake_fail = {"status": "failed", "error": "No search results found for this topic."}
    with patch("backend.routes.research.generate_research", return_value=fake_fail):
        r = c.post("/research", json={"topic": "zzzz qqqq"}, headers=h)
    assert (
        r.status_code == 500
        and r.json()["detail"] == "No search results found for this topic."
    )
