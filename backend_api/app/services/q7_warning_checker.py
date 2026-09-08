"""
Q7 Assay Compatibility Warnings.

Given a cell line's growth pattern and an intended assay type, flags whether
the cell line is compatible. Does not affect ranking score.

Author: NattawasP (Nammon)
"""

import pandas as pd

from app.services.q7_assay_profiles import ASSAY_PROFILES


def check_q7_warnings(dim: pd.DataFrame, assay_type: str) -> pd.DataFrame:
    """
    Check assay compatibility for each cell line.

    Parameters
    ----------
    dim : DataFrame with columns ['ach_id', 'cell_line_name', 'lineage', 'growth_pattern']
    assay_type : one of the keys in ASSAY_PROFILES

    Returns
    -------
    DataFrame with columns ['ach_id', 'q7_status', 'q7_warning']
    """
    if assay_type not in ASSAY_PROFILES:
        raise ValueError(f"Unknown assay. Choose from: {list(ASSAY_PROFILES.keys())}")

    profile = ASSAY_PROFILES[assay_type]
    df = dim.copy()
    df['q7_status'] = 'OK'
    df['q7_warning'] = ''

    if 'need_growth' in profile:
        allowed = profile['need_growth']

        unknown_mask = df['growth_pattern'] == 'unknown'
        df.loc[unknown_mask, 'q7_status'] = 'WARN'
        df.loc[unknown_mask, 'q7_warning'] = 'growth pattern unknown'

        wrong_mask = (~df['growth_pattern'].isin(allowed)) & (~unknown_mask)
        df.loc[wrong_mask, 'q7_status'] = 'WARN'
        allowed_str = '/'.join(allowed)
        df.loc[wrong_mask, 'q7_warning'] = (
            'growth is ' + df.loc[wrong_mask, 'growth_pattern'].astype(str)
            + ' (need ' + allowed_str + ')'
        )

    return df[['ach_id', 'q7_status', 'q7_warning']]
