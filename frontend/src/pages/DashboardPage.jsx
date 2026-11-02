import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";

import api from "../services/api";
import { removeToken } from "../services/auth";

import Header from "../components/Header";
import HistorySidebar from "../components/HistorySidebar";
import Loader from "../components/Loader";
import ReportCard from "../components/ReportCard";

export default function DashboardPage() {
  const navigate = useNavigate();

  const [user, setUser] = useState(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [topic, setTopic] = useState("");
  const [report, setReport] = useState("");
  const [feedback, setFeedback] = useState("");
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    fetchUser();
    fetchHistory();
  }, []);

  async function fetchUser() {
    try {
      const res = await api.get("/me");
      setUser(res.data.user);
    } catch {
      removeToken();
      navigate("/");
    } finally {
      setLoadingUser(false);
    }
  }

  async function fetchHistory() {
    const res = await api.get("/history");
    setHistory(res.data.history);
  }

  async function handleResearch() {
    if (!topic.trim()) return;

    try {
      setLoadingReport(true);
      setError("");
      setReport("");
      setFeedback("");

      const res = await api.post("/research", { topic });

      setReport(res.data.data.report);
      setFeedback(res.data.data.feedback);
      fetchHistory();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to generate report");
    } finally {
      setLoadingReport(false);
    }
  }

  async function openHistory(id) {
    const res = await api.get(`/history/${id}`);
    setReport(res.data.history.report);
    setFeedback(res.data.history.feedback);
  }

  async function deleteHistory(id) {
    await api.delete(`/history/${id}`);
    fetchHistory();
  }

  function logout() {
    removeToken();
    navigate("/");
  }

  if (loadingUser) {
    return <div style={{ padding: "40px" }}>Loading...</div>;
  }

  return (
    <div style={styles.page}>
      <HistorySidebar
        history={history}
        onOpen={openHistory}
        onDelete={deleteHistory}
        onLogout={logout}
        collapsed={collapsed}
        setCollapsed={setCollapsed}
      />

      <main style={styles.main}>
        <Header user={user} onLogout={logout} />

        <motion.section
          style={styles.hero}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 style={styles.heading}>Generate Deep Research</h1>

          <p style={styles.sub}>
            Premium research reports with critique and structured output.
          </p>

          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Analyze AI impact on healthcare in 2026..."
            style={styles.textarea}
          />

          <button style={styles.button} onClick={handleResearch}>
            {loadingReport ? "Generating..." : "Generate Research Report"}
          </button>

          {loadingReport && <Loader />}

          {error && <p style={styles.error}>{error}</p>}
        </motion.section>

        {report && <ReportCard title="Research Report" content={report} />}

        {feedback && <ReportCard title="Critique Feedback" content={feedback} />}
      </main>
    </div>
  );
}

const styles = {
  page: { display: "flex", minHeight: "100vh" },
  main: { flex: 1, padding: "18px 24px", maxWidth: "1320px", margin: "0 auto" },
  hero: { maxWidth: "980px", margin: "0 auto" },
  heading: { fontSize: "44px", marginBottom: "8px", lineHeight: "1.1" },
  sub: { fontSize: "15px", color: "#9a9a9a", marginBottom: "18px" },
  textarea: {
    width: "100%",
    minHeight: "140px",
    borderRadius: "16px",
    padding: "16px",
    background: "#141414",
    color: "#fff",
    border: "1px solid rgba(255,255,255,0.06)",
    resize: "none",
    outline: "none",
    fontSize: "15px",
    marginBottom: "14px",
  },
  button: {
    width: "100%",
    padding: "14px",
    borderRadius: "14px",
    border: "none",
    background: "#853953",
    color: "#fff",
    fontWeight: "700",
    fontSize: "15px",
    cursor: "pointer",
  },
  error: { marginTop: "12px", color: "#ff6b6b" },
};