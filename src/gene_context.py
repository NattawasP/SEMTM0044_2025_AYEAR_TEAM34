# AstraZeneca target gene notes (from Daniel's email)

GENE_NOTES = {
    'FGFR2': {
        'has_proteomics': False,
        'has_transcriptomics': True,
        'has_geo': True,
        'notes': 'No proteomics data available.'
    },
    'CD86': {
        'has_proteomics': True,
        'has_transcriptomics': True,
        'has_geo': True,
        'notes': 'Has proteomics data.'
    },
    'ERBB2': {
        'has_proteomics': True,
        'has_transcriptomics': True,
        'has_geo': True,
        'notes': 'Good representation across proteomics, transcriptomics, and GEO.'
    },
    'KLK4': {
        'has_proteomics': False,
        'has_transcriptomics': True,
        'has_geo': True,
        'notes': 'No proteomics data. Few cell lines in GEO datasets.'
    },
    'GAPDH': {
        'has_proteomics': True,
        'has_transcriptomics': True,
        'has_geo': True,
        'notes': 'HOUSEKEEPING gene used as baseline/control. Activity changes very little across cells. High expression is expected in most cells and NOT biologically informative for target selection. Very few cells should show as high-top selection.'
    },
    'ASGR1': {
        'has_proteomics': True,
        'has_transcriptomics': True,
        'has_geo': False,
        'notes': 'Has transcriptomic and proteomic data, but not much GEO data.'
    },
    'MUC1': {
        'has_proteomics': True,
        'has_transcriptomics': False,
        'has_geo': False,
        'notes': 'Has proteomic data only.'
    },
    'CD3E': {
        'has_proteomics': False,
        'has_transcriptomics': True,
        'has_geo': False,
        'notes': 'T-CELL MARKER — cornerstone of most T-cells. Tricky target: strong literature evidence for protein expression, but limited proteomics or GEO cell line data. Expect narrow expression in immune (T-cell) lineages.'
    },
}


def get_gene_context(gene_symbol):
    gene_upper = gene_symbol.upper()
    if gene_upper in GENE_NOTES:
        return {'gene': gene_upper, **GENE_NOTES[gene_upper]}
    return {
        'gene': gene_symbol,
        'notes': 'No AstraZeneca-provided notes for this gene.'
    }
