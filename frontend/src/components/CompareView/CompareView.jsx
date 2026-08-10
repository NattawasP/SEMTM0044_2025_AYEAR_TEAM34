import { useState, useEffect } from "react";
import { compareCellLines } from "../../api";
import styles from "./CompareView.module.css";

export default function CompareView({ achIds, genes, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeGene, setActiveGene] = useState(genes[0]?.hugo || "");

  useEffect(() => {
    if (!achIds || achIds.length < 2 || !activeGene) return;
    setLoading(true);
    compareCellLines(achIds, activeGene)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [achIds, activeGene]);

  if (!achIds || achIds.length < 2) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>Compare Cell Lines</h2>
          <button className={styles.closeBtn} onClick={onClose}>
            ×
          </button>
        </div>

        {/* Gene tabs */}
        {genes.length > 1 && (
          <div className={styles.geneTabs}>
            {genes.map((g) => (
              <button
                key={g.hugo}
                className={`${styles.geneTab} ${activeGene === g.hugo ? styles.geneTabActive : ""}`}
                onClick={() => setActiveGene(g.hugo)}
              >
                {g.hugo}
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <div className={styles.loading}>Loading comparison...</div>
        ) : !data || !data.comparisons ? (
          <div className={styles.loading}>No data available</div>
        ) : (
          <div className={styles.content}>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th className={styles.metricCol}>Metric</th>
                    {data.comparisons.map((c) => (
                      <th key={c.ach_id}>
                        <div className={styles.clName}>{c.cell_line_name || c.ach_id}</div>
                        <div className={styles.clId}>{c.ach_id}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Disease */}
                  <tr>
                    <td className={styles.metricLabel}>Disease</td>
                    {data.comparisons.map((c) => (
                      <td key={c.ach_id}>{c.primary_disease || "—"}</td>
                    ))}
                  </tr>

                  {/* Lineage */}
                  <tr>
                    <td className={styles.metricLabel}>Lineage</td>
                    {data.comparisons.map((c) => (
                      <td key={c.ach_id}>{c.lineage || "—"}</td>
                    ))}
                  </tr>

                  {/* Expression per source */}
                  {["DepMap", "HPA", "GEO"].map((src) => {
                    const vals = data.comparisons.map((c) => {
                      const match = (c.expression_sources || []).find((s) => s.source === src);
                      return match ? match.tpm : null;
                    });
                    const maxVal = Math.max(...vals.filter((v) => v !== null));

                    return (
                      <tr key={src}>
                        <td className={styles.metricLabel}>{src} TPM</td>
                        {vals.map((v, i) => (
                          <td
                            key={data.comparisons[i].ach_id}
                            className={v !== null && v === maxVal ? styles.bestVal : ""}
                          >
                            {v !== null ? v.toFixed(2) : "—"}
                          </td>
                        ))}
                      </tr>
                    );
                  })}

                  {/* Protein */}
                  {(() => {
                    const vals = data.comparisons.map((c) => c.protein_intensity);
                    const maxVal = Math.max(...vals.filter((v) => v !== null));
                    return (
                      <tr>
                        <td className={styles.metricLabel}>Protein Intensity</td>
                        {vals.map((v, i) => (
                          <td
                            key={data.comparisons[i].ach_id}
                            className={v !== null && v === maxVal ? styles.bestVal : ""}
                          >
                            {v !== null ? v.toFixed(4) : "—"}
                          </td>
                        ))}
                      </tr>
                    );
                  })()}

                  {/* Mutation count */}
                  <tr>
                    <td className={styles.metricLabel}>Mutations</td>
                    {data.comparisons.map((c) => (
                      <td key={c.ach_id}>{(c.mutations || []).length}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
