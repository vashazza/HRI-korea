"""커밋된 처리 결과의 불변식. 원자료 없이 돈다."""

import json

import numpy as np
import pandas as pd
import pytest

from hri import paths
from hri.hri import HRIWeights, compute_hri, compute_hri_raw


@pytest.fixture(scope="module")
def results():
    return pd.read_csv(paths.PROCESSED / "hri_with_clusters.csv", encoding="utf-8-sig")


@pytest.fixture(scope="module")
def weights():
    meta = json.loads((paths.REPORTS / "hri_weights.json").read_text(encoding="utf-8"))
    return HRIWeights(**meta["weights"])


def test_229_unique_regions(results):
    # 시·군·구 코드 대신 (시도, 시군구) 이름이 조인 키다
    assert len(results) == 229
    assert not results.duplicated(["sido", "sgg"]).any()


def test_master_matches_results(results):
    master = pd.read_csv(paths.PROCESSED / "master_dataset.csv", encoding="utf-8-sig")
    assert set(zip(master.sido, master.sgg)) == set(zip(results.sido, results.sgg))


@pytest.mark.parametrize("col", ["hri", "wai", "iai", "dpi"])
def test_scores_in_range_no_nan(results, col):
    assert results[col].notna().all()
    assert results[col].between(0, 100).all()
    assert results[col].min() == pytest.approx(0) and results[col].max() == pytest.approx(100)


def test_weights_sum_to_one_and_nonnegative(weights):
    w = np.array([weights.w_wai, weights.w_iai, weights.w_dpi])
    assert w.sum() == pytest.approx(1.0)
    assert (w >= 0).all()


def test_dpi_enters_negatively(results, weights):
    # 가중치가 0인 지수는 움직여도 그대로일 수 있으므로 방향만 확인한다 (LASSO가 IAI를 0으로 둘 수 있음)
    raw = compute_hri_raw(results, weights)
    assert (compute_hri_raw(results.assign(dpi=results.dpi + 1), weights) <= raw).all()
    assert (compute_hri_raw(results.assign(wai=results.wai + 1), weights) >= raw).all()
    assert (compute_hri_raw(results.assign(iai=results.iai + 1), weights) >= raw).all()
    assert weights.w_dpi > 0


def test_stored_hri_matches_formula(results, weights):
    np.testing.assert_allclose(compute_hri(results, weights), results["hri"], atol=1e-9)


def test_cluster_names_are_one_to_one(results):
    assert results["cluster_name"].notna().all()
    pairs = results[["cluster_id", "cluster_name"]].drop_duplicates()
    assert pairs["cluster_id"].is_unique and pairs["cluster_name"].is_unique


def test_index_inputs_are_not_constant():
    # 로더가 조용히 빈 표를 돌려주면 병합 뒤 0으로 채워져 변수가 통째로 죽는다 (간호사 변수에서 실제로 있었던 일)
    from hri.indices import DPI_RATE_FEATURES, IAI_COUNT_FEATURES, WAI_COUNT_FEATURES

    master = pd.read_csv(paths.PROCESSED / "master_with_indices.csv", encoding="utf-8-sig")
    for col in WAI_COUNT_FEATURES + IAI_COUNT_FEATURES + DPI_RATE_FEATURES:
        assert master[col].nunique() > 1, f"{col} 값이 전부 같다"
