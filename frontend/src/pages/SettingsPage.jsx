import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Shield, User, LogOut, Lock } from "lucide-react";

import api from "../services/api";
import { removeToken } from "../services/auth";

export default function SettingsPage() {
  const navigate = useNavigate();

  const [user, setUser] = useState(null);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchUser();
  }, []);

  async function fetchUser() {
    try {
      const res = await api.get("/me");
      setUser(res.data.user);
    } catch {
      navigate("/");
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();

    try {
      setMessage("");
      setError("");

      await api.put("/change-password", {
        current_password: oldPassword,
        new_password: newPassword,
      });

      setMessage("Password updated successfully.");
      setOldPassword("");
      setNewPassword("");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to change password");
    }
  }

  function logout() {
    removeToken();
    navigate("/");
  }

  const initials =
    user?.name
      ?.split(" ")
      .map((word) => word[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "U";

  return (
    <div style={styles.page}>
      <motion.div
        style={styles.wrap}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
      >
        <div style={styles.header}>
          <button style={styles.backBtn} onClick={() => navigate("/dashboard")}>
            <ArrowLeft size={16} />
            Dashboard
          </button>
          <h1 style={styles.heading}>Settings</h1>
        </div>

        {user && (
          <section style={styles.card}>
            <div style={styles.cardTop}>
              <div style={styles.avatar}>{initials}</div>
              <div>
                <p style={styles.label}>PROFILE</p>
                <h2 style={styles.title}>{user.name}</h2>
                <p style={styles.sub}>{user.email}</p>
              </div>
            </div>

            <div style={styles.infoRow}>
              <div style={styles.badge}>
                <User size={14} />
                Account
              </div>
              <div style={styles.badge}>
                <Shield size={14} />
                Secured
              </div>
            </div>
          </section>
        )}

        <form onSubmit={handleChangePassword} style={styles.card}>
          <div style={styles.formHead}>
            <Lock size={18} />
            <h2 style={styles.formTitle}>Change Password</h2>
          </div>

          <input
            type="password"
            placeholder="Current Password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            required
            style={styles.input}
          />

          <input
            type="password"
            placeholder="New Password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            style={styles.input}
          />

          <button type="submit" style={styles.primaryBtn}>
            Update Password
          </button>

          {message && <p style={styles.success}>{message}</p>}
          {error && <p style={styles.error}>{error}</p>}
        </form>

        <section style={styles.card}>
          <div style={styles.formHead}>
            <LogOut size={18} />
            <h2 style={styles.formTitle}>Session</h2>
          </div>

          <p style={styles.sub}>Securely sign out from your account.</p>

          <button onClick={logout} style={styles.logoutBtn}>
            Logout
          </button>
        </section>
      </motion.div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#0a0a0a", color: "#fff", padding: "34px 18px" },
  wrap: { maxWidth: "920px", margin: "0 auto" },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "22px",
    gap: "14px",
  },
  backBtn: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    border: "none",
    background: "#141414",
    color: "#fff",
    padding: "10px 14px",
    borderRadius: "12px",
    cursor: "pointer",
  },
  heading: { margin: 0, fontSize: "34px", fontWeight: "700" },
  card: {
    background: "#111111",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: "22px",
    padding: "24px",
    marginBottom: "18px",
  },
  cardTop: { display: "flex", gap: "18px", alignItems: "center", marginBottom: "18px" },
  avatar: {
    width: "64px",
    height: "64px",
    borderRadius: "50%",
    background: "#853953",
    display: "grid",
    placeItems: "center",
    fontWeight: "700",
    fontSize: "20px",
  },
  label: { margin: 0, fontSize: "12px", color: "#8a8a8a", letterSpacing: "1px" },
  title: { margin: "6px 0 4px", fontSize: "26px" },
  sub: { margin: 0, color: "#9a9a9a", fontSize: "14px" },
  infoRow: { display: "flex", gap: "10px", flexWrap: "wrap" },
  badge: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "10px 12px",
    borderRadius: "12px",
    background: "#171717",
    fontSize: "13px",
    color: "#ddd",
  },
  formHead: { display: "flex", alignItems: "center", gap: "10px", marginBottom: "18px" },
  formTitle: { margin: 0, fontSize: "20px" },
  input: {
    width: "100%",
    padding: "14px 16px",
    borderRadius: "14px",
    border: "1px solid rgba(255,255,255,0.06)",
    background: "#171717",
    color: "#fff",
    outline: "none",
    fontSize: "15px",
    marginBottom: "12px",
    boxSizing: "border-box",
  },
  primaryBtn: {
    width: "100%",
    padding: "14px",
    borderRadius: "14px",
    border: "none",
    background: "#853953",
    color: "#fff",
    fontWeight: "700",
    fontSize: "15px",
    cursor: "pointer",
    marginTop: "6px",
  },
  logoutBtn: {
    marginTop: "16px",
    width: "100%",
    padding: "14px",
    borderRadius: "14px",
    border: "1px solid rgba(255,255,255,0.06)",
    background: "#171717",
    color: "#fff",
    fontWeight: "700",
    cursor: "pointer",
  },
  success: { marginTop: "12px", color: "#56d98c", fontSize: "14px" },
  error: { marginTop: "12px", color: "#ff6b6b", fontSize: "14px" },
};