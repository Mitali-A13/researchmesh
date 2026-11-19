
import { useEffect, useRef, useState } from "react";
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
  const [stage, setStage] = useState("");
  const [topic, setTopic] = useState("");
  const [report, setReport] = useState("");
  const [feedback, setFeedback] = useState("");
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  // Stop polling when the page is left.
  const pollingRef = useRef(true);

  useEffect(() => {
    pollingRef.current = true;
    fetchUser();
    fetchHistory();

    return () => {
      pollingRef.current = false;
    };
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

  function pause(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // Poll the background job every 2 seconds.
  async function waitForJob(jobId) {
    let missedChecks = 0;

    while (pollingRef.current) {
      let body;

      try {
        const res = await api.get(`/research/jobs/${jobId}`);
        body = res.data;
        missedChecks = 0;
      } catch (err) {
        // Allow a few temporary network failures.
        if (err.response || ++missedChecks >= 3) throw err;

        await pause(2000);
        continue;
      }

      setStage(body.job.stage || "Working...");

      if (body.job.status === "completed") {
        return body.data;
      }

      if (body.job.status === "failed") {
        throw new Error(body.job.error || "Failed to generate report");
      }

      await pause(2000);
    }

    return null;
  }

  function errorText(err) {
    const detail = err.response?.data?.detail;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      return "Please enter a valid topic (3 to 300 characters).";
    }

    return err.message || "Failed to generate report";
  }

  async function handleResearch() {
    if (!topic.trim() || loadingReport) return;

    try {
      setLoadingReport(true);
      setError("");
      setReport("");
      setFeedback("");
      setStage("Starting...");

      const res = await api.post("/research", { topic });
      const data = await waitForJob(res.data.job.id);

      if (data) {
        setReport(data.report);
        setFeedback(data.feedback);
        fetchHistory();
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      if (pollingRef.current) {
        setLoadingReport(false);
        setStage("");
      }
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

          <button
            style={{ ...styles.button, opacity: loadingReport ? 0.6 : 1 }}
            onClick={handleResearch}
            disabled={loadingReport}
          >
            {loadingReport ? "Generating..." : "Generate Research Report"}
          </button>

          {loadingReport && (
            <Loader text={stage ? `${stage}...` : undefined} />
          )}

          {error && <p style={styles.error}>{error}</p>}
        </motion.section>

        {report && (
          <ReportCard title="Research Report" content={report} />
        )}

        {feedback && (
          <ReportCard title="Critique Feedback" content={feedback} />
        )}
      </main>
    </div>
  );
}

const styles = {
  page: { display: "flex", minHeight: "100vh" },
  main: {
    flex: 1,
    padding: "18px 24px",
    maxWidth: "1320px",
    margin: "0 auto",
  },
  hero: { maxWidth: "980px", margin: "0 auto" },
  heading: {
    fontSize: "44px",
    marginBottom: "8px",
    lineHeight: "1.1",
  },
  sub: {
    fontSize: "15px",
    color: "#9a9a9a",
    marginBottom: "18px",
  },
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
