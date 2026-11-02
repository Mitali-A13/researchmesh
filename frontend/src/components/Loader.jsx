import { motion } from "framer-motion";

export default function Loader({ text = "Generating premium research report..." }) {
  return (
    <motion.div style={styles.wrap} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div style={styles.row}>
        <span style={styles.dot} />
        <span style={styles.dot} />
        <span style={styles.dot} />
      </div>
      <p style={styles.text}>{text}</p>
    </motion.div>
  );
}

const styles = {
  wrap: {
    marginTop: "22px",
    padding: "18px",
    borderRadius: "18px",
    background: "rgba(30,30,30,.92)",
    border: "1px solid rgba(255,255,255,.05)",
  },
  row: { display: "flex", gap: "8px", marginBottom: "12px" },
  dot: { width: "10px", height: "10px", borderRadius: "50%", background: "#853953" },
  text: { margin: 0, color: "#B8B8B8", fontSize: "14px" },
};