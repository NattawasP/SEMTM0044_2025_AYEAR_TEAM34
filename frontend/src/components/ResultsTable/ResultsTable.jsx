import styles from "./ResultsTable.module.css";

export default function ResultsTable({
  results,
  loading,
  selected,
  onToggleSelect,
  onSelectAll,
  onRowClick,
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

  function rankBadgeClass(rank) {
    if (rank === 1) return styles.rank1;
    if (rank === 2) return styles.rank2;
    if (rank === 3) return styles.rank3;
    return styles.rankOther;
  }

  function scoreFillClass(ratio) {
    if (ratio >= 0.7) return styles.fillHigh;
    if (ratio >= 0.4) return styles.fillMid;
    return styles.fillLow;
  }

  function scenarioClass(scenario) {
    if (scenario.includes("RNA+Protein")) return styles.scenBoth;
    if (scenario.includes("RNA only")) return styles.scenRna;
    if (scenario.includes("Protein only")) return styles.scenProt;
    return "";
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
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const ratio = maxScore > 0 ? r.score / maxScore : 0;

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
                          className={`${styles.scoreFill} ${scoreFillClass(ratio)}`}
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
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}