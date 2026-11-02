import { PanelLeftClose, PanelLeftOpen, Trash2, Plus, LogOut, FileText } from "lucide-react";
import { motion } from "framer-motion";

export default function HistorySidebar({
  history,
  onOpen,
  onDelete,
  onLogout,
  collapsed,
  setCollapsed,
}) {
  return (
    <motion.aside
      animate={{ width: collapsed ? 78 : 270 }}
      transition={{ duration: 0.25 }}
      style={styles.sidebar}
    >
      <div>
        <div style={styles.top}>
          {!collapsed && <h2 style={styles.logo}>ThinkMesh AI</h2>}
          <button style={styles.iconBtn} onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        <button style={styles.newBtn}>
          <Plus size={16} />
          {!collapsed && "New Research"}
        </button>

        {!collapsed && <p style={styles.label}>Recent Reports</p>}

        <div style={styles.list}>
          {history.map((item) => (
            <div key={item.id} style={styles.card}>
              {collapsed ? (
                <button style={styles.iconOnly} onClick={() => onOpen(item.id)}>
                  <FileText size={16} />
                </button>
              ) : (
                <>
                  <div onClick={() => onOpen(item.id)} style={{ cursor: "pointer" }}>
                    <div style={styles.topic}>{item.topic}</div>
                    <div style={styles.date}>{item.created_at.slice(0, 10)}</div>
                  </div>
                  <button style={styles.delete} onClick={() => onDelete(item.id)}>
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <button style={styles.logout} onClick={onLogout}>
        <LogOut size={16} />
        {!collapsed && "Sign Out"}
      </button>
    </motion.aside>
  );
}

const styles = {
  sidebar: {
    minHeight: "100vh",
    background: "#111111",
    borderRight: "1px solid rgba(255,255,255,.06)",
    padding: "18px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    overflow: "hidden",
  },
  top: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "18px",
  },
  logo: { margin: 0, fontSize: "22px", whiteSpace: "nowrap" },
  iconBtn: { border: "none", background: "transparent", color: "#aaa", cursor: "pointer" },
  newBtn: {
    width: "100%",
    padding: "12px",
    borderRadius: "12px",
    border: "none",
    background: "#853953",
    color: "#fff",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    gap: "8px",
    fontWeight: "600",
    cursor: "pointer",
    marginBottom: "18px",
  },
  label: { fontSize: "11px", color: "#888", marginBottom: "10px" },
  list: { display: "flex", flexDirection: "column", gap: "10px" },
  card: {
    background: "#171717",
    borderRadius: "12px",
    padding: "12px",
    border: "1px solid rgba(255,255,255,.05)",
  },
  topic: { fontSize: "14px", fontWeight: "600", lineHeight: "1.35" },
  date: { fontSize: "12px", color: "#888", marginTop: "6px" },
  delete: {
    marginTop: "8px",
    border: "none",
    background: "transparent",
    color: "#888",
    cursor: "pointer",
  },
  iconOnly: {
    width: "100%",
    border: "none",
    background: "transparent",
    color: "#fff",
    cursor: "pointer",
  },
  logout: {
    marginTop: "18px",
    padding: "12px",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,.06)",
    background: "#171717",
    color: "#fff",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "8px",
  },
};