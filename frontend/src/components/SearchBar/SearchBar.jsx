import { useState, useRef, useEffect } from "react";
import { searchGenes } from "../../api";
import styles from "./SearchBar.module.css";

export default function SearchBar({ genes, onAddGene, onRemoveGene }) {
  const [query, setQuery] = useState("");
  const [direction, setDirection] = useState("high");
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  /* Debounced autocomplete */
  useEffect(() => {
    if (query.length < 1) {
      setSuggestions([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchGenes(query, 8);
        setSuggestions(data.results || []);
        setShowSuggestions(true);
        setHighlightIdx(-1);
      } catch {
        setSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  /* Close dropdown on outside click */
  useEffect(() => {
    const handler = (e) => {
      if (inputRef.current && !inputRef.current.closest(`.${styles.wrapper}`)?.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function addGene(hugo) {
    if (!hugo) return;
    const exists = genes.some((g) => g.hugo.toUpperCase() === hugo.toUpperCase());
    if (exists) return;
    onAddGene({ hugo: hugo.toUpperCase(), direction });
    setQuery("");
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function handleKeyDown(e) {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === "Enter" && query.trim()) {
        addGene(query.trim());
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightIdx >= 0) {
        addGene(suggestions[highlightIdx].hugo_symbol);
      } else if (query.trim()) {
        addGene(query.trim());
      }
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <label className={styles.label}>Target Genes</label>

      {/* Gene tags */}
      {genes.length > 0 && (
        <div className={styles.tags}>
          {genes.map((g) => (
            <span
              key={g.hugo}
              className={`${styles.tag} ${g.direction === "high" ? styles.tagHigh : styles.tagLow}`}
            >
              {g.hugo}
              <span className={styles.tagDir}>{g.direction.toUpperCase()}</span>
              <button className={styles.tagRemove} onClick={() => onRemoveGene(g.hugo)}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className={styles.inputRow}>
        <div className={styles.inputGroup}>
          <input
            ref={inputRef}
            type="text"
            className={styles.input}
            placeholder="Search gene symbol (e.g. EGFR)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          />

          {/* Dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <ul className={styles.dropdown}>
              {suggestions.map((s, i) => (
                <li
                  key={s.ensembl_id}
                  className={`${styles.dropdownItem} ${i === highlightIdx ? styles.dropdownItemActive : ""}`}
                  onMouseDown={() => addGene(s.hugo_symbol)}
                  onMouseEnter={() => setHighlightIdx(i)}
                >
                  <span className={styles.hugoName}>{s.hugo_symbol}</span>
                  <span className={styles.ensemblId}>{s.ensembl_id}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Direction toggle */}
        <div className={styles.dirToggle} title="HIGH = rank cell lines with high expression first&#10;LOW = rank cell lines with low expression first">
          <button
            className={`${styles.dirBtn} ${direction === "high" ? styles.dirBtnActiveHigh : ""}`}
            onClick={() => setDirection("high")}
            title="Rank cell lines with HIGH expression of this gene first"
          >
            HIGH
          </button>
          <button
            className={`${styles.dirBtn} ${direction === "low" ? styles.dirBtnActiveLow : ""}`}
            onClick={() => setDirection("low")}
            title="Rank cell lines with LOW expression of this gene first"
          >
            LOW
          </button>
        </div>

        <button className={styles.addBtn} onClick={() => query.trim() && addGene(query.trim())}>
          Add
        </button>
      </div>
      <div style={{ fontSize: "11px", color: "#888", marginTop: "4px", lineHeight: "1.6" }}>
        <div>HIGH = prefer cell lines with high expression</div>
        <div>LOW = prefer cell lines with low expression</div>
      </div>
    </div>
  );
}
