import { useState, useRef, useEffect } from "react";
import { chatWithAgent } from "../../api";
import styles from "./ChatWidget.module.css";

const SUGGESTIONS = [
  "Find lung cancer cells for adherent screens",
  "Tell me about HCC827",
  "What assay types can I use?",
  "Compare A549 and HCC827",
];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // {role, content}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]); // conversation history for API
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(text) {
    const msg = text || input.trim();
    if (!msg || loading) return;

    // Add user message
    const userMsg = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await chatWithAgent(msg, history);
      const botMsg = { role: "assistant", content: res.answer };

      setMessages((prev) => [...prev, botMsg]);
      setHistory(res.history || []);

      // Store tool calls info if any
      if (res.tool_calls_made && res.tool_calls_made.length > 0) {
        botMsg._tools = res.tool_calls_made;
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "error", content: err.message || "Something went wrong." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // Collapsed state — just the bubble
  if (!open) {
    return (
      <button
        className={styles.bubble}
        onClick={() => setOpen(true)}
        title="Ask CellLineFinder"
        aria-label="Open chat"
      >
        💬
      </button>
    );
  }

  // Expanded panel
  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <span className={styles.headerIcon}>🔬</span>
          Ask CellLineFinder
        </div>
        <button
          className={styles.closeBtn}
          onClick={() => setOpen(false)}
          aria-label="Close chat"
        >
          ×
        </button>
      </div>

      {/* Messages */}
      <div className={styles.messages}>
        {messages.length === 0 && !loading && (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>🧬</div>
            <div className={styles.welcomeTitle}>Cell Line Assistant</div>
            <p className={styles.welcomeText}>
              Ask me about cell lines, lineages, assay compatibility, or gene
              targets. I'll search the database for you.
            </p>
            <div className={styles.suggestions}>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className={styles.suggestionBtn}
                  onClick={() => handleSend(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`${styles.msgRow} ${
              msg.role === "user" ? styles.msgRowUser : styles.msgRowBot
            }`}
          >
            <div
              className={`${styles.msgBubble} ${
                msg.role === "user"
                  ? styles.msgUser
                  : msg.role === "error"
                  ? styles.msgError
                  : styles.msgBot
              }`}
            >
              {msg.content}
              {msg._tools && msg._tools.length > 0 && (
                <div className={styles.toolsBadge}>
                  🔧 Used: {msg._tools.join(", ")}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className={`${styles.msgRow} ${styles.msgRowBot}`}>
            <div className={styles.typing}>
              <div className={styles.dot} />
              <div className={styles.dot} />
              <div className={styles.dot} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className={styles.inputArea}>
        <input
          className={styles.input}
          type="text"
          placeholder="Ask a question..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          autoFocus
        />
        <button
          className={styles.sendBtn}
          onClick={() => handleSend()}
          disabled={!input.trim() || loading}
          aria-label="Send message"
        >
          ↑
        </button>
      </div>
    </div>
  );
}
