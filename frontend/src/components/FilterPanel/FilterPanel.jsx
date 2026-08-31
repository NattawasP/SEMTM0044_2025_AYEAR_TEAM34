import { useState, useEffect, useMemo } from "react";
import { getDiseases, getLineages, getDiseaseLineageMapping } from "../../api";
import styles from "./FilterPanel.module.css";

const MODE_OPTIONS = ["ignore", "include", "exclude"];

const DATA_SOURCES = [
  { key: "depmap", label: "DepMap" },
  { key: "hpa", label: "HPA" },
  { key: "geo", label: "GEO" },
];

export default function FilterPanel({ filters, onChange }) {
  const [allDiseases, setAllDiseases] = useState([]);
  const [allLineages, setAllLineages] = useState([]);
  const [mapping, setMapping] = useState([]);   // [{disease, lineage}, ...]

  /* Load dropdown options + mapping once */
  useEffect(() => {
    getDiseases()
      .then((d) => setAllDiseases(d.values || []))
      .catch((err) => console.error("Failed to load diseases:", err));
    getLineages()
      .then((d) => setAllLineages(d.values || []))
      .catch((err) => console.error("Failed to load lineages:", err));
    getDiseaseLineageMapping()
      .then((d) => setMapping(d.pairs || []))
      .catch((err) => console.error("Failed to load mapping:", err));
  }, []);

  /* One-way: disease → lineage (selecting a disease filters lineage options) */
  const diseases = allDiseases;

  const lineages = useMemo(() => {
    if (!filters.disease_filter) return allLineages;
    const valid = new Set(
      mapping.filter((p) => p.disease === filters.disease_filter).map((p) => p.lineage)
    );
    return allLineages.filter((l) => valid.has(l));
  }, [allLineages, mapping, filters.disease_filter]);

  function set(key, value) {
    const next = { ...filters, [key]: value };

    // When disease changes, reset lineage if it's no longer valid
    if (key === "disease_filter") {
      if (value === null) {
        // Clearing disease also clears lineage
        next.lineage_filter = null;
      } else if (filters.lineage_filter) {
        const validLineages = new Set(
          mapping.filter((p) => p.disease === value).map((p) => p.lineage)
        );
        if (!validLineages.has(filters.lineage_filter)) {
          next.lineage_filter = null;
        }
      }
    }

    onChange(next);
  }

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>Filters & Options</h3>

      <div className={styles.grid}>
        {/* Data sources to include */}
        <div className={styles.field}>
          <label className={styles.label}>RNA Sources Used for Scoring</label>
          <span style={{ fontSize: "11px", color: "#888", marginTop: "-4px", display: "block" }}>
            Only selected sources are used in the ranking calculation
          </span>
          <div className={styles.sourceChecks}>
            {DATA_SOURCES.map((src) => {
              const sources = filters.sources || ["depmap", "hpa", "geo"];
              const checked = sources.includes(src.key);
              return (
                <label key={src.key} className={styles.sourceCheck}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const next = e.target.checked
                        ? [...sources, src.key]
                        : sources.filter((s) => s !== src.key);
                      // Prevent unchecking all sources
                      if (next.length === 0) return;
                      onChange({ ...filters, sources: next });
                    }}
                  />
                  {src.label}
                </label>
              );
            })}
          </div>
        </div>

        {/* Mutation mode */}
        <div className={styles.field}>
          <label className={styles.label}>Mutation Filter</label>
          <div className={styles.modeToggle}>
            {MODE_OPTIONS.map((m) => (
              <button
                key={m}
                className={`${styles.modeBtn} ${filters.mutation_mode === m ? styles[`mode_${m}`] : ""
                  }`}
                onClick={() => set("mutation_mode", m)}
              >
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>
          {filters.mutation_mode === "include" && (
            <label style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "8px", fontSize: "13px", color: "#555" }}>
              <input
                type="checkbox"
                checked={filters.driver_only || false}
                onChange={(e) => set("driver_only", e.target.checked)}
              />
              Driver only
            </label>
          )}
        </div>

        {/* Fusion mode */}
        <div className={styles.field}>
          <label className={styles.label}>Fusion Filter</label>
          <div className={styles.modeToggle}>
            {MODE_OPTIONS.map((m) => (
              <button
                key={m}
                className={`${styles.modeBtn} ${filters.fusion_mode === m ? styles[`mode_${m}`] : ""
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
            max="100"
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
