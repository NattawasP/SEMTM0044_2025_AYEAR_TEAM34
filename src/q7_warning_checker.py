import pandas as pd
from q7_assay_profiles import ASSAY_PROFILES


def check_q7_warnings(dim, assay_type):
    if assay_type not in ASSAY_PROFILES:
        raise ValueError(f"Unknown assay. Choose from: {list(ASSAY_PROFILES.keys())}")

    profile = ASSAY_PROFILES[assay_type]
    df = dim.copy()
    df['q7_status'] = 'OK'
    df['q7_warning'] = ''




def list_assays():
    for key, profile in ASSAY_PROFILES.items():
        print(f"  {key:20s}  {profile['description']}")
