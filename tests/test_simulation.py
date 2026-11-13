"""시나리오는 baseline에서 학습한 PCA·min-max 좌표계를 바꾸지 않아야 한다 (transform-only)."""

import json

import numpy as np
import pandas as pd
import pytest

from hri import paths
from hri.hri import HRIWeights, compute_hri, compute_hri_raw
from hri.indices import fit_indices, transform_indices
from hri.simulation import _bottom_30_mask, apply_scenario


@pytest.fixture(scope="module")
def setup():
    master = pd.read_csv(paths.PROCESSED / "master_dataset.csv", encoding="utf-8-sig")
    clusters = pd.read_csv(paths.PROCESSED / "hri_with_clusters.csv", encoding="utf-8-sig")
    master = master.merge(clusters[["sido", "sgg", "cluster_id", "cluster_name"]], on=["sido", "sgg"])
    meta = json.loads((paths.REPORTS / "hri_weights.json").read_text(encoding="utf-8"))
    w = HRIWeights(**meta["weights"])

    base, fits = fit_indices(master)
    raw = compute_hri_raw(base, w)
    lo, hi = float(raw.min()), float(raw.max())
    base["hri"] = compute_hri(base, w, lo, hi)
    return master, base, fits, w, lo, hi


def _snapshot(fits):
    return {
        k: (f.scaler.mean_.copy(), f.scaler.scale_.copy(), f.pca.components_.copy(), f.sign, f.pmin, f.pmax)
        for k, f in fits.items()
    }


def _assert_same(a, b):
    for k in a:
        for x, y in zip(a[k], b[k]):
            np.testing.assert_array_equal(x, y)


def test_transform_of_unchanged_input_is_identity(setup):
    master, base, fits, *_ = setup
    again = transform_indices(master, fits)
    for col in ["wai", "iai", "dpi"]:
        np.testing.assert_allclose(again[col], base[col], atol=1e-9)


def test_changing_one_region_moves_only_that_region(setup):
    master, base, fits, w, lo, hi = setup
    sim = master.copy()
    sim.loc[0, "facilities_clinic"] += 5
    after = transform_indices(sim, fits)
    # 추정된 가중치와 무관하게 확인: 그 지역의 IAI만 오르고 다른 지역·다른 지수는 그대로
    d_iai = (after["iai"] - base["iai"]).to_numpy()
    assert d_iai[0] > 0
    assert np.all(d_iai[1:] == 0)
    for col in ["wai", "dpi"]:
        np.testing.assert_array_equal(after[col].to_numpy(), base[col].to_numpy())
    delta = (compute_hri(after, w, lo, hi) - base["hri"]).to_numpy()
    assert delta[0] >= 0
    assert np.all(delta[1:] == 0)


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3", "S4"])
def test_scenario_does_not_refit(setup, scenario):
    master, base, fits, w, lo, hi = setup
    before = _snapshot(fits)
    base_hri = base["hri"].copy()
    apply_scenario(master, base, fits, w, scenario, lo, hi)
    _assert_same(before, _snapshot(fits))
    pd.testing.assert_series_equal(base["hri"], base_hri)


def test_s1_touches_only_bottom_30pct_wai(setup):
    master, base, fits, w, lo, hi = setup
    r = apply_scenario(master, base, fits, w, "S1", lo, hi)
    targeted = _bottom_30_mask(base["wai"]).to_numpy()
    delta = r.df["delta_hri"].to_numpy()
    assert np.all(delta[~targeted] == 0)
    assert np.all(delta[targeted] >= 0)


def test_bottom_30_mask_keeps_float_noise_ties_together():
    # 수학적으로 같은 값이 부동소수점 잡음(~1e-14)만 다를 때, 경계에 걸리면 함께 포함되거나 함께 빠져야 한다.
    # (시·도 값을 나눠 쓰던 때 전남 22곳 중 20곳만 대상이 됐던 버그의 회귀 테스트)
    noise = np.array([0.0, 1e-14, -1e-14, 2e-14])
    s = pd.Series(np.concatenate([np.full(3, 1.0), 5.0 + noise, np.full(6, 9.0)]))
    assert s.quantile(0.30) == pytest.approx(5.0)   # 경계가 동률 묶음 위에 놓인다
    mask = _bottom_30_mask(s)
    assert mask[:3].all()
    assert mask[3:7].nunique() == 1
    assert not mask[7:].any()
