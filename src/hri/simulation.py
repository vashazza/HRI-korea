"""Phase 6 — 정책 시나리오 시뮬레이션.

각 시나리오는 마스터 데이터셋의 특정 변수를 조작 → WAI/IAI/DPI 재산출 → HRI 재산출 →
ΔHRI(시나리오 후 − 전)를 클러스터별로 비교.

시나리오:
    S1: WAI 하위 30% 시·군·구에서 필수 5과 전문의 +10%
    S2: IAI 하위 30%에서 1차 의료기관(의원) +5개
    S3: 장비(CT/MRI) 보유 하위 30%에서 CT/MRI 각 +1대
    S4: facilities_public_health_medical 보유 하위 30%에서 공공의료원 +1개
"""

from __future__ import annotations

from dataclasses import dataclass

import json
import numpy as np
import pandas as pd

from . import paths
from .hri import HRIWeights, compute_hri, compute_hri_raw
from .indices import IndexFit, fit_indices, transform_indices


@dataclass
class ScenarioResult:
    name: str
    description: str
    target_mask_size: int
    delta_hri_mean: float
    delta_hri_by_cluster: dict
    df: pd.DataFrame


def _bottom_30_mask(s: pd.Series) -> pd.Series:
    """하위 30% 마스크 — strict <(quantile) 로 동률 다수 시 과대 포함 방지.

    시·도 값을 인구비례로 나눈 변수(WAI, 장비)는 같은 시·도 안에서 수학적으로 같지만
    부동소수점 잡음(~1e-14)이 남는다. 반올림 없이 비교하면 경계에 걸린 시·도가
    잡음에 따라 쪼개지고 BLAS 빌드마다 결과가 달라진다.
    """
    s = s.round(9)
    thr = s.quantile(0.30)
    return s < thr


