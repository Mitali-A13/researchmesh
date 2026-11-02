import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

export default function ReportCard({ title, content }) {
  function copyText() {
    navigator.clipboard.writeText(content);
  }

  return (
    <motion.section
      style={styles.card}
      initial={{ opacity: 0, y: 30, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
    >
      <div style={styles.top}>
        <div>
          <p style={styles.label}>AI OUTPUT</p>
          <h2 style={styles.title}>{title}</h2>
        </div>
        <button onClick={copyText} style={styles.copy}>
          Copy
        </button>
      </div>

      <div style={styles.line} />

      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18, duration: 0.45 }}
        style={styles.reader}
      >
        <ReactMarkdown
          components={{
            h1: ({ children }) => <h1 style={styles.h1}>{children}</h1>,
            h2: ({ children }) => <h2 style={styles.h2}>{children}</h2>,
            h3: ({ children }) => <h3 style={styles.h3}>{children}</h3>,
            p: ({ children }) => <p style={styles.p}>{children}</p>,
            li: ({ children }) => <li style={styles.li}>{children}</li>,
            strong: ({ children }) => <strong style={styles.bold}>{children}</strong>,
            a: ({ href, children }) => (
              <a href={href} target="_blank" rel="noreferrer" style={styles.link}>
                {children}
              </a>
            ),
            code: ({ children }) => <code style={styles.code}>{children}</code>,
            blockquote: ({ children }) => (
              <blockquote style={styles.quote}>{children}</blockquote>
            ),
            table: ({ children }) => (
              <div style={styles.tableWrap}>
                <table style={styles.table}>{children}</table>
              </div>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </motion.div>
    </motion.section>
  );
}

const styles = {
  card: {
    marginTop: "28px",
    padding: "32px",
    borderRadius: "26px",
    background: "rgba(28,28,28,0.94)",
    border: "1px solid rgba(255,255,255,0.05)",
    backdropFilter: "blur(12px)",
    maxWidth: "920px",
    marginLeft: "auto",
    marginRight: "auto",
  },
  top: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "16px",
    marginBottom: "18px",
  },
  label: { margin: 0, fontSize: "12px", color: "#8D8D8D", letterSpacing: "1.2px" },
  title: { margin: "6px 0 0 0", fontSize: "32px", fontWeight: "700" },
  copy: {
    border: "none",
    background: "#853953",
    color: "white",
    padding: "10px 18px",
    borderRadius: "12px",
    fontWeight: "600",
    cursor: "pointer",
  },
  line: { height: "1px", background: "rgba(255,255,255,0.06)", marginBottom: "28px" },
  reader: { textAlign: "left" },
  h1: { fontSize: "34px", marginBottom: "18px", marginTop: "26px", color: "#ffffff", fontWeight: "700" },
  h2: { fontSize: "28px", marginBottom: "16px", marginTop: "24px", color: "#ffffff", fontWeight: "650" },
  h3: { fontSize: "22px", marginBottom: "14px", marginTop: "20px", color: "#ffffff", fontWeight: "600" },
  p: { fontSize: "16px", lineHeight: "1.95", color: "#E6E6E6", marginBottom: "18px" },
  li: { marginBottom: "10px", color: "#E6E6E6", lineHeight: "1.8" },
  bold: { color: "#ffffff", fontWeight: "700" },
  link: { color: "#e3a0b8", textDecoration: "underline" },
  code: {
    background: "rgba(255,255,255,0.06)",
    padding: "3px 8px",
    borderRadius: "8px",
    fontSize: "14px",
  },
  quote: {
    borderLeft: "3px solid #853953",
    paddingLeft: "16px",
    color: "#bdbdbd",
    margin: "18px 0",
  },
  tableWrap: { overflowX: "auto", margin: "20px 0" },
  table: { width: "100%", borderCollapse: "collapse", color: "white" },
};