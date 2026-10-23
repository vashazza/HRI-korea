"""Verify sgg name matching across all datasets."""

import warnings
warnings.filterwarnings("ignore")

from hri import loader

pop = loader.population_totals(2024)[["sido", "sgg"]].copy()
pop["key"] = pop["sido"] + "|" + pop["sgg"]
print(f"pop: {len(pop)}  unique keys: {pop['key'].nunique()}")

dup = pop[pop.duplicated("sgg", keep=False)].sort_values("sgg")
print(f"\nduplicate sgg names across sido: {dup['sgg'].nunique()} sgg ({len(dup)} rows)")
print(dup.head(20).to_string())

for name, df_loader in [
    ("unmet_care", loader.load_unmet_care),
    ("medical_aid", loader.load_welfare_medical_aid),
    ("outflow", loader.load_outflow_ratio),
    ("facilities", loader.load_hira_facilities),
]:
    df = df_loader()
    df["key"] = df["sido"] + "|" + df["sgg"]
    miss = set(pop["key"]) - set(df["key"])
    extra = set(df["key"]) - set(pop["key"])
    print(f"\n=== {name}: rows={len(df)}, in pop but missing here={len(miss)}, extra here not in pop={len(extra)}")
    if miss:
        print(f"  miss(pop has, {name} missing): {sorted(miss)[:20]}")
    if extra:
        print(f"  extra({name} has, pop missing): {sorted(extra)[:20]}")
