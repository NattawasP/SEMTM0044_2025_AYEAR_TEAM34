# Q6 hierarchical lineage scoring


def compute_q6_score(dim, query_lineage=None, query_disease=None, query_subtype=None):
    df = dim.copy()
    df['q6_score'] = 0.0
    df['match_level'] = 'none'
    
    if query_subtype and 'subtype' in df.columns:
        mask = df['subtype'] == query_subtype
        df.loc[mask, 'q6_score'] = 1.00
        df.loc[mask, 'match_level'] = 'exact_subtype'
        
    if query_disease:
        mask = (df['primary_disease'] == query_disease) & (df['q6_score'] == 0)
        df.loc[mask, 'q6_score'] = 0.75
        df.loc[mask, 'match_level'] = 'same_disease'

    if query_lineage:
        mask = (df['lineage'] == query_lineage) & (df['q6_score'] == 0)
        df.loc[mask, 'q6_score'] = 0.50
        df.loc[mask, 'match_level'] = 'same_lineage'

    return df[[
        'ach_id', 'cell_line_name', 'lineage', 'primary_disease',
        'q6_score', 'match_level'
    ]]