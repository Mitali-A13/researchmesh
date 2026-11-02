import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import api from "../services/api";

export default function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      setLoading(true);
      await api.post("/signup", form);
      alert("Signup successful");
      navigate("/");
    } catch (error) {
      alert(error.response?.data?.detail || "Signup failed");
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
            Build Better
            <br />
            Research Faster.
          </h1>

          <p style={styles.sub}>
            Join premium users generating modern research workflows.
          </p>
        </motion.div>
      </div>

      <motion.div
        style={styles.right}
        initial={{ opacity: 0, x: 40 }}
        animate={{ opacity: 1, x: 0 }}
      >
        <div style={styles.card}>
          <h2 style={styles.title}>Create Account</h2>
          <p style={styles.text}>Start in seconds</p>

          <form onSubmit={handleSubmit} style={styles.form}>
            <input
              name="name"
              placeholder="Full Name"
              onChange={handleChange}
              style={styles.input}
            />

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
              {loading ? "Creating..." : "Signup"}
            </motion.button>
          </form>

          <p style={styles.footer}>
            Already have account?{" "}
            <Link to="/" style={styles.link}>
              Login
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
  sub: { color: "#A8A8A8", fontSize: "18px", lineHeight: "1.7", maxWidth: "520px" },
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
  },
  button: {
    marginTop: "6px",
    padding: "16px",
    border: "none",
    borderRadius: "16px",
    background: "#853953",
    color: "white",
    fontWeight: "700",
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