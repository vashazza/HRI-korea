"""Phase 4 — HRI 모델 추정 + 검증.

종속변수 (옵션 B): unmet_std_pct (미충족 의료 표준화율, 지역사회건강조사 2024)
설계:
    unmet_std_pct ~ β_w·WAI + β_i·IAI + β_d·DPI + ε
LASSO 5-fold CV로 β 추정 → 절대값 기반 비례 가중치로 환산
HRI_i = w_w·WAI + w_i·IAI − w_d·DPI  (값이 높을수록 복원 수준 ↑)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LassoCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


# 옵션 A: 관외이용률 = 거주지 밖에서 받는 진료비 비중. 의료 자원 풍부할수록 ↓.
TARGET = "outflow_cost_ratio"
# 옵션 B: unmet_std_pct — robustness check
TARGET_ALT = "unmet_std_pct"
PREDICTORS = ["wai", "iai", "dpi"]


@dataclass
class HRIWeights:
    w_wai: float
    w_iai: float
    w_dpi: float
    raw_coef: dict[str, float]
    alpha: float
    r2_cv: float
    n_train: int
    target: str = TARGET

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "w_wai": self.w_wai,
            "w_iai": self.w_iai,
            "w_dpi": self.w_dpi,
            "raw_coef": self.raw_coef,
            "alpha": self.alpha,
            "r2_cv": self.r2_cv,
            "n_train": self.n_train,
        }


def fit_hri_weights(df: pd.DataFrame, target: str = TARGET, random_state: int = 42) -> HRIWeights:
    """LASSO 5-fold CV. 종속변수의 부호가 음(WAI/IAI 클수록 미충족↓)임을 활용."""
    data = df.dropna(subset=PREDICTORS + [target]).copy()
    X = data[PREDICTORS].values
    y = data[target].values

    lasso = LassoCV(cv=5, random_state=random_state, max_iter=10_000)
    lasso.fit(X, y)
    raw = {p: float(c) for p, c in zip(PREDICTORS, lasso.coef_)}

    abs_coef = np.abs(lasso.coef_)
    total = abs_coef.sum()
    if total == 0:
        weights = np.array([1 / 3, 1 / 3, 1 / 3])
    else:
        weights = abs_coef / total

    return HRIWeights(
        w_wai=float(weights[0]),
        w_iai=float(weights[1]),
        w_dpi=float(weights[2]),
        raw_coef=raw,
        alpha=float(lasso.alpha_),
        r2_cv=float(lasso.score(X, y)),
        n_train=len(data),
    )


def compute_hri_raw(df: pd.DataFrame, w: HRIWeights) -> pd.Series:
    """HRI raw (not scaled). 시뮬레이션 비교용."""
    return w.w_wai * df["wai"] + w.w_iai * df["iai"] - w.w_dpi * df["dpi"]


def compute_hri(
    df: pd.DataFrame, w: HRIWeights,
    baseline_min: float | None = None, baseline_max: float | None = None,
) -> pd.Series:
    """HRI = w_w·WAI + w_i·IAI − w_d·DPI, 0-100 정규화. 값↑ = 복원 수준↑.
    baseline_min/max를 주면 그 범위로 정규화 (시뮬레이션 비교용).
    """
    raw = compute_hri_raw(df, w)
    rmin = baseline_min if baseline_min is not None else float(raw.min())
    rmax = baseline_max if baseline_max is not None else float(raw.max())
    if rmax == rmin:
        return pd.Series(50.0, index=df.index, name="hri")
    return (((raw - rmin) / (rmax - rmin)) * 100).rename("hri")


# ── 검증 ──────────────────────────────────────────────────────


def holdout_validation(df: pd.DataFrame, target: str = TARGET, test_size: float = 0.2,
                       random_state: int = 42) -> dict:
    """80:20 홀드아웃: train으로 가중치 추정 → test에서 unmet 예측 성능."""
    data = df.dropna(subset=PREDICTORS + [target]).copy()
    train, test = train_test_split(data, test_size=test_size, random_state=random_state)
    w = fit_hri_weights(train, target=target, random_state=random_state)
    # 회귀 예측 (LASSO 계수 그대로)
    Xtr = train[PREDICTORS].values
    Xte = test[PREDICTORS].values
    ytr = train[target].values
    yte = test[target].values
    # 단순 OLS-of-LASSO 대신: lasso 모델 재학습으로 예측
    lasso = LassoCV(cv=5, random_state=random_state, max_iter=10_000).fit(Xtr, ytr)
    yhat = lasso.predict(Xte)
    return {
        "weights": w.to_dict(),
        "test_n": int(len(test)),
        "test_r2": float(r2_score(yte, yhat)),
        "test_rmse": float(np.sqrt(mean_squared_error(yte, yhat))),
        "test_mae": float(mean_absolute_error(yte, yhat)),
    }


def repeated_holdout(df: pd.DataFrame, target: str = TARGET, n_splits: int = 200,
                     test_size: float = 0.2) -> dict:
    """분할을 바꿔가며 80:20 홀드아웃 R²의 분포를 본다.

    WAI는 대형병원이 몰린 몇 곳(종로구 등)이 극단값이라, 한 번의 분할은 그 지역이
    검증셋에 들어가느냐에 크게 좌우된다.
    """
    data = df.dropna(subset=PREDICTORS + [target])
    X, y = data[PREDICTORS].values, data[target].values
    r2 = []
    for seed in range(n_splits):
        tr, te = train_test_split(np.arange(len(data)), test_size=test_size, random_state=seed)
        model = LassoCV(cv=5, random_state=42, max_iter=10_000).fit(X[tr], y[tr])
        r2.append(r2_score(y[te], model.predict(X[te])))
    r2 = np.array(r2)
    return {
        "n_splits": n_splits,
        "r2_median": float(np.median(r2)),
        "r2_q25": float(np.percentile(r2, 25)),
        "r2_q75": float(np.percentile(r2, 75)),
        "share_negative": float(np.mean(r2 < 0)),
    }


def bootstrap_weights(df: pd.DataFrame, target: str = TARGET, n_iter: int = 100,
                      random_state: int = 42) -> dict:
    """부트스트랩으로 가중치 신뢰구간과, 각 지수가 LASSO에 남는 비율을 본다."""
    data = df.dropna(subset=PREDICTORS + [target]).copy()
    rng = np.random.default_rng(random_state)
    rows, kept = [], []
    for _ in range(n_iter):
        idx = rng.integers(0, len(data), len(data))
        sample = data.iloc[idx]
        w = fit_hri_weights(sample, target=target, random_state=random_state)
        rows.append([w.w_wai, w.w_iai, w.w_dpi])
        kept.append([w.raw_coef[p] != 0 for p in PREDICTORS])
    arr, kept = np.array(rows), np.array(kept)

    def summary(i: int) -> dict:
        col = arr[:, i]
        return {
            "mean": float(col.mean()),
            "ci_lo": float(np.percentile(col, 2.5)),
            "ci_hi": float(np.percentile(col, 97.5)),
            "selected": float(kept[:, i].mean()),   # LASSO가 이 지수를 남긴(계수≠0) 표본의 비율
        }

    return {"n_iter": n_iter, "w_wai": summary(0), "w_iai": summary(1), "w_dpi": summary(2)}


def external_validation(df: pd.DataFrame, external_col: str) -> dict:
    """HRI vs 외부 지표(예: outflow ratio, amenable mortality) 상관."""
    data = df.dropna(subset=["hri", external_col]).copy()
    pearson = data[["hri", external_col]].corr(method="pearson").iloc[0, 1]
    spearman = data[["hri", external_col]].corr(method="spearman").iloc[0, 1]
    return {
        "external_col": external_col,
        "n": int(len(data)),
        "pearson": float(pearson),
        "spearman": float(spearman),
    }


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    from . import paths
    from .indices import attach_indices

    master = pd.read_csv(paths.PROCESSED / "master_dataset.csv", encoding="utf-8-sig")
    df = attach_indices(master)

    print(f"input: {df.shape}")
    n_target_na = df[TARGET].isna().sum()
    print(f"target ({TARGET}) NaN: {n_target_na}")
    print()

    # 1) 가중치 추정
    weights = fit_hri_weights(df)
    print(f"━━━ LASSO weights (target = {TARGET}) ━━━")
    print(f"  raw coef: {weights.raw_coef}")
    print(f"  α (LASSO): {weights.alpha:.4f}")
    print(f"  R² (in-sample): {weights.r2_cv:.3f}")
    print(f"  normalized weights:")
    print(f"    w_wai = {weights.w_wai:.3f}")
    print(f"    w_iai = {weights.w_iai:.3f}")
    print(f"    w_dpi = {weights.w_dpi:.3f}")
    print()

    # 2) HRI 산출
    df["hri"] = compute_hri(df, weights)

    print("━━━ HRI face validity ━━━")
    label = df["sido"] + " " + df["sgg"]
    sr = df["hri"].copy(); sr.index = label
    print("TOP 10 (복원 수준 ↑):")
    for k, v in sr.nlargest(10).items():
        print(f"  {v:6.2f}  {k}")
    print("BOTTOM 10 (복원 수준 ↓):")
    for k, v in sr.nsmallest(10).items():
        print(f"  {v:6.2f}  {k}")
    print()

    # 3) 검증
    print("━━━ 80:20 홀드아웃 ━━━")
    ho = holdout_validation(df)
    print(json.dumps(ho, indent=2, ensure_ascii=False))
    print()

    print("━━━ 반복 홀드아웃 (80:20 분할 200회) ━━━")
    rh = repeated_holdout(df)
    print(json.dumps(rh, indent=2, ensure_ascii=False))
    print()

    print("━━━ 부트스트랩 (n=100) ━━━")
    bs = bootstrap_weights(df, n_iter=100)
    print(json.dumps(bs, indent=2, ensure_ascii=False))
    print()

    print("━━━ 외부 검증 (HRI vs 미사용 종속변수 후보) ━━━")
    # 메인이 옵션 A(outflow)이므로 옵션 B(미충족)와의 상관 + 보조 outflow_patient_ratio
    for ext in ["unmet_std_pct", "unmet_crude_pct", "outflow_patient_ratio"]:
        if ext in df.columns:
            ev = external_validation(df, ext)
            print(f"  HRI vs {ext}: pearson={ev['pearson']:+.3f}, spearman={ev['spearman']:+.3f}, n={ev['n']}")
    print()

    # 옵션 B로 robustness check
    print("━━━ Robustness — 옵션 B(unmet_std_pct) 종속변수로 재추정 ━━━")
    weights_b = fit_hri_weights(df, target=TARGET_ALT)
    print(f"  raw coef: {weights_b.raw_coef}")
    print(f"  R²: {weights_b.r2_cv:.3f}")
    print(f"  weights: w_wai={weights_b.w_wai:.3f}, w_iai={weights_b.w_iai:.3f}, w_dpi={weights_b.w_dpi:.3f}")
    print()

    # 저장
    out_path = paths.PROCESSED / "hri_results.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"saved → {out_path}")

    weights_path = paths.REPORTS / "hri_weights.json"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    with open(weights_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "weights": weights.to_dict(),
                "holdout": ho,
                "repeated_holdout": rh,
                "bootstrap": bs,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"saved → {weights_path}")
