import { useState } from "react";
import styles from "./DocsModal.module.css";

const TABS = [
  { key: "docs", label: "Documentation" },
  { key: "sources", label: "Data Sources" },
  { key: "methods", label: "Methods" },
  { key: "about", label: "About" },
];

export default function DocsModal({ initialTab = "docs", onClose }) {
  const [tab, setTab] = useState(initialTab);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <h2 className={styles.title}>CellLineFinder Documentation</h2>
          <button className={styles.closeBtn} onClick={onClose}>×</button>
        </div>

        {/* Tabs */}
        <div className={styles.tabs}>
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`${styles.tab} ${tab === t.key ? styles.tabActive : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className={styles.body}>
          {tab === "docs" && <DocsContent />}
          {tab === "sources" && <SourcesContent />}
          {tab === "methods" && <MethodsContent />}
          {tab === "about" && <AboutContent />}
        </div>
      </div>
    </div>
  );
}

/* ── Tab content components ─────────────────────────────── */

function DocsContent() {
  return (
    <div className={styles.content}>
      <h3>Getting Started</h3>
      <p>
        CellLineFinder is a multi-omics cell line recommendation platform designed
        to help researchers identify the most suitable cancer cell lines for their
        experiments based on gene expression, protein abundance, mutation status,
        and fusion data.
      </p>

      <h4>How to Search</h4>
      <ol>
        <li>
          <strong>Add target genes</strong> — Type a HUGO gene symbol (e.g. EGFR, TP53)
          into the search bar and click Add. Set each gene to HIGH (prefer high expression)
          or LOW (prefer low expression).
        </li>
        <li>
          <strong>Configure filters</strong> — Optionally filter by disease, lineage,
          subtype, mutation/fusion status, or adjust RNA/Protein weights.
        </li>
        <li>
          <strong>Find Cell Lines</strong> — Click the button to run the ranking pipeline.
          Results are sorted by score (best match first).
        </li>
        <li>
          <strong>Explore details</strong> — Click any row to see the full multi-omics
          evidence breakdown, including per-source scores, protein detection, and mutation details.
        </li>
        <li>
          <strong>Compare</strong> — Select 2 or more cell lines using the checkboxes,
          then click Compare to see a side-by-side view.
        </li>
      </ol>

      <h4>Multi-Gene Search</h4>
      <p>
        When searching for multiple genes, the system ranks cell lines per gene
        individually, then fuses the ranks using Reciprocal Rank Fusion (RRF).
        Scores are normalised to 0–1, where 1.0 means the cell line is ranked #1
        for every gene searched. Per-gene ranks are shown in each results row
        so you can see which genes a cell line is strong or weak in.
      </p>

      <h4>Score Interpretation</h4>
      <table className={styles.infoTable}>
        <thead>
          <tr><th>Score Range</th><th>Interpretation</th></tr>
        </thead>
        <tbody>
          <tr><td className={styles.scoreHigh}>0.7 – 1.0</td><td>Strong match — high expression/protein for target genes</td></tr>
          <tr><td className={styles.scoreMid}>0.4 – 0.7</td><td>Moderate match — consider reviewing the evidence breakdown</td></tr>
          <tr><td className={styles.scoreLow}>0.0 – 0.4</td><td>Weak match — likely low expression for one or more genes</td></tr>
        </tbody>
      </table>

      <h4>Chatbot Assistant</h4>
      <p>
        Use the chat widget (bottom-right corner) to ask biology questions about
        your results, get explanations of cell line characteristics, or request
        help interpreting the ranking output.
      </p>
    </div>
  );
}

function SourcesContent() {
  return (
    <div className={styles.content}>
      <h3>Data Sources</h3>
      <p>
        CellLineFinder integrates data from multiple public databases, harmonised
        into a unified DuckDB warehouse. All data is mapped to a common cell line
        identifier (ACH ID from DepMap).
      </p>

      <h4>RNA Expression</h4>
      <table className={styles.infoTable}>
        <thead>
          <tr><th>Source</th><th>Description</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>DepMap</strong></td>
            <td>Cancer Cell Line Encyclopedia (CCLE) RNA-seq TPM values from the Broad Institute DepMap portal</td>
            <td>~1,400 cell lines</td>
          </tr>
          <tr>
            <td><strong>HPA</strong></td>
            <td>Human Protein Atlas RNA-seq expression data (TPM) across cancer cell lines</td>
            <td>~70 cell lines</td>
          </tr>
          <tr>
            <td><strong>GEO</strong></td>
            <td>Gene Expression Omnibus curated RNA-seq datasets, reprocessed to TPM</td>
            <td>~250 cell lines</td>
          </tr>
        </tbody>
      </table>

      <h4>Protein Abundance</h4>
      <table className={styles.infoTable}>
        <thead>
          <tr><th>Source</th><th>Description</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Gygi Proteomics</strong></td>
            <td>Mass spectrometry–based protein intensity measurements from the Gygi lab (via DepMap)</td>
            <td>~375 cell lines</td>
          </tr>
        </tbody>
      </table>

      <h4>Genomic Variants</h4>
      <table className={styles.infoTable}>
        <thead>
          <tr><th>Source</th><th>Description</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Mutations</strong></td>
            <td>Somatic mutations from DepMap, including driver/hotspot/damaging annotations and variant allele frequency</td>
          </tr>
          <tr>
            <td><strong>Fusions</strong></td>
            <td>Gene fusions from DepMap, including confidence level, reading frame, and fusion fragments per million (FFPM)</td>
          </tr>
        </tbody>
      </table>

      <h4>Cell Line Metadata</h4>
      <p>
        Cell line annotations (disease, lineage, subtype, sex, growth pattern)
        are sourced from the DepMap Model table and used for filtering and the
        tissue-match (Q6) boost.
      </p>
    </div>
  );
}

function MethodsContent() {
  return (
    <div className={styles.content}>
      <h3>Ranking Methodology</h3>

      <h4>Step 1: Per-Gene Expression Scoring</h4>
      <p>
        For each target gene, RNA expression data (TPM) is retrieved from up to
        3 sources (DepMap, HPA, GEO). Within each source, two statistical rankings
        are computed:
      </p>
      <ul>
        <li><strong>Z-Score Rank</strong> — Standardises expression relative to the population mean and standard deviation</li>
        <li><strong>Percentile Rank</strong> — Ranks by the fraction of cell lines with lower expression</li>
      </ul>
      <p>
        These rank lists are combined using <strong>Reciprocal Rank Fusion (RRF)</strong> with
        k=60, averaged across the sources a cell line appears in. Averaging (rather
        than summing) prevents penalising cell lines that are missing from one data source.
      </p>

      <h4>Step 2: Protein Scoring</h4>
      <p>
        Protein intensity data undergoes the same Z-Score + Percentile → RRF process
        as RNA expression.
      </p>

      <h4>Step 3: RNA + Protein Combination</h4>
      <p>
        RNA and protein RRF scores are min-max normalised to [0, 1], then combined
        with user-configurable weights (default: 70% RNA, 30% Protein):
      </p>
      <code className={styles.formula}>
        combined_score = w_rna × RNA_norm + w_protein × Protein_norm
      </code>
      <p>
        Cell lines with only RNA or only protein data are scored on whichever
        layer is available, with the confidence field reflecting partial coverage.
      </p>

      <h4>Step 4: Multi-Gene Fusion</h4>
      <p>
        For multi-gene searches, cell lines are ranked per gene by their combined
        score, then fused across genes using <strong>summed RRF</strong>. The raw
        RRF score is normalised by dividing by the theoretical maximum (n_genes / (k + 1)),
        so a cell line ranked #1 for all genes receives a score of 1.0.
      </p>
      <p>
        Ranks are used instead of raw scores because different genes have incomparable
        expression scales. RRF naturally rewards cell lines that are consistently
        strong across all searched genes.
      </p>

      <h4>Step 5: Hard Filters</h4>
      <p>
        Mutation and fusion filters (include/exclude/ignore) are applied before
        multi-gene fusion. Instability (MSI/CIN), metabolite, and miRNA filters
        are also available as hard exclusion criteria.
      </p>

      <h4>Step 6: Tissue-Match Soft Boost (Q6)</h4>
      <p>
        When a target disease, lineage, or subtype is specified, a Q6 score (0–1)
        rewards cell lines matching the target tissue. The boost formula multiplies
        the base score by (0.7 + 0.3 × q6_score), so matching cell lines receive up
        to a 30% score increase without completely overriding expression-based ranking.
      </p>

      <h4>Step 7: Assay Compatibility Warnings (Q7)</h4>
      <p>
        When an assay type is selected, cell lines are checked for compatibility
        based on growth pattern (adherent vs. suspension). Warnings are displayed
        but do not affect ranking order.
      </p>

      <h4>Similarity Scoring (Similar Alternatives)</h4>
      <p>
        The detail panel offers a "Similar Alternatives" section that finds cell lines
        with the most similar molecular profile to the selected one. This helps researchers
        identify backup options or related models.
      </p>
      <p>
        The similarity pipeline works across multiple omics layers:
      </p>
      <ul>
        <li>
          <strong>Expression similarity</strong> — Built from the top 1,000 most variable
          genes (by variance across cell lines) in DepMap RNA-seq. Each cell line becomes a
          1,000-dimensional vector of z-scored log₂(TPM+1) values. Cosine similarity measures
          how closely two cell lines' expression profiles match.
        </li>
        <li>
          <strong>Protein similarity</strong> — Z-scored protein intensity vectors from Gygi
          proteomics, compared via cosine similarity. Combined with expression at a 70:30 weighting.
        </li>
        <li>
          <strong>Metabolomics &amp; miRNA</strong> — Reported as separate similarity figures
          alongside each result but not blended into the headline score, because testing showed
          they separate lineages far more weakly than expression.
        </li>
      </ul>
      <p>
        Cell lines sharing a lineage of derivation (parent–derivative relationships) are
        flagged with a "Derivative" badge so researchers can distinguish genuinely independent
        alternatives from related models.
      </p>

      <h4>Reciprocal Rank Fusion (RRF)</h4>
      <p>
        RRF is a well-established rank aggregation method from information retrieval
        (Cormack, Clarke & Butt, 2009). For each item, the RRF score is:
      </p>
      <code className={styles.formula}>
        score = Σ 1 / (k + rank_i)
      </code>
      <p>
        The parameter k=60 controls how much weight is given to top-ranked items.
        This non-linear formula ensures that being near the top of a ranking contributes
        far more than being in the middle or bottom.
      </p>
    </div>
  );
}

function AboutContent() {
  return (
    <div className={styles.content}>
      <h3>About CellLineFinder</h3>
      <p>
        CellLineFinder v2.0 is a multi-omics cell line recommendation platform
        developed as a collaborative project between the University of Bristol
        and AstraZeneca. The platform helps cancer researchers identify the most
        appropriate cell lines for their experimental needs by integrating and
        ranking data across multiple omics layers.
      </p>

      <h4>Team — Group 34</h4>
      <table className={styles.infoTable}>
        <thead>
          <tr><th>Member</th><th>Contributions</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Prab Wongsekleo</strong></td>
            <td>Full-stack development, deployment (EC2/Nginx/CI), LLM chatbot integration</td>
          </tr>
          <tr>
            <td><strong>Nattawas</strong></td>
            <td>LLM chatbot, biology questions drafting, data harmonisation</td>
          </tr>
          <tr>
            <td><strong>Victor</strong></td>
            <td>Data cleaning, similarity scoring, supervisor communication</td>
          </tr>
          <tr>
            <td><strong>Mew</strong></td>
            <td>Base ranking algorithm, project leadership, project management</td>
          </tr>
        </tbody>
      </table>

      <h4>Supervisor</h4>
      <p>Daniel D'Andrea</p>

      <h4>Technology Stack</h4>
      <ul>
        <li><strong>Backend:</strong> Python, FastAPI, DuckDB, Parquet</li>
        <li><strong>Frontend:</strong> React, Vite</li>
        <li><strong>Deployment:</strong> AWS EC2, Nginx, GitHub Actions CI/CD</li>
        <li><strong>AI:</strong> OpenAI GPT API for chatbot</li>
      </ul>

      <h4>Academic Context</h4>
      <p>
        MSc Data Science final project, University of Bristol, 2024–2025.
        Developed in collaboration with AstraZeneca to address the challenge
        of selecting appropriate cancer cell lines from thousands of candidates
        across multiple data modalities.
      </p>
    </div>
  );
}
