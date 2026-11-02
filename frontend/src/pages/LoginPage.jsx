import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import api from "../services/api";
import { saveToken } from "../services/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      setLoading(true);
      const res = await api.post("/login", form);
      saveToken(res.data.access_token);
      navigate("/dashboard");
    } catch (error) {
      alert(error.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.blurOne} />
      <div style={styles.blurTwo} />

      <div style={styles.left}>
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}>
          <p style={styles.brand}>ThinkMesh AI</p>

          <h1 style={styles.hero}>
            Deep Research.
            <br />
            Premium Output.
          </h1>

          <p style={styles.sub}>
            Generate expert reports, critiques and insights in seconds.
          </p>

          <div style={styles.points}>
            <span>Multi-source research</span>
            <span>Smart critique</span>
            <span>Instant reports</span>
          </div>
        </motion.div>
      </div>

      <motion.div
        style={styles.right}
        initial={{ opacity: 0, x: 40 }}
        animate={{ opacity: 1, x: 0 }}
      >
        <div style={styles.card}>
          <h2 style={styles.title}>Welcome Back</h2>
          <p style={styles.text}>Sign in to continue</p>

          <form onSubmit={handleSubmit} style={styles.form}>
            <input
              name="email"
              placeholder="Email"
              onChange={handleChange}
              style={styles.input}
            />

            <input
              type="password"
              name="password"
              placeholder="Password"
              onChange={handleChange}
              style={styles.input}
            />

            <motion.button
              type="submit"
              style={styles.button}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              {loading ? "Signing in..." : "Login"}
            </motion.button>
          </form>

          <p style={styles.footer}>
            New here?{" "}
            <Link to="/signup" style={styles.link}>
              Create account
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "grid",
    gridTemplateColumns: "1fr 520px",
    background: "#151515",
    position: "relative",
    overflow: "hidden",
  },
  left: { padding: "80px", display: "flex", alignItems: "center" },
  right: { display: "grid", placeItems: "center", padding: "40px" },
  brand: { color: "#F3F4F4", fontSize: "18px", marginBottom: "24px", opacity: ".8" },
  hero: { fontSize: "72px", lineHeight: "1.05", marginBottom: "24px" },
  sub: {
    color: "#A8A8A8",
    fontSize: "18px",
    lineHeight: "1.7",
    maxWidth: "520px",
    marginBottom: "32px",
  },
  points: { display: "flex", gap: "14px", flexWrap: "wrap", color: "#ddd", fontSize: "14px" },
  card: {
    width: "100%",
    maxWidth: "430px",
    background: "rgba(32,32,32,.88)",
    border: "1px solid rgba(255,255,255,.05)",
    borderRadius: "28px",
    padding: "42px",
    backdropFilter: "blur(12px)",
  },
  title: { fontSize: "34px", marginBottom: "8px" },
  text: { color: "#999", marginBottom: "28px" },
  form: { display: "grid", gap: "16px" },
  input: {
    padding: "16px",
    borderRadius: "16px",
    border: "1px solid rgba(255,255,255,.05)",
    background: "#2A2A2A",
    color: "white",
    fontSize: "15px",
  },
  button: {
    marginTop: "6px",
    padding: "16px",
    border: "none",
    borderRadius: "16px",
    background: "#853953",
    color: "white",
    fontWeight: "700",
    fontSize: "15px",
  },
  footer: { marginTop: "22px", color: "#999", fontSize: "14px" },
  link: { color: "#F3F4F4", textDecoration: "none" },
  blurOne: {
    position: "absolute",
    width: "280px",
    height: "280px",
    borderRadius: "50%",
    background: "#853953",
    filter: "blur(150px)",
    opacity: 0.15,
    top: "-80px",
    left: "-40px",
  },
  blurTwo: {
    position: "absolute",
    width: "260px",
    height: "260px",
    borderRadius: "50%",
    background: "#853953",
    filter: "blur(150px)",
    opacity: 0.09,
    bottom: "-60px",
    right: "120px",
  },
};