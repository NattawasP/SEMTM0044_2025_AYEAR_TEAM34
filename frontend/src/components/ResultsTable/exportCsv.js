// Builds a CSV of the current ranked results and hands it to the browser as a
// download. The query parameters are written as comment rows above the table so
// the file is self-describing: a colleague opening it can see which query
// produced the ranking without needing the session that ran it.

// CSV values must be quoted if they contain a comma, a double quote or a
// newline, and any embedded quote must be doubled. Anything else is written
// bare. Null and undefined become an empty cell rather than the strings
// "null" or "undefined".
function csvCell(value) {
  if (value === null || value === undefined) return "";
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// A cell line can carry several mutations. The table shows a count; the export
// writes them out, since the point of exporting is to keep the evidence.
// Driver status is marked inline because it is the field a reader scans for.
function mutationsToText(mutations) {
  if (!mutations || mutations.length === 0) return "";
  return mutations
    .map((m) => {
      const change = m.protein_change || m.variant_info || "unknown";
      return m.is_driver ? `${change} (driver)` : change;
    })
    .join("; ");
}

// Same idea for fusions. Reading frame is included because an out-of-frame call
// is much weaker evidence than an in-frame one, and that distinction is
// invisible from the fusion name alone.
function fusionsToText(fusions) {
  if (!fusions || fusions.length === 0) return "";
  return fusions
    .map((f) => {
      const name = f.fusion_name || `${f.gene1_hugo}--${f.gene2_hugo}`;
      return `${name} [${f.reading_frame || "frame unknown"}]`;
    })
    .join("; ");
}

// Turns the server's echo of the query into one comment row per parameter.
// Empty and unset parameters are dropped so the header shows what was actually
// applied rather than the whole schema. Arrays and nested objects are flattened
// so a multi-gene query still reads on one line.
function queryToRows(query) {
  if (!query) return [];
  return Object.entries(query)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([key, value]) => {
      let text;
      if (Array.isArray(value)) {
        text = value
          .map((v) => (typeof v === "object" ? JSON.stringify(v) : v))
          .join(" | ");
      } else if (typeof value === "object") {
        text = JSON.stringify(value);
      } else {
        text = value;
      }
      return `# ${key}: ${text}`;
    });
}

// Column order for the exported table. Each entry pairs a header name with a
// function that pulls that value off a result row, so adding a column is a
// one-line change and the header can never drift out of step with the data
// beneath it. Scores are written to six decimal places rather than the four
// shown on screen, because the export is what someone would reuse.
const COLUMNS = [
  ["rank", (r) => r.rank],
  ["ach_id", (r) => r.ach_id],
  ["cell_line_name", (r) => r.cell_line_name],
  ["primary_disease", (r) => r.primary_disease],
  ["lineage", (r) => r.lineage],
  ["score", (r) => (typeof r.score === "number" ? r.score.toFixed(6) : "")],
  ["confidence", (r) => (typeof r.confidence === "number" ? r.confidence.toFixed(6) : "")],
  ["scenario", (r) => r.scenario],
  ["growth_pattern", (r) => r.growth_pattern],
  ["mutations", (r) => mutationsToText(r.mutations)],
  ["fusions", (r) => fusionsToText(r.fusions)],
];

// Assembles the whole file as one string: comment header, blank separator,
// column names, then one row per cell line. Rows are joined with CRLF, which is
// what the CSV convention specifies and what Excel expects.
export function buildCsv(results, query) {
  const lines = [];
  lines.push("# CellLineFinder ranked results");
  lines.push(`# Exported: ${new Date().toISOString()}`);
  lines.push(`# Results: ${results.length}`);
  lines.push(...queryToRows(query));
  lines.push("");
  lines.push(COLUMNS.map(([name]) => name).join(","));
  for (const row of results) {
    lines.push(COLUMNS.map(([, get]) => csvCell(get(row))).join(","));
  }
  return lines.join("\r\n");
}

// Wraps the string in a Blob, points a temporary anchor at it and clicks it.
// The ﻿ byte-order mark makes Excel on Windows read the file as UTF-8
// instead of the local codepage. The object URL is revoked afterwards so the
// blob does not sit in memory for the rest of the session.
export function downloadCsv(results, query, filename) {
  const csv = buildCsv(results, query);
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download =
    filename || `celllinefinder_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
