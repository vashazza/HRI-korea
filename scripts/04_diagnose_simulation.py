"""시뮬레이션 마스크와 부호 진단."""
import warnings
warnings.filterwarnings("ignore")

import json
import pandas as pd

from hri import paths
from hri.hri import HRIWeights, compute_hri
from hri.indices import fit_indices, transform_indices

base = pd.read_csv(paths.PROCESSED / "hri_with_clusters.csv", encoding="utf-8-sig")
master = pd.read_csv(paths.PROCESSED / "master_dataset.csv", encoding="utf-8-sig")
master = master.merge(base[["sido", "sgg", "cluster_id", "cluster_name"]], on=["sido", "sgg"])

with open(paths.REPORTS / "hri_weights.json") as f:
    meta = json.load(f)
w = HRIWeights(**meta["weights"])

base_df, fits = fit_indices(master)
base_df["hri"] = compute_hri(base_df, w)

print("=== WAI 분포 ===")
print(base_df["wai"].describe())
print("\nWAI unique values:", sorted(base_df["wai"].unique())[:20])
q30 = base_df["wai"].quantile(0.30)
print(f"\nQuantile 0.30 = {q30:.3f}")
print(f"  count <  q30: {(base_df['wai'] < q30).sum()}")
print(f"  count <= q30: {(base_df['wai'] <= q30).sum()}")
print(f"  count == 0:   {(base_df['wai'] == 0).sum()}")

print("\n=== IAI 분포 ===")
print(base_df["iai"].describe())
q30 = base_df["iai"].quantile(0.30)
print(f"Quantile 0.30 = {q30:.3f}, count < q30: {(base_df['iai'] < q30).sum()}")

print("\n=== facilities_public_health_medical 분포 ===")
print(master["facilities_public_health_medical"].describe())
per_100k = master["facilities_public_health_medical"] / (master["total_population"] / 100_000)
print(f"per_100k describe:")
print(per_100k.describe())
print(f"count == 0: {(per_100k == 0).sum()}")

print("\n=== WAI 부호·HRI 산출 검증 ===")
# WAI 단순 증가시켜 보고 HRI 어떻게 변하는지
sim = master.copy()
sim_idx = sim.index[:5]
print("baseline HRI for first 5 rows:")
print(base_df.iloc[:5][["sido", "sgg", "wai", "iai", "dpi", "hri"]].to_string())

# 모든 시군구에서 spe_내과만 +50% 늘려봄
sim2 = master.copy()
sim2["spe_내과"] *= 1.5
sim2["doc_의사_전문의"] *= 1.5
after = transform_indices(sim2, fits)
after["hri"] = compute_hri(after, w)
diff = after["hri"] - base_df["hri"]
print(f"\n[ALL rows] 내과+전문의 +50% → ΔHRI mean: {diff.mean():.3f}, ΔWAI mean: {(after['wai']-base_df['wai']).mean():.3f}")

# DPI는 어떻게 변하는지? 의료급여 늘려보자
sim3 = master.copy()
sim3["medical_aid_recipients"] *= 1.5
after = transform_indices(sim3, fits)
after["hri"] = compute_hri(after, w)
diff = after["hri"] - base_df["hri"]
print(f"[ALL rows] medical_aid +50% → ΔHRI mean: {diff.mean():.3f}, ΔDPI mean: {(after['dpi']-base_df['dpi']).mean():.3f}")

# IAI 늘려보자
sim4 = master.copy()
sim4["facilities_clinic"] += 50
after = transform_indices(sim4, fits)
after["hri"] = compute_hri(after, w)
diff = after["hri"] - base_df["hri"]
print(f"[ALL rows] clinic +50 → ΔHRI mean: {diff.mean():.3f}, ΔIAI mean: {(after['iai']-base_df['iai']).mean():.3f}")

print("\n=== HRI 가중치·부호 확인 ===")
print(f"raw_coef: {w.raw_coef}")
print(f"weights (|coef| 정규화): w_wai={w.w_wai:.3f}, w_iai={w.w_iai:.3f}, w_dpi={w.w_dpi:.3f}")
print(f"HRI 공식: HRI = +w_wai·WAI + w_iai·IAI - w_dpi·DPI")
print(f"실제 raw coef 부호:")
print(f"  wai → outflow : {w.raw_coef['wai']:+.5f} ({'+' if w.raw_coef['wai']>0 else '-'})")
print(f"  iai → outflow : {w.raw_coef['iai']:+.5f}")
print(f"  dpi → outflow : {w.raw_coef['dpi']:+.5f}")
