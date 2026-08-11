import { useState, useCallback } from "react";
import SearchBar from "./components/SearchBar/SearchBar.jsx";
import FilterPanel from "./components/FilterPanel/FilterPanel.jsx";
import ResultsTable from "./components/ResultsTable/ResultsTable.jsx";
import DetailPanel from "./components/DetailPanel/DetailPanel.jsx";
import CompareView from "./components/CompareView/CompareView.jsx";
import { rankCellLines } from "./api";
import styles from "./TestApp.module.css";

const DEFAULT_FILTERS = {
  w_rna: 0.7,
  w_protein: 0.3,
  mutation_mode: "ignore",
  fusion_mode: "ignore",
  disease_filter: null,
  lineage_filter: null,
  core_only: false,
  top_n: 20,
  sources: ["depmap", "hpa", "geo", "protein"],
};

const SCORING_METHODS = [
  { value: "rrf", label: "RRF Ensemble" },
  { value: "zscore", label: "Z-Score Only" },
  { value: "percentile", label: "Percentile Only" },
];

export default function TestApp() {
  /* Search state */
  const [genes, setGenes] = useState([]);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [scoringMethod, setScoringMethod] = useState("rrf");

  /* Results state */
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /* Selection & panels */
  const [selected, setSelected] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [showCompare, setShowCompare] = useState(false);

  /* Gene management */
  const addGene = useCallback((gene) => {
    setGenes((prev) => [...prev, gene]);
  }, []);

  const removeGene = useCallback((hugo) => {
    setGenes((prev) => prev.filter((g) => g.hugo !== hugo));
  }, []);

  /* Run ranking — passes scoring_method */
  async function handleSearch() {
    if (genes.length === 0) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setSelected([]);

    try {
      const res = await rankCellLines({
        genes: genes.map((g) => ({ hugo: g.hugo, direction: g.direction })),
        ...filters,
        scoring_method: scoringMethod,
      });
      setResults(res.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  /* Selection handlers */
  function handleToggleSelect(id) {
    if (id === "COMPARE") {
      setShowCompare(true);
      return;
    }
    if (id === "CLEAR") {
      setSelected([]);
      return;
    }
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function handleSelectAll(selectAll) {
    if (!results) return;
    setSelected(selectAll ? results.map((r) => r.ach_id) : []);
  }

  const methodLabel = SCORING_METHODS.find((m) => m.value === scoringMethod)?.label;

  return (
    <div className={styles.app}>
      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.logo}>
            Cell<span className={styles.logoAccent}>Line</span>Finder
          </div>
          <span className={styles.testBadge}>TEST MODE</span>
          <span className={styles.headerTag}>v2.0 · Bristol × AstraZeneca</span>
        </div>
        <div className={styles.headerRight}>
          <a className={styles.headerLink} href="/">← Back to Main App</a>
        </div>
      </header>

      <div className={styles.main}>
        {/* ── Left sidebar: Search Query ── */}
        <aside className={styles.sidebar}>
          <div className={styles.sidebarSection}>
            <h2 className={styles.sidebarTitle}>Search Query</h2>
            <SearchBar genes={genes} onAddGene={addGene} onRemoveGene={removeGene} />
          </div>

          {/* ── Scoring Method Toggle (TEST FEATURE) ── */}
          <div className={styles.sidebarSection}>
            <h2 className={styles.sidebarTitle}>
              Scoring Method <span className={styles.testTag}>TEST</span>
            </h2>
            <div className={styles.methodToggle}>
              {SCORING_METHODS.map((m) => (
                <button
                  key={m.value}
                  className={`${styles.methodBtn} ${scoringMethod === m.value ? styles.methodActive : ""}`}
                  onClick={() => setScoringMethod(m.value)}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <p className={styles.methodHint}>
              <b>RRF</b> = Z-Score + Percentile combined via Reciprocal Rank Fusion (default).
              <b> Z-Score</b> = standard deviations from mean only.
              <b> Percentile</b> = position in distribution only.
            </p>
          </div>

          <div className={styles.sidebarSection}>
            <FilterPanel filters={filters} onChange={setFilters} />
          </div>

          <div className={styles.sidebarSection}>
            <button
              className={styles.searchBtn}
              onClick={handleSearch}
              disabled={genes.length === 0 || loading}
            >
              {loading ? "Searching..." : "Find Cell Lines"}
            </button>
            {error && <div className={styles.error}>{error}</div>}
          </div>
        </aside>

        {/* ── Right content: Results ── */}
        <main className={styles.content}>
          {results && results.length > 0 && (
            <div className={styles.resultsHeader}>
              <h2 className={styles.resultsTitle}>
                Results
                <span className={`${styles.methodLabel} ${styles[`method_${scoringMethod}`]}`}>
                  {methodLabel}
                </span>
              </h2>
              <span className={styles.resultsMeta}>
                Showing <b>{results.length}</b> cell lines · Ranked by{" "}
                <b>{methodLabel}</b>
              </span>
            </div>
          )}

          {!results && !loading && (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>🔬</div>
              <div className={styles.emptyTitle}>Add genes to begin</div>
              <p className={styles.emptyText}>
                Search for target genes on the left, pick a scoring method, then click
                "Find Cell Lines" to rank cell lines by multi-omics expression.
              </p>
            </div>
          )}

          <ResultsTable
            results={results}
            loading={loading}
            selected={selected}
            onToggleSelect={handleToggleSelect}
            onSelectAll={handleSelectAll}
            onRowClick={setDetailId}
          />
        </main>
      </div>

      {/* Detail slide-in */}
      {detailId && (
        <DetailPanel
          achId={detailId}
          genes={genes}
          resultRow={results?.find((r) => r.ach_id === detailId)}
          scoringMethod={scoringMethod}
          onClose={() => setDetailId(null)}
        />
      )}

      {/* Compare modal */}
      {showCompare && (
        <CompareView
          achIds={selected}
          genes={genes}
          onClose={() => setShowCompare(false)}
        />
      )}
    </div>
  );
}
