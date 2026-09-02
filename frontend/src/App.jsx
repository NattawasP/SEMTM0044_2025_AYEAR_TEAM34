import { useState, useCallback, useMemo } from "react";
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
  driver_only: false,
  fusion_mode: "ignore",
  disease_filter: null,
  lineage_filter: null,
  subtype_filter: null,
  filter_mode: "filter",  // "filter" = hard exclude, "boost" = Q6 soft boost
  core_only: false,
  top_n: 20,
  sources: ["depmap", "hpa", "geo"],
  assay_type: null,
  msi_max: null,
  cin_max: null,
  exclude_metabolite: null,
  metabolite_threshold: null,
  exclude_mirna: null,
  mirna_threshold: null,
};

export default function App() {
  /* Search state */
  const [genes, setGenes] = useState([]);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  /* Results state */
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Snapshot of filters at the time of the last successful search — used to
  // detect when the current filters differ, so we can prompt the user to
  // refresh the results.
  const [lastSearchedFilters, setLastSearchedFilters] = useState(null);
  // Genes at the time of the last successful search — same purpose.
  const [lastSearchedGenes, setLastSearchedGenes] = useState(null);

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

  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
  }, []);

  /* Run ranking */
  async function handleSearch() {
    if (genes.length === 0) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setSelected([]);

    try {
      // Protein is always included in scoring (only the 3 RNA sources are
      // user-toggleable), so ensure "protein" is always in sources.
      const sourcesWithProtein = filters.sources.includes("protein")
        ? filters.sources
        : [...filters.sources, "protein"];

      // Route disease/lineage/subtype to filter or boost params based on mode
      const isBoost = filters.filter_mode === "boost";
      const apiParams = {
        genes: genes.map((g) => ({ hugo: g.hugo, direction: g.direction })),
        ...filters,
        sources: sourcesWithProtein,
        // In boost mode: clear hard filters, set Q6 targets
        disease_filter: isBoost ? null : filters.disease_filter,
        lineage_filter: isBoost ? null : filters.lineage_filter,
        subtype_filter: isBoost ? null : filters.subtype_filter,
        target_disease: isBoost ? filters.disease_filter : null,
        target_lineage: isBoost ? filters.lineage_filter : null,
        target_subtype: isBoost ? filters.subtype_filter : null,
        q6_boost_enabled: isBoost,
      };
      // filter_mode is frontend-only, don't send it
      delete apiParams.filter_mode;

      const res = await rankCellLines(apiParams);
      setResults(res.results);
      setLastSearchedFilters(filters);
      setLastSearchedGenes(genes);
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
    if (!displayedResults) return;
    setSelected(selectAll ? displayedResults.map((r) => r.ach_id) : []);
  }

  // Apply the "Driver only" filter on the client after ranking. Only active
  // when Mutation Filter = Include and Driver only is checked. Ranks are
  // recomputed so the displayed list is contiguous (1, 2, 3, ...).
  const displayedResults = useMemo(() => {
    if (!results) return null;
    const shouldFilter =
      filters.mutation_mode === "include" && filters.driver_only;
    if (!shouldFilter) return results;
    const filtered = results.filter(
      (r) => Array.isArray(r.mutations) && r.mutations.some((m) => m.is_driver)
    );
    return filtered.map((r, i) => ({ ...r, rank: i + 1 }));
  }, [results, filters.mutation_mode, filters.driver_only]);

  /* Highest score in the current results — used so the detail panel can colour
     its score with the same ratio-based thresholds as the results table. */
  const maxScore =
    displayedResults && displayedResults.length > 0
      ? Math.max(...displayedResults.map((r) => r.score))
      : 0;

  /* Detect pending changes: filters (or gene list) differ from the last search.
     driver_only is excluded because it filters live on the frontend and doesn't
     need a re-search. */
  const hasPendingChanges = useMemo(() => {
    if (!results || !lastSearchedFilters) return false;
    const stripDriverOnly = (f) => {
      const { driver_only, ...rest } = f;
      return rest;
    };
    const filtersChanged =
      JSON.stringify(stripDriverOnly(filters)) !==
      JSON.stringify(stripDriverOnly(lastSearchedFilters));
    const genesChanged =
      JSON.stringify(genes) !== JSON.stringify(lastSearchedGenes);
    return filtersChanged || genesChanged;
  }, [filters, lastSearchedFilters, genes, lastSearchedGenes, results]);

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
          {displayedResults && displayedResults.length > 0 && (
            <div className={styles.resultsHeader}>
              <h2 className={styles.resultsTitle}>Results</h2>
              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginLeft: "auto" }}>
                {hasPendingChanges && (
                  <span style={{ fontSize: "13px", color: "#f0b429", fontWeight: 500 }}>
                    Filters changed — refresh to update
                  </span>
                )}
                <button
                  onClick={handleSearch}
                  disabled={loading || genes.length === 0}
                  style={{
                    padding: "6px 14px",
                    fontSize: "13px",
                    borderRadius: "6px",
                    border: hasPendingChanges ? "1px solid #f0b429" : "1px solid #ccc",
                    background: hasPendingChanges ? "#fff8e6" : "#fff",
                    color: hasPendingChanges ? "#b8860b" : "#555",
                    cursor: loading ? "wait" : "pointer",
                    fontWeight: hasPendingChanges ? 600 : 400,
                  }}
                >
                  {loading ? "Refreshing..." : "↻ Refresh"}
                </button>
                <span className={styles.resultsMeta}>
                  Showing <b>{displayedResults.length}</b> cell lines · Ranked by{" "}
                  <b>Z-Score + Percentile RRF</b>
                </span>
              </div>
            </div>
          )}

          {/* Empty-state: a search was run but no cell lines matched. */}
          {results && (!displayedResults || displayedResults.length === 0) && !loading && (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>🔍</div>
              <div className={styles.emptyTitle}>No cell lines match your search criteria</div>
              {hasPendingChanges && (
                <button
                  onClick={handleSearch}
                  disabled={loading || genes.length === 0}
                  style={{
                    marginTop: "12px",
                    padding: "8px 16px",
                    fontSize: "13px",
                    borderRadius: "6px",
                    border: "1px solid #f0b429",
                    background: "#fff8e6",
                    color: "#b8860b",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  ↻ Refresh with current filters
                </button>
              )}
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

          <ResultsTable
            results={displayedResults}
            loading={loading}
            selected={selected}
            onToggleSelect={handleToggleSelect}
            onSelectAll={handleSelectAll}
            onRowClick={setDetailId}
            mutationMode={filters.mutation_mode}
            fusionMode={filters.fusion_mode}
            assayType={filters.assay_type}
            boostMode={filters.filter_mode === "boost"}
          />
        </main>
      </div>

      {/* Detail slide-in */}
      {detailId && (
        <DetailPanel
          achId={detailId}
          genes={genes}
          resultRow={displayedResults?.find((r) => r.ach_id === detailId)}
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
