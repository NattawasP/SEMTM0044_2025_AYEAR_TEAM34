import { useState, useEffect, useMemo } from "react";
import { getDiseases, getLineages, getDiseaseLineageMapping, getSubtypes, getDiseaseLineageSubtypeMapping } from "../../api";
import styles from "./FilterPanel.module.css";

const MODE_OPTIONS = ["ignore", "include", "exclude"];

const ASSAY_OPTIONS = [
  { key: "", label: "No assay selected" },
  { key: "adherent_screen", label: "Adherent screen (96/384 well)" },
  { key: "3d_spheroid", label: "3D spheroid" },
  { key: "suspension_screen", label: "Suspension screen" },
  { key: "flexible", label: "Flexible" },
];

const DATA_SOURCES = [
  { key: "depmap", label: "DepMap" },
  { key: "hpa", label: "HPA" },
  { key: "geo", label: "GEO" },
];

export default function FilterPanel({ filters, onChange }) {
  const [allDiseases, setAllDiseases] = useState([]);
  const [allLineages, setAllLineages] = useState([]);
  const [allSubtypes, setAllSubtypes] = useState([]);
  const [mapping, setMapping] = useState([]);
  const [tripleMapping, setTripleMapping] = useState([]);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    getDiseases()
      .then((d) => setAllDiseases(d.values || []))
      .catch((err) => console.error("Failed to load diseases:", err));
    getLineages()
      .then((d) => setAllLineages(d.values || []))
      .catch((err) => console.error("Failed to load lineages:", err));
    getSubtypes()
      .then((d) => setAllSubtypes(d.values || []))
      .catch((err) => console.error("Failed to load subtypes:", err));
    getDiseaseLineageMapping()
      .then((d) => setMapping(d.pairs || []))
      .catch((err) => console.error("Failed to load mapping:", err));
    getDiseaseLineageSubtypeMapping()
      .then((d) => setTripleMapping(d.triples || []))
      .catch((err) => console.error("Failed to load triple mapping:", err));
  }, []);

  const diseases = allDiseases;

  const lineages = useMemo(() => {
    if (!filters.disease_filter) return allLineages;
    const valid = new Set(
      mapping.filter((p) => p.disease === filters.disease_filter).map((p) => p.lineage)
    );
    return allLineages.filter((l) => valid.has(l));
  }, [allLineages, mapping, filters.disease_filter]);

  const subtypes = useMemo(() => {
    let filtered = tripleMapping;
    if (filters.disease_filter) {
      filtered = filtered.filter((t) => t.disease === filters.disease_filter);
    }
    if (filters.lineage_filter) {
      filtered = filtered.filter((t) => t.lineage === filters.lineage_filter);
    }
    const valid = new Set(filtered.map((t) => t.subtype));
    return allSubtypes.filter((s) => valid.has(s));
  }, [allSubtypes, tripleMapping, filters.disease_filter, filters.lineage_filter]);

  const advancedCount = useMemo(() => {
    let n = 0;
    if (filters.mutation_mode !== "ignore") n++;
    if (filters.fusion_mode !== "ignore") n++;
    if (filters.assay_type) n++;
    if (filters.msi_max != null) n++;
    if (filters.cin_max != null) n++;
    if (filters.exclude_metabolite) n++;
    if (filters.exclude_mirna) n++;
    if (filters.core_only) n++;
    const sources = filters.sources || ["depmap", "hpa", "geo"];
    if (sources.length < 3) n++;
    if (filters.w_rna !== 0.7) n++;
    if (filters.top_n !== 20) n++;
    return n;
  }, [filters]);

  function set(key, value) {
    const next = { ...filters, [key]: value };

    if (key === "disease_filter") {
      if (value === null) {
        next.lineage_filter = null;
        next.subtype_filter = null;
      } else {
        // Reset lineage if no longer valid for new disease
        if (filters.lineage_filter) {
          const validLineages = new Set(
            mapping.filter((p) => p.disease === value).map((p) => p.lineage)
          );
          if (!validLineages.has(filters.lineage_filter)) {
            next.lineage_filter = null;
          }
        }
        // Reset subtype if no longer valid
        if (filters.subtype_filter) {
          const validSubs = new Set(
            tripleMapping
              .filter((t) => t.disease === value && (!next.lineage_filter || t.lineage === next.lineage_filter))
              .map((t) => t.subtype)
          );
          if (!validSubs.has(filters.subtype_filter)) {
            next.subtype_filter = null;
          }
        }
      }
    }

    if (key === "lineage_filter") {
      // Reset subtype if no longer valid for new lineage
      if (filters.subtype_filter) {
        const validSubs = new Set(
          tripleMapping
            .filter((t) => (!next.disease_filter || t.disease === next.disease_filter) && (!value || t.lineage === value))
            .map((t) => t.subtype)
        );
        if (!validSubs.has(filters.subtype_filter)) {
          next.subtype_filter = null;
        }
      }
    }

    onChange(next);
  }

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>Filters & Options</h3>

      <div className={styles.grid}>
        {/* ── BASIC FILTERS (always visible) ── */}

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

        {/* Subtype dropdown */}
        <div className={styles.field}>
          <label className={styles.label}>Subtype</label>
          <select
            className={styles.select}
            value={filters.subtype_filter || ""}
            onChange={(e) => set("subtype_filter", e.target.value || null)}
          >
            <option value="">All subtypes</option>
            {subtypes.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* ── ADVANCED FILTERS (collapsible) ── */}
        <button
          className={styles.advancedToggle}
          onClick={() => setAdvancedOpen((o) => !o)}
        >
          <span>
            Advanced Filters
            {advancedCount > 0 && (
              <span className={styles.advancedBadge}>{advancedCount} active</span>
            )}
          </span>
          <span className={`${styles.chevron} ${advancedOpen ? styles.chevronOpen : ""}`}>
            &#9662;
          </span>
        </button>

        {advancedOpen && (
          <div className={styles.advancedSection}>

            {/* ── GROUP: Scoring ── */}
            <div className={styles.groupHeader}>Scoring</div>

            {/* RNA Sources */}
            <div className={styles.field}>
              <label className={styles.label}>RNA Sources</label>
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

            {/* RNA:Protein weight slider */}
            <div className={styles.field}>
              <label className={styles.label}>
                RNA: {Math.round(filters.w_rna * 100)}% — Protein:{" "}
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
                Core only (data in all 3 sources)
              </label>
            </div>

            {/* ── GROUP: Genomic Filters ── */}
            <div className={styles.groupHeader}>Genomic Filters</div>

            {/* Mutation mode */}
            <div className={styles.field}>
              <label className={styles.label}>Mutation</label>
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
              {filters.mutation_mode === "include" && (
                <label className={styles.inlineCheck}>
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
              <label className={styles.label}>Fusion</label>
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

            {/* ── GROUP: Cell Line Exclusion ── */}
            <div className={styles.groupHeader}>Cell Line Exclusion</div>

            {/* Genomic instability thresholds */}
            <div className={styles.field}>
              <label className={styles.label}>Genomic Instability</label>
              <span className={styles.hint}>
                Exclude cell lines above these thresholds
              </span>
              <div className={styles.thresholdRow}>
                <label className={styles.thresholdLabel}>
                  MSI max
                  <input
                    type="number"
                    className={styles.thresholdInput}
                    placeholder="e.g. 0.4"
                    step="0.1"
                    min="0"
                    max="1"
                    value={filters.msi_max ?? ""}
                    onChange={(e) =>
                      set("msi_max", e.target.value ? parseFloat(e.target.value) : null)
                    }
                  />
                </label>
                <label className={styles.thresholdLabel}>
                  CIN max
                  <input
                    type="number"
                    className={styles.thresholdInput}
                    placeholder="e.g. 0.5"
                    step="0.1"
                    min="0"
                    max="1"
                    value={filters.cin_max ?? ""}
                    onChange={(e) =>
                      set("cin_max", e.target.value ? parseFloat(e.target.value) : null)
                    }
                  />
                </label>
              </div>
            </div>

            {/* Metabolite exclusion */}
            <div className={styles.field}>
              <label className={styles.label}>Metabolite</label>
              <div className={styles.thresholdRow}>
                <label className={styles.thresholdLabel}>
                  Name
                  <input
                    type="text"
                    className={styles.thresholdInput}
                    placeholder="e.g. glutamine"
                    value={filters.exclude_metabolite ?? ""}
                    onChange={(e) => set("exclude_metabolite", e.target.value || null)}
                  />
                </label>
                <label className={styles.thresholdLabel}>
                  Max level
                  <input
                    type="number"
                    className={styles.thresholdInput}
                    placeholder="threshold"
                    step="0.1"
                    value={filters.metabolite_threshold ?? ""}
                    onChange={(e) =>
                      set(
                        "metabolite_threshold",
                        e.target.value ? parseFloat(e.target.value) : null
                      )
                    }
                  />
                </label>
              </div>
            </div>

            {/* miRNA exclusion */}
            <div className={styles.field}>
              <label className={styles.label}>miRNA</label>
              <div className={styles.thresholdRow}>
                <label className={styles.thresholdLabel}>
                  ID
                  <input
                    type="text"
                    className={styles.thresholdInput}
                    placeholder="e.g. hsa-miR-21"
                    value={filters.exclude_mirna ?? ""}
                    onChange={(e) => set("exclude_mirna", e.target.value || null)}
                  />
                </label>
                <label className={styles.thresholdLabel}>
                  Max level
                  <input
                    type="number"
                    className={styles.thresholdInput}
                    placeholder="threshold"
                    step="0.1"
                    value={filters.mirna_threshold ?? ""}
                    onChange={(e) =>
                      set(
                        "mirna_threshold",
                        e.target.value ? parseFloat(e.target.value) : null
                      )
                    }
                  />
                </label>
              </div>
            </div>

            {/* ── GROUP: Experimental Context ── */}
            <div className={styles.groupHeader}>Experimental Context</div>

            {/* Planned assay */}
            <div className={styles.field}>
              <label className={styles.label}>Planned Assay</label>
              <select
                className={styles.select}
                value={filters.assay_type || ""}
                onChange={(e) => set("assay_type", e.target.value || null)}
              >
                {ASSAY_OPTIONS.map((a) => (
                  <option key={a.key} value={a.key}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
