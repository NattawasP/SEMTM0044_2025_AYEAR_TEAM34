# Q6 hierarchical lineage scoring

import pandas as pd

def compute_q6_score(dim, query_lineage=None, query_disease=None, query_subtype=None):
    df = dim.copy()
    df['q6_score'] = 0.0
    df['match_level'] = 'none'