import styles from "./ResultsTable.module.css";

export default function ResultsTable({
  results,
  loading,
  selected,
  onToggleSelect,
  onSelectAll,
  onRowClick,
  mutationMode = "ignore",
  fusionMode = "ignore",
}) {
  if (loading) {
    return (
      <div className={styles.loading}>
        <div className={styles.spinner} />
        <p>Ranking cell lines...</p>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return null;
  }

  const allSelected = results.every((r) => selected.includes(r.ach_id));
  const maxScore = Math.max(...results.map((r) => r.score));

  // Mutation column only shows when the user has actively filtered for
  // cell lines with mutations (Include). Ignore/Exclude keep the table clean.
  const showMutationColumn = mutationMode === "include";
  const showFusionColumn = fusionMode === "include";

  function rankBadgeClass(rank) {
    if (rank === 1) return styles.rank1;
    if (rank === 2) return styles.rank2;
    if (rank === 3) return styles.rank3;
    return styles.rankOther;
  }

  function scoreFillClass(score) {
    if (score >= 0.7) return styles.fillHigh;
    if (score >= 0.4) return styles.fillMid;
    return styles.fillLow;
  }

  function scenarioClass(scenario) {
    if (scenario.includes("RNA+Protein")) return styles.scenBoth;
    if (scenario.includes("RNA only")) return styles.scenRna;
    if (scenario.includes("Protein only")) return styles.scenProt;
    return "";
  }

  // Summarise a cell line's mutations for the results table:
  //   "3 mutations · has driver"  (if any mutation has is_driver = true)
  //   "3 mutations"               (otherwise)
  // The full per-variant table is shown in the detail panel on click.
  function mutationSummary(mutations) {
    if (!mutations || mutations.length === 0) return null;
    const count = mutations.length;
    const hasDriver = mutations.some((m) => m.is_driver);
    const label = `${count} mutation${count !== 1 ? "s" : ""}`;
    return hasDriver ? `${label} · has driver` : label;
  }

  // Summarise a cell line's fusions for the results table:
  //   "SEC61G-DT +2 more"   (shows the partner gene(s), not the searched gene)
  //   "SEC61G-DT"           (single partner)
  // For each fusion, the "partner" is whichever gene is NOT the one the user
  // searched for. Duplicates are removed so a fusion listed twice (different
  // transcript variants) counts as one partner.
  function fusionSummary(fusions) {
    if (!fusions || fusions.length === 0) return null;
    // Collect unique partner genes across all fusions in this cell line.
    // "Partner" = the gene in the fusion that isn't the one the user searched.
    // We treat any searched gene as "self" and pick the other side.
    const searchedGenes = new Set(); // built below from all fusions themselves
    // Fallback: figure out searched genes by seeing which gene appears on
    // both sides across many fusions in this cell line — but simpler and
    // correct is to use the fact that a "partner" is whichever gene name
    // wasn't the searched one. We don't have the search query here, so
    // instead derive it: if the same gene appears in every fusion, it's the
    // searched one.
    const gene1Set = new Set(fusions.map((f) => f.gene1_hugo));
    const gene2Set = new Set(fusions.map((f) => f.gene2_hugo));
    // If every fusion has the same gene on side 1 → that's the searched gene
    // and partners come from gene2. Same for side 2. Otherwise fall back to
    // showing the fusion_name.
    const commonG1 = gene1Set.size === 1 ? [...gene1Set][0] : null;
    const commonG2 = gene2Set.size === 1 ? [...gene2Set][0] : null;

    let partners;
    if (commonG1 && !commonG2) {
      partners = [...new Set(fusions.map((f) => f.gene2_hugo))];
    } else if (commonG2 && !commonG1) {
      partners = [...new Set(fusions.map((f) => f.gene1_hugo))];
    } else if (commonG1 && commonG2) {
      // Only one distinct fusion pair — pick the "other" side arbitrarily
      partners = [commonG2];
    } else {
      // Mixed — pick each partner as the one that differs across fusions
      partners = [
        ...new Set(
          fusions.map((f) =>
            gene1Set.size < gene2Set.size ? f.gene2_hugo : f.gene1_hugo
          )
        ),
      ];
    }

    if (partners.length === 0) return null;
    const first = partners[0];
    const rest = partners.length - 1;
    return rest > 0 ? `${first} +${rest} more` : first;
  }

  return (
    <div className={styles.wrapper}>
      {/* Compare bar — shows when 2+ selected */}
      {selected.length >= 2 && (
        <div className={styles.compareBar}>
          <span>
            <span style={{ color: "#f0b429" }}>{selected.length}</span> cell lines selected
          </span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button className={styles.compareBtn} onClick={() => onToggleSelect("COMPARE")}>
              Compare Selected
            </button>
            <button className={styles.clearBtn} onClick={() => onToggleSelect("CLEAR")}>
              Clear
            </button>
          </div>
        </div>
      )}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.thCheck}>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={() => onSelectAll(!allSelected)}
                  style={{ accentColor: "#f0b429" }}
                />
              </th>
              <th className={styles.thRank}>Rank</th>
              <th>Cell Line</th>
              <th>Disease</th>
              <th>Score</th>
              <th>Scenario</th>
              {showMutationColumn && <th>Mutation</th>}
              {showFusionColumn && <th>Fusion</th>}
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const ratio = maxScore > 0 ? r.score / maxScore : 0;
              const mutText = showMutationColumn ? mutationSummary(r.mutations) : null;
              const fusText = showFusionColumn ? fusionSummary(r.fusions) : null;

              return (
                <tr
                  key={r.ach_id}
                  className={`${styles.row} ${selected.includes(r.ach_id) ? styles.rowSelected : ""}`}
                  onClick={() => onRowClick(r.ach_id)}
                >
                  <td className={styles.tdCheck} onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(r.ach_id)}
                      onChange={() => onToggleSelect(r.ach_id)}
                    />
                  </td>
                  <td className={styles.rank}>
                    <div className={`${styles.rankBadge} ${rankBadgeClass(r.rank)}`}>
                      {r.rank}
                    </div>
                  </td>
                  <td>
                    <div className={styles.cellName}>{r.cell_line_name || r.ach_id}</div>
                    <div className={styles.achId}>{r.ach_id}</div>
                  </td>
                  <td className={styles.disease}>{r.primary_disease || "—"}</td>
                  <td>
                    <div className={styles.scoreCell}>
                      <div className={styles.scoreBar}>
                        <div
                          className={`${styles.scoreFill} ${scoreFillClass(r.score)}`}
                          style={{ width: `${ratio * 100}%` }}
                        />
                      </div>
                      <span className={styles.scoreVal}>{r.score.toFixed(4)}</span>
                    </div>
                  </td>
                  <td>
                    <span className={`${styles.scenTag} ${scenarioClass(r.scenario)}`}>
                      {r.scenario}
                    </span>
                  </td>
                  {showMutationColumn && (
                    <td style={{ fontSize: "12px", color: "#555" }}>
                      {mutText || <span style={{ color: "#bbb" }}>—</span>}
                    </td>
                  )}
                  {showFusionColumn && (
                    <td style={{ fontSize: "12px", color: "#555" }}>
                      {fusText || <span style={{ color: "#bbb" }}>—</span>}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