def apply_scenario(
    master: pd.DataFrame,
    base: pd.DataFrame,
    fits: dict[str, IndexFit],
    weights: HRIWeights,
    scenario: str,
    baseline_min: float = None,
    baseline_max: float = None,
) -> ScenarioResult:
    """
    master: 원본 (개입 적용 대상)
    base: baseline indices+HRI가 부여된 df (개입 전 비교 기준)
    fits: baseline PCA fit 객체 (transform-only 재계산용)
    """
    sim = master.copy()
    desc = ""

    if scenario == "S1":
        mask = _bottom_30_mask(base["wai"])
        cols = ["spe_내과", "spe_외과", "spe_응급의학과", "spe_소아청소년과", "spe_산부인과", "doc_의사_전문의"]
        for c in cols:
            sim.loc[mask, c] = sim.loc[mask, c] * 1.10
        desc = "WAI 하위 30% 시·군·구에서 필수 5과 전문의 + 의사 전문의 +10%"
    elif scenario == "S2":
        mask = _bottom_30_mask(base["iai"])
        sim.loc[mask, "facilities_clinic"] = sim.loc[mask, "facilities_clinic"] + 5
        desc = "IAI 하위 30%에서 의원(facilities_clinic) +5개"
    elif scenario == "S3":
        # CT/MRI 인구당 보유량 하위 30%
        ct_mri = master["eq_전산화단층촬영장치"] + master["eq_자기공명영상진단기"]
        per_100k = ct_mri / (master["total_population"] / 100_000)
        mask = _bottom_30_mask(per_100k)
        sim.loc[mask, "eq_전산화단층촬영장치"] += 1
        sim.loc[mask, "eq_자기공명영상진단기"] += 1
        desc = "CT+MRI 인구당 보유량 하위 30%에서 CT, MRI 각각 +1대"
    elif scenario == "S4":
        # 보건의료원 보유량 == 0 인 시·군·구 (대부분) 에서 신설. 진정한 정책 시나리오 의미.
        mask = master["facilities_public_health_medical"] == 0
        sim.loc[mask, "facilities_public_health_medical"] = 1
        desc = "보건의료원이 없는 시·군·구에 보건의료원 신설(+1개)"
    else:
        raise ValueError(f"unknown scenario {scenario!r}")

    # baseline의 PCA·스케일링·HRI min-max를 그대로 적용해 indices+HRI 재계산
    after = transform_indices(sim, fits)
    after["hri"] = compute_hri(after, weights, baseline_min, baseline_max)
    delta = after["hri"] - base["hri"]

    merged = base[["sido", "sgg", "cluster_id", "cluster_name", "hri"]].copy()
    merged = merged.rename(columns={"hri": "hri_before"})
    merged["hri_after"] = after["hri"].values
    merged["delta_hri"] = delta.values
    merged["treated"] = (delta.abs() > 1e-9)

    by_cluster = (
        merged.groupby("cluster_name", as_index=False)
        .agg(
            n=("sgg", "count"),
            n_treated=("treated", "sum"),
            delta_mean=("delta_hri", "mean"),
            delta_median=("delta_hri", "median"),
        )
        .sort_values("delta_mean", ascending=False)
    )

    return ScenarioResult(
        name=scenario,
        description=desc,
        target_mask_size=int(merged["treated"].sum()),
        delta_hri_mean=float(merged["delta_hri"].mean()),
        delta_hri_by_cluster=by_cluster.to_dict(orient="records"),
        df=merged,
    )


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    # 1) 입력
    base = pd.read_csv(paths.PROCESSED / "hri_with_clusters.csv", encoding="utf-8-sig")
    master_raw = pd.read_csv(paths.PROCESSED / "master_dataset.csv", encoding="utf-8-sig")
    # 클러스터 정보 머지
    master_raw = master_raw.merge(
        base[["sido", "sgg", "cluster_id", "cluster_name"]], on=["sido", "sgg"], how="left"
    )

    # 2) Phase 4 가중치 재로드
    with open(paths.REPORTS / "hri_weights.json", encoding="utf-8") as f:
        meta = json.load(f)
    w = HRIWeights(
        w_wai=meta["weights"]["w_wai"],
        w_iai=meta["weights"]["w_iai"],
        w_dpi=meta["weights"]["w_dpi"],
        raw_coef=meta["weights"]["raw_coef"],
        alpha=meta["weights"]["alpha"],
        r2_cv=meta["weights"]["r2_cv"],
        n_train=meta["weights"]["n_train"],
        target=meta["weights"]["target"],
    )
    print(f"using weights: w_wai={w.w_wai:.3f}, w_iai={w.w_iai:.3f}, w_dpi={w.w_dpi:.3f}")
    print()

    # 3) baseline PCA를 학습 + HRI 산출 (master_raw에 cluster 컬럼이 이미 머지된 상태)
    base_df, fits = fit_indices(master_raw)
    raw_base = compute_hri_raw(base_df, w)
    baseline_min, baseline_max = float(raw_base.min()), float(raw_base.max())
    base_df["hri"] = compute_hri(base_df, w, baseline_min, baseline_max)

    # 4) 4개 시나리오 시뮬레이션 — baseline min-max를 고정
    all_results = []
    for sc in ["S1", "S2", "S3", "S4"]:
        r = apply_scenario(master_raw, base_df, fits, w, sc, baseline_min, baseline_max)
        print(f"━━━ {r.name} — {r.description} ━━━")
        print(f"  treated count: {r.target_mask_size}")
        print(f"  ΔHRI overall mean: {r.delta_hri_mean:+.3f}")
        print(f"  ΔHRI by cluster:")
        for row in r.delta_hri_by_cluster:
            print(f"    {row['cluster_name']:<25s} n={row['n']:>3} treated={int(row['n_treated']):>3}  Δmean={row['delta_mean']:+.3f}  Δmed={row['delta_median']:+.3f}")
        print()
        all_results.append(r)

    # 4) 매트릭스 형태로 정리
    print("━━━ 클러스터 × 시나리오 ΔHRI 매트릭스 ━━━")
    rows = []
    for r in all_results:
        for cl in r.delta_hri_by_cluster:
            rows.append({"scenario": r.name, "cluster": cl["cluster_name"], "delta_mean": cl["delta_mean"]})
    mat = pd.DataFrame(rows).pivot(index="cluster", columns="scenario", values="delta_mean").round(3)
    print(mat.to_string())
    print()

    # 5) 저장
    out_csv = paths.PROCESSED / "scenario_simulations.csv"
    combined = []
    for r in all_results:
        d = r.df.copy()
        d["scenario"] = r.name
        combined.append(d)
    pd.concat(combined, ignore_index=True).to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"saved → {out_csv}")

    mat_path = paths.PROCESSED / "scenario_cluster_matrix.csv"
    mat.to_csv(mat_path, encoding="utf-8-sig")
    print(f"saved → {mat_path}")
