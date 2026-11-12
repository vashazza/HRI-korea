"""Phase 7 (선택) — 정적 시각화."""

import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from hri import paths

# 한글 폰트 설정 (macOS)
for f in ["AppleGothic", "AppleSDGothicNeo-Regular", "NanumGothic"]:
    try:
        fm.findfont(f, fallback_to_default=False)
        plt.rcParams["font.family"] = f
        break
    except Exception:
        pass
plt.rcParams["axes.unicode_minus"] = False

FIG_DIR = paths.FIGURES
FIG_DIR.mkdir(parents=True, exist_ok=True)

hri_df = pd.read_csv(paths.PROCESSED / "hri_with_clusters.csv", encoding="utf-8-sig")
sim_df = pd.read_csv(paths.PROCESSED / "scenario_simulations.csv", encoding="utf-8-sig")

# 군집 색 — HRI 평균이 높은 군집부터 Okabe-Ito 팔레트(색각 이상에도 구분됨) 순서로 배정
_PALETTE = ["#0072B2", "#56B4E9", "#009E73", "#E69F00", "#D55E00", "#CC79A7", "#999999", "#000000"]
_order = hri_df.groupby("cluster_name")["hri"].mean().sort_values(ascending=False).index
CLUSTER_COLORS = dict(zip(_order, _PALETTE))


# 1) HRI 분포 히스토그램 + 클러스터별
fig, ax = plt.subplots(figsize=(9, 5))
for name, col in CLUSTER_COLORS.items():
    sub = hri_df[hri_df["cluster_name"] == name]
    ax.hist(sub["hri"], bins=20, alpha=0.65, label=f"{name} (n={len(sub)})", color=col, edgecolor="white")
ax.set_xlabel("HRI 점수 (0–100)")
ax.set_ylabel("시·군·구 수")
ax.set_title("지역 의료 복원 지수(HRI) 분포 — 클러스터별 (n=229)")
ax.legend(loc="upper right", frameon=False)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(FIG_DIR / "01_hri_distribution.png", dpi=150)
plt.close(fig)
print("saved 01_hri_distribution.png")


# 2) 클러스터 프로파일 레이더 차트
labels = ["WAI", "IAI", "DPI(반전)", "HRI"]
angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
for name, col in CLUSTER_COLORS.items():
    sub = hri_df[hri_df["cluster_name"] == name]
    vals = [sub["wai"].mean(), sub["iai"].mean(), 100 - sub["dpi"].mean(), sub["hri"].mean()]
    vals += vals[:1]
    ax.plot(angles, vals, "o-", lw=2, label=name, color=col)
    ax.fill(angles, vals, alpha=0.15, color=col)
ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels, size=11)
ax.set_yticks([20, 40, 60, 80])
ax.set_yticklabels(["20", "40", "60", "80"], size=8)
ax.set_ylim(0, 100)
ax.set_title("클러스터 평균 프로파일 (DPI는 반전: 100 - DPI)", pad=20)
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), frameon=False)
fig.tight_layout()
fig.savefig(FIG_DIR / "02_cluster_radar.png", dpi=150)
plt.close(fig)
print("saved 02_cluster_radar.png")


# 3) 시나리오 × 클러스터 ΔHRI 박스플롯
fig, axes = plt.subplots(1, 4, figsize=(14, 5), sharey=True)
for ax, sc in zip(axes, ["S1", "S2", "S3", "S4"]):
    sub = sim_df[sim_df["scenario"] == sc]
    data, labels_b, colors_b = [], [], []
    for name, col in CLUSTER_COLORS.items():
        d = sub[sub["cluster_name"] == name]["delta_hri"]
        if len(d) > 0:
            data.append(d)
            labels_b.append(name.replace(" ", "\n"))
            colors_b.append(col)
    bp = ax.boxplot(data, patch_artist=True, labels=labels_b, widths=0.6)
    for patch, c in zip(bp["boxes"], colors_b):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
    ax.axhline(0, color="gray", lw=0.7, ls="--")
    ax.set_title(sc)
    ax.set_ylabel("ΔHRI") if sc == "S1" else None
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=90, labelsize=7)
fig.suptitle("시나리오별 클러스터 ΔHRI 분포", y=1.02)
fig.tight_layout()
fig.savefig(FIG_DIR / "03_scenario_boxplot.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("saved 03_scenario_boxplot.png")


# 4) HRI vs 관외이용률 산점도 (외부 검증 시각화)
fig, ax = plt.subplots(figsize=(8, 6))
for name, col in CLUSTER_COLORS.items():
    sub = hri_df[hri_df["cluster_name"] == name]
    ax.scatter(sub["hri"], sub["outflow_cost_ratio"], alpha=0.6, s=35, color=col, label=name, edgecolors="white", linewidths=0.4)

# 회귀선
from numpy.polynomial import polynomial as P
z = np.polyfit(hri_df["hri"], hri_df["outflow_cost_ratio"], 1)
xs = np.linspace(hri_df["hri"].min(), hri_df["hri"].max(), 100)
ax.plot(xs, np.polyval(z, xs), "k--", lw=1.5, alpha=0.6, label=f"OLS y = {z[0]:+.4f}x + {z[1]:.3f}")

r = hri_df[["hri", "outflow_cost_ratio"]].corr().iloc[0, 1]
ax.set_xlabel("HRI (의료 복원 지수)")
ax.set_ylabel("관외 의료이용률 (cost 기준)")
ax.set_title(f"HRI vs 관외 의료이용률  (Pearson r = {r:.3f})")
ax.legend(loc="upper right", frameon=False)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(FIG_DIR / "04_hri_vs_outflow.png", dpi=150)
plt.close(fig)
print("saved 04_hri_vs_outflow.png")


# 5) WAI/IAI/DPI 3축 산점도 (클러스터 구분)
fig = plt.figure(figsize=(11, 4))
for i, (xn, yn) in enumerate([("wai", "iai"), ("wai", "dpi"), ("iai", "dpi")], start=1):
    ax = fig.add_subplot(1, 3, i)
    for name, col in CLUSTER_COLORS.items():
        sub = hri_df[hri_df["cluster_name"] == name]
        ax.scatter(sub[xn], sub[yn], alpha=0.6, s=30, color=col, label=name, edgecolors="white", linewidths=0.4)
    ax.set_xlabel(xn.upper())
    ax.set_ylabel(yn.upper())
    if i == 1:
        ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.grid(alpha=0.3)
fig.suptitle("WAI·IAI·DPI 페어플롯 (클러스터 색상)")
fig.tight_layout()
fig.savefig(FIG_DIR / "05_indices_pairs.png", dpi=150)
plt.close(fig)
print("saved 05_indices_pairs.png")

print(f"\nall figures saved → {FIG_DIR}")
