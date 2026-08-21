import { useState, useEffect } from "react";
import { getCellLineEvidence } from "../../api";
import styles from "./DetailPanel.module.css";

export default function DetailPanel({ achId, genes, resultRow, scoringMethod = "rrf", maxScore = 0, wRna = 0.7, wProtein = 0.3, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!achId || genes.length === 0) return;
    setLoading(true);
    getCellLineEvidence(achId, genes, wRna, wProtein)
      .then(setData)
      .catch((err) => {
        console.error("Evidence fetch error:", err);
        setData(null);
      })
      .finally(() => setLoading(false));
  }, [achId, genes, wRna, wProtein]);

  if (!achId) return null;

  const score = resultRow?.score;
  const confidence = resultRow?.confidence;
  const scenario = resultRow?.scenario;

  // Colour the score using RAW score value (same thresholds as the results table).
  // Raw score gives a colour that reflects absolute quality, so it doesn't
  // mislead when the top result in a filtered list happens to have a low score.
  const scoreColor =
    score == null ? "#e05a4d"
    : score >= 0.7 ? "#2f9e6f"
    : score >= 0.4 ? "#f0b429"
    : "#e05a4d";

  // Per-source combined scores (w_rna*RNA_source + w_protein*Protein), same scale
  // as overall score. Keyed by display name: { DepMap: 0.89, HPA: 0.85, GEO: 0.82 }
  const sourceScores = data?.source_scores || {};

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* ── Header ── */}
        <div className={styles.header}>
          <div className={styles.headerInfo}>
            <h2 className={styles.title}>
              {data?.cell_line_name || resultRow?.cell_line_name || achId}
              <span className={styles.subtitle}>
                {" — Multi-Omics Evidence Breakdown"}
              </span>
            </h2>
            <span className={styles.achMeta}>
              {achId}
              {data?.primary_disease && ` · ${data.primary_disease}`}
              {data?.lineage && ` · ${data.lineage}`}
              {data?.sex && ` · ${data.sex}`}
              {data?.growth_pattern && ` · ${data.growth_pattern}`}
            </span>
          </div>
          <div className={styles.headerRight}>
            {score != null && (
              <div className={styles.detailScore} style={{ background: scoreColor }}>{score.toFixed(2)}</div>
            )}
            <button className={styles.closeBtn} onClick={onClose}>×</button>
          </div>
        </div>

        {loading ? (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            Computing evidence breakdown...
          </div>
        ) : !data ? (
          <div className={styles.loading}>No evidence data available</div>
        ) : (
          <div className={styles.body}>
            {/* ── Per-gene expression cards ── */}
            <div className={styles.geneCards}>
              {genes.map((g) => {
                const gd = data.genes?.[g.hugo];
                if (!gd) return null;
                const dirLabel = gd.direction === "high" ? "HIGH ↑" : "LOW ↓";
                const dirClass = gd.direction === "high" ? styles.dirHigh : styles.dirLow;
                return (
                  <div key={g.hugo} className={styles.geneCard}>
                    <div className={styles.geneCardHeader}>
                      <span className={styles.geneCardLabel}>
                        {g.hugo} Expression
                      </span>
                      <span className={`${styles.dirBadge} ${dirClass}`}>
                        {dirLabel}
                      </span>
                    </div>
                    {gd.expression_rank == null && (
                      <div className={styles.geneCardRank}>No expression data</div>
                    )}
                    <div className={styles.geneCardSub}>
                      {scoringMethod === "rrf"
                        ? `RRF ensemble across ${gd.source_count} source${gd.source_count !== 1 ? "s" : ""} × 2 methods`
                        : scoringMethod === "zscore"
                        ? `Z-Score ranking across ${gd.source_count} source${gd.source_count !== 1 ? "s" : ""}`
                        : `Percentile ranking across ${gd.source_count} source${gd.source_count !== 1 ? "s" : ""}`}
                    </div>
                    <div className={styles.geneCardSub}>
                      Sources:{" "}
                      {["DepMap", "HPA", "GEO"].map((src) => {
                        const has = gd.sources.some((s) => s.source === src);
                        return (
                          <span key={src} className={has ? styles.srcYes : styles.srcNo}>
                            {src} {has ? "✓" : "✗"}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })}

              {/* Protein summary card — always shown */}
              <div className={styles.geneCard}>
                <div className={styles.geneCardHeader}>
                  <span className={styles.geneCardLabel}>Protein Detection</span>
                </div>
                {data.protein ? (
                  <>
                    <div className={styles.geneCardRank}>
                      Rank #{data.protein.z_rank}{" "}
                      <span className={styles.rankTotal}>/ {data.protein.total?.toLocaleString()}</span>
                    </div>
                    <div className={styles.geneCardSub}>
                      {genes[0]?.hugo}: Intensity {data.protein.intensity} · Gygi proteomics
                    </div>
                    <div className={`${styles.geneCardSub} ${styles.proteinConfirm}`}>
                      Confirmed at protein level ✓
                    </div>
                  </>
                ) : (
                  <>
                    <div className={styles.geneCardRank}>No protein data</div>
                    <div className={styles.geneCardSub}>
                      {genes[0]?.hugo}: not detected in Gygi proteomics
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* ── Source-Level Scores per gene ── */}
            {genes.map((g) => {
              const gd = data.genes?.[g.hugo];
              if (!gd || gd.sources.length === 0) return null;
              return (
                <div key={g.hugo} className={styles.sourceSection}>
                  <h4 className={styles.sectionLabel}>
                    Source-Level Scores — {g.hugo}
                  </h4>
                  <div className={styles.sourceGrid}>
                    {gd.sources.map((src) => {
                      const combined = sourceScores[src.source];
                      return (
                        <div key={src.source} className={styles.sourceCard}>
                          <h5 className={styles.sourceTitle}>{src.source}</h5>
                          <div className={styles.sourceRow}>
                            <span>TPM</span>
                            <span className={styles.val}>{src.tpm}</span>
                          </div>
                          {(scoringMethod === "rrf" || scoringMethod === "zscore") && (
                            <div className={styles.sourceRow}>
                              <span>Z-Score</span>
                              <span className={styles.val}>
                                {src.z_score > 0 ? "+" : ""}{src.z_score}
                              </span>
                            </div>
                          )}
                          {(scoringMethod === "rrf" || scoringMethod === "percentile") && (
                            <div className={styles.sourceRow}>
                              <span>Percentile</span>
                              <span className={styles.val}>{src.percentile}%</span>
                            </div>
                          )}
                          {(scoringMethod === "rrf" || scoringMethod === "zscore") && (
                            <div className={styles.sourceRow}>
                              <span>Z-Score Rank</span>
                              <span className={styles.val}>#{src.z_rank}</span>
                            </div>
                          )}
                          {(scoringMethod === "rrf" || scoringMethod === "percentile") && (
                            <div className={styles.sourceRow}>
                              <span>Percentile Rank</span>
                              <span className={styles.val}>#{src.pct_rank}</span>
                            </div>
                          )}
                          {combined != null && (
                            <div className={`${styles.sourceRow} ${styles.sourceScoreRow}`}>
                              <span>Score</span>
                              <span className={styles.val}>{combined.toFixed(4)}</span>
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {/* Protein source card — always shown */}
                    <div className={styles.sourceCard}>
                      <h5 className={styles.sourceTitle}>Protein (Gygi)</h5>
                      {data.protein ? (
                        <>
                          <div className={styles.sourceRow}>
                            <span>Intensity</span>
                            <span className={styles.val}>{data.protein.intensity}</span>
                          </div>
                          {(scoringMethod === "rrf" || scoringMethod === "zscore") && (
                            <div className={styles.sourceRow}>
                              <span>Z-Score</span>
                              <span className={styles.val}>
                                {data.protein.z_score > 0 ? "+" : ""}{data.protein.z_score}
                              </span>
                            </div>
                          )}
                          {(scoringMethod === "rrf" || scoringMethod === "percentile") && (
                            <div className={styles.sourceRow}>
                              <span>Percentile</span>
                              <span className={styles.val}>{data.protein.percentile}%</span>
                            </div>
                          )}
                          {(scoringMethod === "rrf" || scoringMethod === "zscore") && (
                            <div className={styles.sourceRow}>
                              <span>Z-Score Rank</span>
                              <span className={styles.val}>#{data.protein.z_rank}</span>
                            </div>
                          )}
                          {(scoringMethod === "rrf" || scoringMethod === "percentile") && (
                            <div className={styles.sourceRow}>
                              <span>Percentile Rank</span>
                              <span className={styles.val}>#{data.protein.pct_rank}</span>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className={styles.sourceRow}>
                          <span>No protein data</span>
                          <span className={styles.val}>—</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* ── Mutation detail ── */}
            {data.mutations && data.mutations.length > 0 && (
              <div className={styles.sourceSection}>
                <h4 className={styles.sectionLabel}>
                  Mutations in {genes.map((g) => g.hugo).join(", ")}
                </h4>
                <div className={styles.mutTableWrap}>
                  <table className={styles.mutTable}>
                    <thead>
                      <tr>
                        <th>Variant</th>
                        <th>Type</th>
                        <th>Protein</th>
                        <th className={styles.thCenter}>Driver</th>
                        <th className={styles.thCenter}>Hotspot</th>
                        <th className={styles.thCenter}>Damaging</th>
                        <th className={styles.thCenter}>Loss of function</th>
                        <th className={styles.thCenter}>Mutation %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.mutations.map((m, i) => (
                        <tr key={i}>
                          <td className={styles.mono}>
                            {m.chrom}:{m.pos} {m.ref}→{m.alt}
                          </td>
                          <td>{m.variant_type || "—"}</td>
                          <td className={styles.proteinChange}>
                            {m.protein_change || "—"}
                          </td>
                          <td className={styles.tdCenter}>
                            <span className={`${styles.pill} ${m.is_driver ? styles.pillPass : styles.pillFail}`}>
                              {m.is_driver ? "Yes" : "No"}
                            </span>
                          </td>
                          <td className={styles.tdCenter}>
                            <span className={`${styles.pill} ${m.is_hotspot ? styles.pillPass : styles.pillFail}`}>
                              {m.is_hotspot ? "Yes" : "No"}
                            </span>
                          </td>
                          <td className={styles.tdCenter}>
                            <span className={`${styles.pill} ${m.is_damaging ? styles.pillPass : styles.pillFail}`}>
                              {m.is_damaging ? "Yes" : "No"}
                            </span>
                          </td>
                          <td className={styles.tdCenter}>
                            <span className={`${styles.pill} ${m.is_lof ? styles.pillPass : styles.pillFail}`}>
                              {m.is_lof ? "Yes" : "No"}
                            </span>
                          </td>
                          <td className={styles.tdCenter}>
                            {m.allele_freq != null
                              ? `${(m.allele_freq * 100).toFixed(1)}%`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── Fusions ── */}
            {data.fusions && data.fusions.length > 0 && (
              <div className={styles.sourceSection}>
                <h4 className={styles.sectionLabel}>
                  Fusions ({data.fusions.length})
                </h4>
                <div className={styles.mutTableWrap}>
                  <table className={styles.mutTable}>
                    <thead>
                      <tr>
                        <th>Fusion</th>
                        <th>Confidence</th>
                        <th>Frame</th>
                        <th>Fusion Fragments (per million)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.fusions.map((f, i) => (
                        <tr key={i}>
                          <td className={styles.mono}>
                            {f.fusion_name || `${f.gene1_hugo}—${f.gene2_hugo}`}
                          </td>
                          <td>{f.confidence}</td>
                          <td>{f.reading_frame || "—"}</td>
                          <td>{f.ffpm != null ? f.ffpm.toFixed(3) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── Scoring method info ── */}
            <div className={styles.methodInfo}>
              <h4 className={styles.methodTitle}>Scoring Method</h4>
              <p className={styles.methodText}>
                {scoringMethod === "rrf" && (
                  <>Expression ranked via <code>Z-Score</code> + <code>Percentile</code> per source (DepMap, HPA, GEO), combined with <code>Reciprocal Rank Fusion</code> (k=60).</>
                )}
                {scoringMethod === "zscore" && (
                  <>Expression ranked via <code>Z-Score</code> only per source (DepMap, HPA, GEO), combined with <code>Reciprocal Rank Fusion</code> (k=60).</>
                )}
                {scoringMethod === "percentile" && (
                  <>Expression ranked via <code>Percentile</code> only per source (DepMap, HPA, GEO), combined with <code>Reciprocal Rank Fusion</code> (k=60).</>
                )}
                {data.protein && (
                  <> Protein scored separately, combined with RNA at the selected weighting.</>
                )}
                {genes.length > 1 && (
                  <> Multi-gene combination via RRF across gene-specific ranks.</>
                )}
                {" "}Per-source scores use the selected RNA/Protein weights on the
                same scale as the overall score.
              </p>
            </div>

            {/* ── Data coverage bar ── */}
            <div className={styles.omicsBar}>
              <div>
                <span className={styles.omicsLabel}>Data Coverage</span>
                <br />
                <span className={styles.omicsText}>
                  RNA-seq ({data.data_coverage.rna_sources}/3 sources)
                  {data.data_coverage.has_protein && " · Proteomics"}
                  {data.data_coverage.has_mutations && " · Mutations"}
                  {data.data_coverage.has_fusions && " · Fusions"}
                </span>
              </div>
              <span className={styles.omicsCount}>
                {data.data_coverage.total_types}/{data.data_coverage.max_types} DATA TYPES
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
