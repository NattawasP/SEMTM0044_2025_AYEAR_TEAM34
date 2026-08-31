import { useState, useCallback, useRef } from "react";
import SearchBar from "./components/SearchBar/SearchBar.jsx";
import FilterPanel from "./components/FilterPanel/FilterPanel.jsx";
import ResultsTable from "./components/ResultsTable/ResultsTable.jsx";
import DetailPanel from "./components/DetailPanel/DetailPanel.jsx";
import CompareView from "./components/CompareView/CompareView.jsx";
import ChatWidget from "./components/ChatWidget/ChatWidget.jsx";
import { rankCellLines } from "./api";
import styles from "./App.module.css";

const DEFAULT_FILTERS = {
  w_rna: 0.7,
  w_protein: 0.3,
  mutation_mode: "ignore",
  fusion_mode: "ignore",
  disease_filter: null,
  lineage_filter: null,
  core_only: false,
  top_n: 20,
  sources: ["depmap", "hpa", "geo"],
};

export default function App() {
  /* Search state */
  const [genes, setGenes] = useState([]);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  /* Results state */
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /* Stale-results tracking: true when genes/filters changed since last search */
  const [stale, setStale] = useState(false);
  const hasSearched = useRef(false);

  /* Selection & panels */
  const [selected, setSelected] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [showCompare, setShowCompare] = useState(false);

  /* Gene management */
  const addGene = useCallback((gene) => {
    setGenes((prev) => [...prev, gene]);
    if (hasSearched.current) setStale(true);
  }, []);

  const removeGene = useCallback((hugo) => {
    setGenes((prev) => prev.filter((g) => g.hugo !== hugo));
    if (hasSearched.current) setStale(true);
  }, []);

  /* Wrap filter changes to also mark stale */
  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
    if (hasSearched.current) setStale(true);
  }, []);

  /* Run ranking */
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
      });
      setResults(res.results);
      hasSearched.current = true;
      setStale(false);
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

  /* Highest score in the current results — used so the detail panel can colour
     its score with the same ratio-based thresholds as the results table. */
  const maxScore =
    results && results.length > 0
      ? Math.max(...results.map((r) => r.score))
      : 0;

  return (
    <div className={styles.app}>
      {/* ── Header ── */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.logo}>
            Cell<span className={styles.logoAccent}>Line</span>Finder
          </div>
          <span className={styles.headerTag}>v2.0 · Bristol × AstraZeneca</span>
        </div>
        <div className={styles.headerRight}>
          <a className={styles.headerLink} href="#">Documentation</a>
          <a className={styles.headerLink} href="#">Data Sources</a>
          <a className={styles.headerLink} href="#">Methods</a>
          <a className={styles.headerLink} href="#">About</a>
        </div>
      </header>

      <div className={styles.main}>
        {/* ── Left sidebar: Search Query ── */}
        <aside className={styles.sidebar}>
          <div className={styles.sidebarSection}>
            <h2 className={styles.sidebarTitle}>Search Query</h2>
            <SearchBar genes={genes} onAddGene={addGene} onRemoveGene={removeGene} />
          </div>

          <div className={styles.sidebarSection}>
            <FilterPanel filters={filters} onChange={handleFilterChange} />
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
              <h2 className={styles.resultsTitle}>Results</h2>
              <span className={styles.resultsMeta}>
                Showing <b>{results.length}</b> cell lines · Ranked by{" "}
                <b>Z-Score + Percentile RRF</b>
              </span>
            </div>
          )}

          {!results && !loading && (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>🔬</div>
              <div className={styles.emptyTitle}>Add genes to begin</div>
              <p className={styles.emptyText}>
                Search for target genes on the left, set your filters, then click
                "Find Cell Lines" to rank cell lines by multi-omics expression.
              </p>
            </div>
          )}

          {stale && results && (
            <div className={styles.staleBanner}>
              Search parameters changed — click <b>Find Cell Lines</b> to update results.
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
          maxScore={maxScore}
          wRna={filters.w_rna}
          wProtein={filters.w_protein}
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

      {/* Chat widget */}
      <ChatWidget />
    </div>
  );
}
