import pandas as pd
from pathlib import Path
from q6_lineage_scorer import compute_q6_score
from q7_warning_checker import check_q7_warnings
from q7_assay_profiles import ASSAY_PROFILES

PROCESSED = Path(__file__).parent.parent / 'data' / 'processed'
dim = pd.read_parquet(PROCESSED / 'dim_cell_lines.parquet')


def search_by_lineage(lineage=None, disease=None, subtype=None, top_n=5):
    q6 = compute_q6_score(dim, query_lineage=lineage,query_disease=disease, query_subtype=subtype)
    top = q6[q6['q6_score'] > 0].nlargest(top_n, 'q6_score')
    return top.to_dict('record')

def check_assay_compatibility(cell_names, assay_type):
    q7 = check_q7_warnings(dim, assay_type)
    subset = q7[q7['cell_line_name'].isin(cell_names)]
    return subset.to_dict('records')

