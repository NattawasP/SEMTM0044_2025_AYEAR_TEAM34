/**
 * API service layer — all fetch calls to the FastAPI backend.
 * In dev, Vite proxies /api → http://localhost:8000
 */

const BASE = "/api";

async function request(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

/* ── Genes ─────────────────────────────────────────────────── */

export function searchGenes(query, limit = 10) {
  return request(`${BASE}/genes/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export function resolveGene(hugo) {
  return request(`${BASE}/genes/resolve/${encodeURIComponent(hugo)}`);
}

/* ── Ranking ───────────────────────────────────────────────── */

export function rankCellLines(params) {
  return request(`${BASE}/rank`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

/* ── Cell line detail ──────────────────────────────────────── */

export function getCellLineDetail(achId, gene) {
  let url = `${BASE}/celllines/${encodeURIComponent(achId)}`;
  if (gene) url += `?gene=${encodeURIComponent(gene)}`;
  return request(url);
}

/**
 * Get full evidence breakdown for a cell line across all queried genes.
 * Returns per-source Z-scores, percentiles, ranks, protein z-score, data coverage,
 * and per-source combined scores using the given RNA/Protein weights.
 */
export function getCellLineEvidence(achId, genes, wRna = 0.7, wProtein = 0.3) {
  const hugos = genes.map((g) => g.hugo).join(",");
  const dirs = genes.map((g) => g.direction).join(",");
  return request(
    `${BASE}/celllines/${encodeURIComponent(achId)}/evidence` +
      `?genes=${encodeURIComponent(hugos)}` +
      `&directions=${encodeURIComponent(dirs)}` +
      `&w_rna=${encodeURIComponent(wRna)}` +
      `&w_protein=${encodeURIComponent(wProtein)}`
  );
}

/* ── Compare ───────────────────────────────────────────────── */

export function compareCellLines(achIds, gene) {
  return request(`${BASE}/celllines/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ach_ids: achIds, gene }),
  });
}

/* ── Filter options ────────────────────────────────────────── */

export function getDiseases() {
  return request(`${BASE}/filters/diseases`);
}

export function getLineages() {
  return request(`${BASE}/filters/lineages`);
}