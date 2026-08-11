import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline import (load_tables, build_feature_matrix,
                          rank_cell_lines, apply_full_exclusion)

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "parquet")
PROC = os.path.join(os.path.dirname(__file__), "..", "processed")

tables = load_tables(DATA, PROC)
master, feat_cols = build_feature_matrix(tables)

EGFR  = "ENSG00000146648"
ERBB2 = "ENSG00000141736"
KRAS  = "ENSG00000133703"


def test_feature_matrix_shape():
    assert len(master) == 895
    assert len(feat_cols) == 965


def test_egfr_returns_squamous_lineages():
    top20 = rank_cell_lines(EGFR, tables).head(20)["lineage"].tolist()
    assert any(l in top20 for l in ["lung", "esophagus", "upper_aerodigestive"])


def test_erbb2_returns_breast():
    top20 = rank_cell_lines(ERBB2, tables).head(20)["lineage"].tolist()
    assert "breast" in top20


def test_scores_are_bounded():
    df = rank_cell_lines(EGFR, tables)
    assert df["confidence_score"].between(0, 1).all()
    assert df["evidence_score"].between(0, 100).all()


def test_kras_exclusion_removes_expected_count():
    ranked = rank_cell_lines(EGFR, tables)
    viable = apply_full_exclusion(ranked, tables, criteria={"damaging_mutation": KRAS})
    assert len(viable) == len(ranked) - 73


def test_missing_threshold_raises():
    import pytest
    ranked = rank_cell_lines(EGFR, tables)
    with pytest.raises(ValueError):
        apply_full_exclusion(ranked, tables, criteria={"metabolite": ("lactate", None)})