"""Phase 5 — 시·군·구 유형 클러스터링.

WAI/IAI/DPI 3차원 공간에서 K-Means + 계층 군집(Ward)으로 지역 유형 도출.
- 최적 K: Elbow(SSE) + Silhouette score
- 교차 검증: K-Means 결과와 Ward 결과의 ARI(Adjusted Rand Index)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler


CLUSTER_FEATURES = ["wai", "iai", "dpi"]


@dataclass
class ClusterDiagnostics:
    k: int
    sse: float
    silhouette: float
    ward_ari: float


def diagnose_k(df: pd.DataFrame, k_range=(3, 4, 5, 6, 7, 8),
               random_state: int = 42) -> list[ClusterDiagnostics]:
    """K별 SSE·Silhouette·Ward ARI 계산."""
    X = StandardScaler().fit_transform(df[CLUSTER_FEATURES].values)
    Z = linkage(X, method="ward")
    results = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=20, random_state=random_state).fit(X)
        ward_labels = fcluster(Z, t=k, criterion="maxclust")
        results.append(
            ClusterDiagnostics(
                k=k,
                sse=float(km.inertia_),
                silhouette=float(silhouette_score(X, km.labels_)),
                ward_ari=float(adjusted_rand_score(km.labels_, ward_labels)),
            )
        )
    return results


def cluster_regions(df: pd.DataFrame, k: int, random_state: int = 42) -> pd.DataFrame:
    """K-Means 군집 라벨 + 클러스터 중심 거리 부여."""
    out = df.copy()
    X = StandardScaler().fit_transform(out[CLUSTER_FEATURES].values)
    km = KMeans(n_clusters=k, n_init=20, random_state=random_state).fit(X)
    out["cluster_id"] = km.labels_
    return out, km


def profile_clusters(df: pd.DataFrame) -> pd.DataFrame:
    """클러스터별 평균 프로파일."""
    profile_vars = [
        "wai", "iai", "dpi",
        "total_population", "aging_rate", "medical_aid_recipient_rate",
        "outflow_cost_ratio", "unmet_std_pct",
        "facilities_general_hospital", "facilities_tertiary",
        "doc_의사_전문의_per_100k", "nur_간호사_간호사_per_100k",
        "hri",
    ]
    use_vars = [c for c in profile_vars if c in df.columns]
    prof = df.groupby("cluster_id", as_index=False).agg(
        {**{c: "mean" for c in use_vars}, "sgg": "count"}
    )
    prof = prof.rename(columns={"sgg": "n_sgg"})
    return prof


def name_clusters(profile: pd.DataFrame) -> dict[int, str]:
    """군집 평균(WAI·IAI·DPI)의 패턴으로 이름을 붙인다. 이름은 군집마다 달라야 한다."""
    names: dict[int, str] = {}
    for rank, row in enumerate(profile.sort_values("hri", ascending=False).itertuples(), start=1):
        if row.wai > 40:
            label = "대형병원 밀집 도심형"
        elif row.dpi > 65:
            label = "고령지역 인프라보유형" if row.iai >= 30 else "고령지역 자원부족형"
        elif row.iai > 50:
            label = "도시 거점형"
        elif row.dpi < 25:
            label = "대도시·신도시 저수요형"
        else:
            label = "중소도시 중간형"
        if label in names.values():   # 규칙이 두 군집을 못 가르면 HRI 순위를 붙여 구분
            label = f"{label} {rank}"
        names[int(row.cluster_id)] = label
    return names


if __name__ == "__main__":
    import json
    import warnings
    warnings.filterwarnings("ignore")

    from . import paths

    df = pd.read_csv(paths.PROCESSED / "hri_results.csv", encoding="utf-8-sig")

    print(f"input: {df.shape}")
    print()

    # 1) 최적 K 진단
    print("━━━ K 진단 (SSE↓·Silhouette↑·Ward ARI↑) ━━━")
    diags = diagnose_k(df)
    print(f"  {'K':>3} {'SSE':>10} {'Silhouette':>12} {'WardARI':>10}")
    for d in diags:
        print(f"  {d.k:>3} {d.sse:>10.2f} {d.silhouette:>12.3f} {d.ward_ari:>10.3f}")
    print()

    # silhouette + ARI 평균으로 최적 K 선택
    best = max(diags, key=lambda d: d.silhouette + d.ward_ari * 0.5)
    print(f"→ 최적 K = {best.k} (silhouette={best.silhouette:.3f}, ward_ari={best.ward_ari:.3f})")
    print()

    # 2) 클러스터링 실행
    clustered, _ = cluster_regions(df, k=best.k)

    # 3) 프로파일 산출
    profile = profile_clusters(clustered)
    print("━━━ 클러스터 프로파일 ━━━")
    print(profile.to_string(float_format=lambda x: f"{x:.2f}"))
    print()

    # 4) 이름 부여
    names = name_clusters(profile)
    clustered["cluster_name"] = clustered["cluster_id"].map(names)
    print("━━━ 클러스터 명명 ━━━")
    for cid, nm in sorted(names.items()):
        n = (clustered["cluster_id"] == cid).sum()
        print(f"  cluster {cid}: {nm} (n={n})")
    print()

    # 5) 클러스터별 대표 시·군·구
    print("━━━ 클러스터별 대표 시·군·구 (HRI 기준 상·하위) ━━━")
    for cid in sorted(clustered["cluster_id"].unique()):
        sub = clustered[clustered["cluster_id"] == cid]
        nm = names[cid]
        print(f"\n[{cid}] {nm} (n={len(sub)})")
        top = sub.nlargest(3, "hri")[["sido", "sgg", "hri"]]
        bot = sub.nsmallest(3, "hri")[["sido", "sgg", "hri"]]
        print(f"  TOP: {', '.join(f'{r.sido} {r.sgg}({r.hri:.1f})' for r in top.itertuples())}")
        print(f"  BOT: {', '.join(f'{r.sido} {r.sgg}({r.hri:.1f})' for r in bot.itertuples())}")
    print()

    # 6) 저장
    out_csv = paths.PROCESSED / "hri_with_clusters.csv"
    clustered.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"saved → {out_csv}")

    out_prof = paths.PROCESSED / "cluster_profiles.csv"
    prof_with_names = profile.copy()
    prof_with_names["cluster_name"] = prof_with_names["cluster_id"].map(names)
    prof_with_names.to_csv(out_prof, index=False, encoding="utf-8-sig")
    print(f"saved → {out_prof}")
