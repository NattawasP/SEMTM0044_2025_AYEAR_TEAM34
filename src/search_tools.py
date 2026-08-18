import pandas as pd
from pathlib import Path
from q6_lineage_scorer import compute_q6_score
from q7_warning_checker import check_q7_warnings
from q7_assay_profiles import ASSAY_PROFILES

PROCESSED = Path(__file__).parent.parent / 'data' / 'processed'
dim = pd.read_parquet(PROCESSED / 'dim_cell_lines.parquet')


def search_by_lineage(lineage=None, disease=None, subtype=None, top_n=10):
    q6 = compute_q6_score(dim, query_lineage=lineage,query_disease=disease, query_subtype=subtype)
    top = q6[q6['q6_score'] > 0].nlargest(top_n, 'q6_score')
    return top.to_dict('records')

def check_assay_compatibility(cell_names, assay_type):
    if not cell_names:
        return {'error': 'cell_names is empty. Call search_by_lineage first to get cells.'}
    q7 = check_q7_warnings(dim, assay_type)
    subset = q7[q7['cell_line_name'].isin(cell_names)]
    return subset.to_dict('records')

def lookup_cell_line(name_or_id):
    if name_or_id.startswith('ACH-'):
        row = dim[dim['ach_id'] == name_or_id]
    else:
        row = dim[dim['cell_line_name'].str.upper() == name_or_id.upper()]

    if len(row) == 0:
        return {'error': f'{name_or_id} not found'}

    return row.iloc[0].to_dict()

def list_options(category):
    if category == 'lineages':
        return sorted(dim['lineage'].dropna().unique().tolist())
    if category == 'diseases':
        return sorted(dim['primary_disease'].dropna().unique().tolist())
    if category == 'growth_patterns':
        return sorted(dim['growth_pattern'].dropna().unique().tolist())
    if category == 'assays':
        return list(ASSAY_PROFILES.keys())
    return {'error': 'Unknown category'}

