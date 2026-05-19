"""Diagnose why some metropolitan districts are missing in facilities."""

import warnings
warnings.filterwarnings("ignore")

from hri import loader

f = loader.load_hira_facilities()
print(f"facilities total: {len(f)}")
print(f"\nsido counts in facilities:")
print(f.groupby("sido").size().to_string())

print(f"\n광주·대구 facilities rows:")
print(f[f["sido"].isin(["광주광역시", "대구광역시"])].iloc[:, :3].to_string())

print(f"\n=== extra (facilities has, pop missing) — full list ===")
pop = loader.population_totals(2024)
pop_keys = set(pop["sido"] + "|" + pop["sgg"])
f_keys = set(f["sido"] + "|" + f["sgg"])
extra = sorted(f_keys - pop_keys)
print(f"total: {len(extra)}")
for k in extra:
    print(" ", k)
