"""Phase 3 — WAI, IAI, DPI 하위 지수 산출.

각 지수는 다음 단계로 산출:
1. 원천 변수를 인구 10만명당으로 표준화 (count) 또는 그대로 사용 (rate)
2. StandardScaler 적용
3. PCA → PC1 추출
4. PC1 부호를 의도 방향에 맞게 정렬
5. Min-Max로 [0, 100] 정규화
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


# ── 변수 정의 ────────────────────────────────────────────────────

# WAI — 의료 인력 (10만명당 의사·간호사·전문의)
WAI_COUNT_FEATURES = [
    "doc_의사_전문의",            # 전문의
    "nur_간호사_간호사",           # 간호사
    "spe_내과",
    "spe_외과",
    "spe_응급의학과",
    "spe_소아청소년과",
    "spe_산부인과",
]
WAI_SIGN_ANCHOR = "doc_의사_전문의_per_100k"  # 이 변수와 양의 상관이 되도록 PC1 부호 조정

# IAI — 의료 인프라 (10만명당 시설·장비·병상)
IAI_COUNT_FEATURES = [
    "facilities_clinic",
    "facilities_hospital",
    "facilities_general_hospital",
    "facilities_tertiary",
    "facilities_health_center",
    "facilities_public_health_medical",
    "sr_수술실_병상수",
    "sr_분만실_병상수",
    "eq_전산화단층촬영장치",
    "eq_자기공명영상진단기",
]
IAI_SIGN_ANCHOR = "facilities_general_hospital_per_100k"

# DPI — 수요 압력 (rate/index — 표준화 분모 적용 안 함)
DPI_RATE_FEATURES = [
    "aging_rate",
    "extinction_index_inverted",  # 1/extinction_index — 클수록 소멸 위험 ↑
    "medical_aid_recipient_rate",
    "claims_cost_per_capita",
]
DPI_SIGN_ANCHOR = "aging_rate"  # 고령화↑ ↔ 수요↑


@dataclass
class IndexResult:
    name: str
    features_used: list[str]
    score: pd.Series  # 0-100 scaled
    pc1_raw: pd.Series
    explained_variance: float
    loadings: pd.Series
    note: str = ""


@dataclass
class IndexFit:
    """Phase 6 시뮬레이션용 — baseline에서 학습된 PCA 변환 객체.
    transform()으로 새 데이터를 baseline 기준으로 변환.
    """
    name: str
    features: list[str]
    scaler: StandardScaler
    pca: PCA
    sign: int  # +1 or -1
    pmin: float
    pmax: float

    def transform(self, df: pd.DataFrame) -> pd.Series:
        X = df[self.features].astype(float).values
        Xs = self.scaler.transform(X)
        pc1 = self.pca.transform(Xs).ravel() * self.sign
        if self.pmax > self.pmin:
            return pd.Series(((pc1 - self.pmin) / (self.pmax - self.pmin)) * 100, index=df.index)
        return pd.Series(50.0, index=df.index)


def _add_per_100k_columns(df: pd.DataFrame, count_cols: list[str]) -> pd.DataFrame:
    """count 변수에 _per_100k 컬럼 추가."""
    out = df.copy()
    pop_100k = out["total_population"] / 100_000
    for c in count_cols:
        if c in out.columns:
            out[f"{c}_per_100k"] = out[c] / pop_100k
    return out


def _add_extinction_inverted(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # extinction_index 0이면 inf → 큰 값으로 clip
    out["extinction_index_inverted"] = 1 / out["extinction_index"].replace(0, np.nan)
    out["extinction_index_inverted"] = out["extinction_index_inverted"].fillna(
        out["extinction_index_inverted"].max()
    )
    return out


def _fit_pca_index(
    df: pd.DataFrame, feature_cols: list[str], sign_anchor: str | None, name: str
) -> tuple[pd.Series, pd.Series, float, pd.Series, IndexFit]:
    """공통 PCA 헬퍼. 반환: (score_0_100, pc1_raw, explained_var, loadings, IndexFit)."""
    X = df[feature_cols].astype(float).values
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    pca = PCA(n_components=1).fit(Xs)
    pc1 = pca.transform(Xs).ravel()
    ev = float(pca.explained_variance_ratio_[0])
    loadings = pd.Series(pca.components_[0], index=feature_cols)

    sign = 1
    if sign_anchor and sign_anchor in df.columns:
        corr = np.corrcoef(pc1, df[sign_anchor].astype(float).values)[0, 1]
        if corr < 0:
            sign = -1
            pc1 = -pc1
            loadings = -loadings

    pc1_s = pd.Series(pc1, index=df.index)
    pmin, pmax = float(pc1_s.min()), float(pc1_s.max())
    score = (pc1_s - pmin) / (pmax - pmin) * 100 if pmax > pmin else pd.Series(50.0, index=df.index)
    fit = IndexFit(name=name, features=feature_cols, scaler=scaler, pca=pca, sign=sign, pmin=pmin, pmax=pmax)
    return score, pc1_s, ev, loadings, fit


def _pca_index(df, feature_cols, sign_anchor):
    s, p, e, l, _ = _fit_pca_index(df, feature_cols, sign_anchor, name="")
    return s, p, e, l


def compute_wai(master: pd.DataFrame) -> IndexResult:
    """Workforce Adequacy Index — 의료 인력 적정성."""
    df = _add_per_100k_columns(master, WAI_COUNT_FEATURES)
    features = [f"{c}_per_100k" for c in WAI_COUNT_FEATURES]
    score, pc1, ev, loadings = _pca_index(df, features, WAI_SIGN_ANCHOR)
    return IndexResult(
        name="WAI",
        features_used=features,
        score=score,
        pc1_raw=pc1,
        explained_variance=ev,
        loadings=loadings,
        note="시·도 단위 HIRA 인력을 시·군·구 인구비례로 분배 — 시·도 내 시·군·구는 동일 per_100k.",
    )


def compute_iai(master: pd.DataFrame) -> IndexResult:
    """Infrastructure Adequacy Index — 의료 인프라 적정성."""
    df = _add_per_100k_columns(master, IAI_COUNT_FEATURES)
    features = [f"{c}_per_100k" for c in IAI_COUNT_FEATURES]
    score, pc1, ev, loadings = _pca_index(df, features, IAI_SIGN_ANCHOR)
    return IndexResult(
        name="IAI",
        features_used=features,
        score=score,
        pc1_raw=pc1,
        explained_variance=ev,
        loadings=loadings,
        note="시설(facilities_*)은 시·군·구 실측, 장비·특수진료실은 시·도 인구비례 분배.",
    )


def compute_dpi(master: pd.DataFrame) -> IndexResult:
    """Demand Pressure Index — 의료 수요 압력."""
    df = _add_extinction_inverted(master)
    features = DPI_RATE_FEATURES
    score, pc1, ev, loadings = _pca_index(df, features, DPI_SIGN_ANCHOR)
    return IndexResult(
        name="DPI",
        features_used=features,
        score=score,
        pc1_raw=pc1,
        explained_variance=ev,
        loadings=loadings,
        note="값이 클수록 수요 압력 ↑ (고령화·소멸·의료급여·일인당 진료비 모두 ↑ 방향).",
    )


def attach_indices(master: pd.DataFrame) -> pd.DataFrame:
    """master에 WAI, IAI, DPI 컬럼 (그리고 사용된 per_100k 컬럼들도) 추가."""
    out = master.copy()
    out = _add_per_100k_columns(out, WAI_COUNT_FEATURES + IAI_COUNT_FEATURES)
    out = _add_extinction_inverted(out)
    out["wai"] = compute_wai(master).score.values
    out["iai"] = compute_iai(master).score.values
    out["dpi"] = compute_dpi(master).score.values
    return out


def fit_indices(master: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, IndexFit]]:
    """baseline에서 indices를 학습. IndexFit dict를 함께 반환해 transform-only 재계산에 사용."""
    df = _add_per_100k_columns(master.copy(), WAI_COUNT_FEATURES + IAI_COUNT_FEATURES)
    df = _add_extinction_inverted(df)

    wai_feats = [f"{c}_per_100k" for c in WAI_COUNT_FEATURES]
    iai_feats = [f"{c}_per_100k" for c in IAI_COUNT_FEATURES]

    s_wai, _, _, _, fit_wai = _fit_pca_index(df, wai_feats, WAI_SIGN_ANCHOR, "WAI")
    s_iai, _, _, _, fit_iai = _fit_pca_index(df, iai_feats, IAI_SIGN_ANCHOR, "IAI")
    s_dpi, _, _, _, fit_dpi = _fit_pca_index(df, DPI_RATE_FEATURES, DPI_SIGN_ANCHOR, "DPI")
    df["wai"] = s_wai.values
    df["iai"] = s_iai.values
    df["dpi"] = s_dpi.values
    return df, {"WAI": fit_wai, "IAI": fit_iai, "DPI": fit_dpi}


def transform_indices(master_modified: pd.DataFrame, fits: dict[str, IndexFit]) -> pd.DataFrame:
    """baseline에서 학습한 PCA·스케일·정규화 기준을 그대로 적용해 indices 재계산.
    시뮬레이션 전·후를 동일 좌표계에서 비교하기 위함.
    """
    df = _add_per_100k_columns(master_modified.copy(), WAI_COUNT_FEATURES + IAI_COUNT_FEATURES)
    df = _add_extinction_inverted(df)
    df["wai"] = fits["WAI"].transform(df).values
    df["iai"] = fits["IAI"].transform(df).values
    df["dpi"] = fits["DPI"].transform(df).values
    return df


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    from . import paths

    master = pd.read_csv(paths.PROCESSED / "master_dataset.csv", encoding="utf-8-sig")

    print(f"input: {master.shape}")
    print()

    for fn, name in [(compute_wai, "WAI"), (compute_iai, "IAI"), (compute_dpi, "DPI")]:
        r = fn(master)
        print(f"━━━ {r.name} ━━━")
        print(f"  features: {r.features_used}")
        print(f"  PC1 explained variance: {r.explained_variance:.1%}")
        print(f"  loadings:")
        for f, ld in r.loadings.sort_values(ascending=False).items():
            print(f"    {ld:+.3f}  {f}")
        # face validity
        s = r.score.copy()
        s.index = master["sido"] + " " + master["sgg"]
        print(f"  TOP 5:")
        for k, v in s.nlargest(5).items():
            print(f"    {v:6.2f}  {k}")
        print(f"  BOTTOM 5:")
        for k, v in s.nsmallest(5).items():
            print(f"    {v:6.2f}  {k}")
        print()

    out = attach_indices(master)
    out_path = paths.PROCESSED / "master_with_indices.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"saved → {out_path}")
