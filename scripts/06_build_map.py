"""Phase 7+ — GitHub Pages용 인터랙티브 지도 빌더.

Folium 기반. data/geo/skorea_sgg.geojson에 시도·시군구 매스터 매칭 정보 부여 후
HRI 값을 choropleth로 색칠. 클릭/호버 시 시·군·구 풍선 정보 표시.

출력: docs/index.html
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

import sys
sys.path.insert(0, "src")
from hri import paths
from hri.loader import _normalize_one_sgg, apply_admin_changes

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

# code prefix → 시도 풀네임
SIDO_CODE_MAP = {
    "11": "서울특별시", "21": "부산광역시", "22": "대구광역시", "23": "인천광역시",
    "24": "광주광역시", "25": "대전광역시", "26": "울산광역시", "29": "세종특별자치시",
    "31": "경기도", "32": "강원특별자치도", "33": "충청북도", "34": "충청남도",
    "35": "전북특별자치도", "36": "전라남도", "37": "경상북도", "38": "경상남도",
    "39": "제주특별자치도",
}


def enrich_geojson(geo_path: Path) -> dict:
    """Feature 마다 sido / sgg_master 속성을 부여 (master 데이터 키와 일치하도록)."""
    with open(geo_path, encoding="utf-8") as f:
        g = json.load(f)
    for ft in g["features"]:
        p = ft["properties"]
        code = str(p.get("code", ""))
        sido = SIDO_CODE_MAP.get(code[:2], None)
        name = p.get("name", "")
        # 세종은 단일 단위
        if sido == "세종특별자치시":
            sgg = "세종특별자치시"
        else:
            sgg = _normalize_one_sgg(sido, name)
        sido, sgg = apply_admin_changes(sido, sgg)
        p["sido"] = sido
        p["sgg_master"] = sgg
        p["join_key"] = f"{sido}|{sgg}" if sido else None
    return g


def main():
    try:
        import folium
        from folium import GeoJsonTooltip
        import branca.colormap as cm
    except ImportError as e:
        raise SystemExit(f"folium 미설치. conda install -n hri folium branca -c conda-forge\n{e}")

    df = pd.read_csv(paths.PROCESSED / "hri_with_clusters.csv", encoding="utf-8-sig")
    df["join_key"] = df["sido"] + "|" + df["sgg"]
    by_key = df.set_index("join_key")

    geo = enrich_geojson(paths.DATA / "geo" / "skorea_sgg.geojson")

    matched, unmatched = 0, []
    for ft in geo["features"]:
        k = ft["properties"].get("join_key")
        if k in by_key.index:
            row = by_key.loc[k]
            ft["properties"]["hri"] = float(row["hri"])
            ft["properties"]["wai"] = float(row["wai"])
            ft["properties"]["iai"] = float(row["iai"])
            ft["properties"]["dpi"] = float(row["dpi"])
            ft["properties"]["cluster_name"] = row["cluster_name"]
            ft["properties"]["total_population"] = int(row["total_population"])
            ft["properties"]["aging_rate"] = round(float(row["aging_rate"]), 2)
            ft["properties"]["outflow_cost_ratio"] = round(float(row["outflow_cost_ratio"]), 3)
            ft["properties"]["unmet_std_pct"] = round(float(row["unmet_std_pct"]), 2)
            ft["properties"]["medical_aid_recipient_rate"] = round(float(row["medical_aid_recipient_rate"]), 2)
            matched += 1
        else:
            unmatched.append((ft["properties"].get("name"), ft["properties"].get("sido")))

    print(f"matched: {matched} / {len(geo['features'])} features")
    if unmatched:
        print(f"unmatched ({len(unmatched)}):")
        for n, s in unmatched[:20]:
            print(f"  {s} | {n}")

    # ── 지도 생성 ──
    # 배경 타일 없이 시·군·구 폴리곤만 그린다 (CARTO 타일은 API 키를 요구하게 바뀌어 워터마크가 뜸)
    m = folium.Map(location=[36.5, 127.8], zoom_start=7, tiles=None)
    m.get_root().header.add_child(folium.Element("<style>.leaflet-container{background:#f4f6f8 !important}</style>"))

    # 컬러맵
    hri_vals = [ft["properties"].get("hri") for ft in geo["features"] if "hri" in ft["properties"]]
    hri_min, hri_max = min(hri_vals), max(hri_vals)
    colormap = cm.LinearColormap(
        colors=["#cb181d", "#fb6a4a", "#fdae6b", "#fee08b", "#a6d96a", "#1a9850"],
        vmin=hri_min, vmax=hri_max, caption="HRI 점수 (높을수록 의료 복원 수준 ↑)",
    )

    def style_function(feature):
        v = feature["properties"].get("hri")
        if v is None:
            return {"fillColor": "#d9d9d9", "color": "white", "weight": 0.4, "fillOpacity": 0.4}
        return {"fillColor": colormap(v), "color": "white", "weight": 0.4, "fillOpacity": 0.82}

    def highlight(feature):
        return {"weight": 2.5, "color": "#222"}

    tooltip = GeoJsonTooltip(
        fields=[
            "sido", "sgg_master", "cluster_name",
            "hri", "wai", "iai", "dpi",
            "total_population", "aging_rate",
            "outflow_cost_ratio", "unmet_std_pct", "medical_aid_recipient_rate",
        ],
        aliases=[
            "시·도", "시·군·구", "유형",
            "HRI", "WAI(인력)", "IAI(인프라)", "DPI(수요)",
            "총인구", "고령화율(%)",
            "관외이용률", "미충족의료율(%)", "의료급여율(%)",
        ],
        localize=True, sticky=False, labels=True,
        style="background-color: #fff; border: 1px solid #888; border-radius: 4px; "
              "box-shadow: 2px 2px 4px rgba(0,0,0,0.15); padding: 6px;",
    )

    folium.GeoJson(
        geo,
        name="HRI",
        style_function=style_function,
        highlight_function=highlight,
        tooltip=tooltip,
    ).add_to(m)
    colormap.add_to(m)

    # 클러스터 색상 범례 (별도 HTML)
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 10px; z-index: 9999;
                background: rgba(255,255,255,0.95); padding: 10px 14px; border-radius: 6px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.25); font-family: -apple-system, sans-serif;
                font-size: 12px; line-height: 1.7;">
      <b>지역 의료 복원 지수 (HRI)</b><br>
      전국 229 시·군·구 · 2024년 기준<br>
      <span style="color:#666; font-size: 11px;">
        WAI(인력) + IAI(인프라) − DPI(수요) ⇒ LASSO 가중치<br>
        종속변수: 관외 의료이용률 (KOSIS 거주지 기준)
      </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    out = DOCS / "index.html"
    m.save(str(out))
    print(f"\nsaved → {out}")
    print(f"size: {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
