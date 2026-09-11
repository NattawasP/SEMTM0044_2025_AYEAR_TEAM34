/**
 * Export ranking results to a downloadable CSV file.
 *
 * The CSV includes:
 *  - A metadata header block with the query parameters (genes, filters, weights, date)
 *  - A data table with all columns from the results, including conditional columns
 *    (mutations, fusions, assay, tissue match) when relevant filters were active.
 */

function escapeCsv(value) {
  if (value == null) return "";
  const str = String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildRow(values) {
  return values.map(escapeCsv).join(",");
}

/**
 * @param {Object} opts
 * @param {Array}  opts.results        - The displayed (possibly driver-filtered) results array
 * @param {Array}  opts.genes          - Array of { hugo, direction }
 * @param {Object} opts.filters        - Current filter state from App
 */
export function exportResultsCsv({ results, genes, filters }) {
  if (!results || results.length === 0) return;

  const lines = [];
  const now = new Date();

  // ── Metadata header ──────────────────────────────────────
  lines.push("# CellLineFinder Export");
  lines.push(`# Date: ${now.toISOString()}`);
  lines.push(
    `# Genes: ${genes.map((g) => `${g.hugo} (${g.direction})`).join("; ")}`
  );
  lines.push(`# RNA weight: ${filters.w_rna}  Protein weight: ${filters.w_protein}`);
  lines.push(`# Sources: ${(filters.sources || ["depmap", "hpa", "geo"]).join(", ")}`);

  if (filters.disease_filter) lines.push(`# Disease filter: ${filters.disease_filter}`);
  if (filters.lineage_filter) lines.push(`# Lineage filter: ${filters.lineage_filter}`);
  if (filters.subtype_filter) lines.push(`# Subtype filter: ${filters.subtype_filter}`);
  if (filters.filter_mode === "boost") {
    lines.push("# Mode: Soft boost (Q6)");
    if (filters.disease_filter) lines.push(`# Target disease: ${filters.disease_filter}`);
    if (filters.lineage_filter) lines.push(`# Target lineage: ${filters.lineage_filter}`);
    if (filters.subtype_filter) lines.push(`# Target subtype: ${filters.subtype_filter}`);
  }
  lines.push(`# Mutation filter: ${filters.mutation_mode}`);
  lines.push(`# Fusion filter: ${filters.fusion_mode}`);
  if (filters.assay_type) lines.push(`# Assay type: ${filters.assay_type}`);
  if (filters.msi_max != null) lines.push(`# MSI max: ${filters.msi_max}`);
  if (filters.cin_max != null) lines.push(`# CIN max: ${filters.cin_max}`);
  if (filters.exclude_metabolite) {
    lines.push(`# Exclude metabolite: ${filters.exclude_metabolite} > ${filters.metabolite_threshold}`);
  }
  if (filters.exclude_mirna) {
    lines.push(`# Exclude miRNA: ${filters.exclude_mirna} > ${filters.mirna_threshold}`);
  }
  if (filters.core_only) lines.push("# Core only: yes");
  lines.push(`# Top N: ${filters.top_n}`);
  lines.push("#");

  // ── Determine which conditional columns to include ───────
  const showMutation = filters.mutation_mode === "include";
  const showFusion = filters.fusion_mode === "include";
  const showAssay = !!filters.assay_type;
  const showBoost = filters.filter_mode === "boost";
  const isMultiGene = genes.length > 1;

  // ── Column headers ───────────────────────────────────────
  const headers = [
    "Rank",
    "Cell Line",
    "ACH ID",
    "Disease",
    "Lineage",
    "Score",
    "Scenario",
  ];

  if (showBoost) {
    headers.push("Base Score", "Match Level", "Q6 Score");
  }
  if (isMultiGene) {
    genes.forEach((g) => headers.push(`${g.hugo} Rank`));
  }
  if (showMutation) headers.push("Mutations");
  if (showFusion) headers.push("Fusions");
  if (showAssay) headers.push("Assay Status", "Assay Warning");

  lines.push(buildRow(headers));

  // ── Data rows ────────────────────────────────────────────
  for (const r of results) {
    const row = [
      r.rank,
      r.cell_line_name || "",
      r.ach_id,
      r.primary_disease || "",
      r.lineage || "",
      r.score?.toFixed(4) ?? "",
      r.scenario || "",
    ];

    if (showBoost) {
      row.push(
        r.base_score?.toFixed(4) ?? "",
        r.match_level || "",
        r.q6_score?.toFixed(2) ?? ""
      );
    }

    if (isMultiGene) {
      genes.forEach((g) => {
        row.push(r.per_gene_rank?.[g.hugo] ?? "");
      });
    }

    if (showMutation) {
      const muts = r.mutations || [];
      const summary = muts
        .map((m) => {
          const parts = [m.protein_change || m.variant_type || "variant"];
          if (m.is_driver) parts.push("driver");
          if (m.is_hotspot) parts.push("hotspot");
          return parts.join("/");
        })
        .join("; ");
      row.push(summary || "none");
    }

    if (showFusion) {
      const fus = r.fusions || [];
      const summary = fus
        .map((f) => `${f.fusion_name || `${f.gene1_hugo}--${f.gene2_hugo}`} (${f.confidence || "?"})`)
        .join("; ");
      row.push(summary || "none");
    }

    if (showAssay) {
      row.push(r.q7_status || "", r.q7_warning || "");
    }

    lines.push(buildRow(row));
  }

  // ── Trigger download ─────────────────────────────────────
  const geneStr = genes.map((g) => g.hugo).join("_");
  const dateStr = now.toISOString().slice(0, 10);
  const filename = `celllinefinder_${geneStr}_${dateStr}.csv`;

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
