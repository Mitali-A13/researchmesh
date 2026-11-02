import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Settings, LogOut } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function Header({ user, onLogout }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const initials =
    user?.name
      ?.split(" ")
      .map((w) => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "U";

  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <span style={styles.path}>Home</span>
        <span style={styles.sep}>/</span>
        <h1 style={styles.title}>Research Dashboard</h1>
      </div>

      <div style={styles.wrapper}>
        <button style={styles.trigger} onClick={() => setOpen(!open)}>
          <div style={styles.avatar}>{initials}</div>
          <span style={styles.name}>{user?.name}</span>
          <ChevronDown size={14} />
        </button>

        <AnimatePresence>
          {open && (
            <motion.div
              style={styles.menu}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <button style={styles.item} onClick={() => navigate("/settings")}>
                <Settings size={15} />
                Settings
              </button>
              <button style={styles.item} onClick={onLogout}>
                <LogOut size={15} />
                Logout
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  );
}

const styles = {
  header: {
    height: "62px",
    padding: "0 18px",
    borderRadius: "16px",
    background: "#111111",
    border: "1px solid rgba(255,255,255,0.06)",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "18px",
  },
  left: { display: "flex", alignItems: "center", gap: "10px" },
  path: { fontSize: "13px", color: "#8e8e8e" },
  sep: { color: "#555" },
  title: { margin: 0, fontSize: "18px", fontWeight: "600" },
  wrapper: { position: "relative" },
  trigger: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    background: "transparent",
    border: "none",
    color: "#fff",
    cursor: "pointer",
  },
  avatar: {
    width: "34px",
    height: "34px",
    borderRadius: "50%",
    display: "grid",
    placeItems: "center",
    background: "#853953",
    fontSize: "13px",
    fontWeight: "700",
  },
  name: { fontSize: "14px" },
  menu: {
    position: "absolute",
    top: "48px",
    right: 0,
    width: "180px",
    padding: "8px",
    borderRadius: "14px",
    background: "#161616",
    border: "1px solid rgba(255,255,255,0.06)",
    zIndex: 100,
  },
  item: {
    width: "100%",
    padding: "11px 12px",
    background: "transparent",
    border: "none",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    borderRadius: "10px",
    fontSize: "14px",
    cursor: "pointer",
  },
};