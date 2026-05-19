"""마스터 데이터셋 요약 통계 + face validity 확인."""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd

from hri import paths

master = pd.read_csv(paths.PROCESSED / "master_dataset.csv", encoding="utf-8-sig")
print(f"shape: {master.shape}")
print(f"인구 합계: {master['total_population'].sum():,.0f}")

print("\n=== 결측 현황 (Top 20) ===")
nulls = master.isna().sum()
print(nulls[nulls > 0].sort_values(ascending=False).head(20).to_string())

print("\n=== 종속변수 (옵션 B): unmet_std_pct ===")
print(master["unmet_std_pct"].describe().round(2))

print("\n=== 보조 종속변수: outflow_cost_ratio ===")
print(master["outflow_cost_ratio"].describe().round(3))

print("\n=== DPI 핵심 변수 ===")
for c in ["aging_rate", "medical_aid_recipient_rate", "extinction_index", "claims_cost_per_capita"]:
    if c in master.columns:
        print(f"  {c}: mean={master[c].mean():.3f}, min={master[c].min():.3f}, max={master[c].max():.3f}")

print("\n=== Face validity ===")
print("\n[미충족의료율 상위 10 — 의료 접근성 가장 나쁜 곳]")
print(master.nlargest(10, "unmet_std_pct")[["sido", "sgg", "unmet_std_pct", "aging_rate", "outflow_cost_ratio"]].to_string())

print("\n[관외이용률 상위 10 — 자체 의료 가장 부족한 곳]")
print(master.nlargest(10, "outflow_cost_ratio")[["sido", "sgg", "outflow_cost_ratio", "facilities_general_hospital", "aging_rate"]].to_string())

print("\n[의료급여 수급률 상위 10 — 저소득층 비중 가장 높은 곳]")
print(master.nlargest(10, "medical_aid_recipient_rate")[["sido", "sgg", "medical_aid_recipient_rate", "aging_rate"]].to_string())

print("\n[종합병원 수 상위 10]")
print(master.nlargest(10, "facilities_general_hospital")[["sido", "sgg", "total_population", "facilities_general_hospital", "facilities_tertiary"]].to_string())
