import { useState, useEffect } from "react";
import { getDiseases, getLineages } from "../../api";
import styles from "./FilterPanel.module.css";

const MODE_OPTIONS = ["ignore", "include", "exclude"];

export default function FilterPanel({ filters, onChange }) {
  const [diseases, setDiseases] = useState([]);
  const [lineages, setLineages] = useState([]);

  /* Load dropdown options once */
  useEffect(() => {
    getDiseases()
      .then((d) => setDiseases(d.values || []))
      .catch((err) => console.error("Failed to load diseases:", err));
    getLineages()
      .then((d) => setLineages(d.values || []))
      .catch((err) => console.error("Failed to load lineages:", err));
  }, []);

  function set(key, value) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>Filters & Options</h3>

      <div className={styles.grid}>
        {/* Mutation mode */}
        <div className={styles.field}>
          <label className={styles.label}>Mutation Filter</label>
          <div className={styles.modeToggle}>
            {MODE_OPTIONS.map((m) => (
              <button
                key={m}
                className={`${styles.modeBtn} ${
                  filters.mutation_mode === m ? styles[`mode_${m}`] : ""
                }`}
                onClick={() => set("mutation_mode", m)}
              >
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Fusion mode */}
        <div className={styles.field}>
          <label className={styles.label}>Fusion Filter</label>
          <div className={styles.modeToggle}>
            {MODE_OPTIONS.map((m) => (
              <button
                key={m}
                className={`${styles.modeBtn} ${
                  filters.fusion_mode === m ? styles[`mode_${m}`] : ""
                }`}
                onClick={() => set("fusion_mode", m)}
              >
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Disease dropdown */}
        <div className={styles.field}>
          <label className={styles.label}>Disease</label>
          <select
            className={styles.select}
            value={filters.disease_filter || ""}
            onChange={(e) => set("disease_filter", e.target.value || null)}
          >
            <option value="">All diseases</option>
            {diseases.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>

        {/* Lineage dropdown */}
        <div className={styles.field}>
          <label className={styles.label}>Lineage</label>
          <select
            className={styles.select}
            value={filters.lineage_filter || ""}
            onChange={(e) => set("lineage_filter", e.target.value || null)}
          >
            <option value="">All lineages</option>
            {lineages.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>

        {/* RNA:Protein weight slider */}
        <div className={styles.field}>
          <label className={styles.label}>
            RNA weight: {Math.round(filters.w_rna * 100)}% — Protein:{" "}
            {Math.round(filters.w_protein * 100)}%
          </label>
          <input
            type="range"
            className={styles.slider}
            min="50"
            max="95"
            step="5"
            value={Math.round(filters.w_rna * 100)}
            onChange={(e) => {
              const rna = parseInt(e.target.value) / 100;
              set("w_rna", rna);
              onChange({ ...filters, w_rna: rna, w_protein: +(1 - rna).toFixed(2) });
            }}
          />
        </div>

        {/* Top-N slider */}
        <div className={styles.field}>
          <label className={styles.label}>Show top {filters.top_n} results</label>
          <input
            type="range"
            className={styles.slider}
            min="5"
            max="50"
            step="5"
            value={filters.top_n}
            onChange={(e) => set("top_n", parseInt(e.target.value))}
          />
        </div>

        {/* Core only checkbox */}
        <div className={styles.checkField}>
          <label className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={filters.core_only}
              onChange={(e) => set("core_only", e.target.checked)}
            />
            Core cell lines only (data in all 3 expression sources)
          </label>
        </div>
      </div>
    </div>
  );
}
