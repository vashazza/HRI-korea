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


# ── 가중치 슬라이더 패널 ──────────────────────────────────────────
# 슬라이더를 움직이면 브라우저에서 hri.compute_hri와 같은 식으로 다시 계산한다:
# raw = w1·WAI + w2·IAI − w3·DPI → 229곳 기준 min-max 0~100 → 순위 → 재채색.

PANEL_CSS = """<style>
.hri-panel{position:fixed;z-index:1000;width:260px;padding:10px 12px;border-radius:8px;
  background:rgba(255,255,255,.96);box-shadow:0 1px 4px rgba(0,0,0,.25);color:#222;
  font:12px/1.5 -apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
#hri-controls{top:10px;left:56px}
#hri-region{bottom:24px;left:10px;display:none}
.hri-panel h4{margin:0 0 2px;font-size:13px}
.hri-sub{color:#666;font-size:11px}
.hri-row{display:grid;grid-template-columns:82px 1fr 40px;align-items:center;gap:6px;margin:4px 0}
.hri-row input{width:100%;margin:0}
.hri-num{text-align:right;font-variant-numeric:tabular-nums}
.hri-presets{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0 4px}
.hri-presets button{font:inherit;font-size:11px;padding:2px 7px;border:1px solid #bbb;border-radius:4px;
  background:#fff;cursor:pointer}
.hri-presets button.on{background:#222;color:#fff;border-color:#222}
#hri-region table{width:100%;border-collapse:collapse;margin-top:4px}
#hri-region td{padding:1px 0}
#hri-region td:last-child{text-align:right;font-variant-numeric:tabular-nums}
.hri-close{float:right;border:0;background:none;font-size:15px;line-height:1;cursor:pointer;color:#888}
@media (max-width:600px){
  .hri-panel{width:auto;left:10px;right:10px;font-size:11px}
  #hri-controls{top:auto;bottom:10px}
  #hri-region{bottom:auto;top:62px}
  .legend.leaflet-control{transform:scale(.72);transform-origin:top right}
}
</style>"""

PANEL_HTML = """
<div id="hri-controls" class="hri-panel">
  <h4>지역 의료 복원 지수 (HRI)</h4>
  <div class="hri-sub">229 시·군·구 · 2024년 기준 (간호사·기관 수는 2026Q1)</div>
  <div class="hri-sub" style="margin:4px 0 2px">HRI = w₁·WAI + w₂·IAI − w₃·DPI → 229곳 기준 0~100</div>
  <div class="hri-row"><label for="hri-w0">w₁ 인력 WAI</label>
    <input id="hri-w0" type="range" min="0" max="1" step="any"><span id="hri-v0" class="hri-num"></span></div>
  <div class="hri-row"><label for="hri-w1">w₂ 인프라 IAI</label>
    <input id="hri-w1" type="range" min="0" max="1" step="any"><span id="hri-v1" class="hri-num"></span></div>
  <div class="hri-row"><label for="hri-w2">w₃ 수요 DPI</label>
    <input id="hri-w2" type="range" min="0" max="1" step="any"><span id="hri-v2" class="hri-num"></span></div>
  <div class="hri-presets" id="hri-presets"></div>
  <div class="hri-sub">가중치는 비율만 결과에 영향을 준다 (전체 배율은 0~100 정규화에서 사라짐).
    CI 하한·상한은 부트스트랩 95% 구간. 지역을 클릭하면 순위 변화가 보인다.</div>
  <div class="hri-sub" style="margin-top:4px">
    <a href="https://github.com/vashazza/HRI-korea" target="_blank" rel="noopener">코드 · 방법 · 한계</a></div>
</div>
<div id="hri-region" class="hri-panel"></div>
"""

PANEL_JS = """
window.addEventListener("load", function () {
  var layer = __LAYER__;
  var R = __REGIONS__, P = __PRESETS__, COLORS = __COLORS__;
  var keys = Object.keys(R), score = {}, rank = {}, selected = null;
  var sliders = [0, 1, 2].map(function (i) { return document.getElementById("hri-w" + i); });

  var RGB = COLORS.map(function (h) { return [1, 3, 5].map(function (i) { return parseInt(h.substr(i, 2), 16); }); });
  function color(v) {
    var t = Math.max(0, Math.min(1, v / 100)) * (RGB.length - 1);
    var i = Math.min(Math.floor(t), RGB.length - 2), f = t - i;
    return "rgb(" + RGB[i].map(function (a, j) { return Math.round(a + (RGB[i + 1][j] - a) * f); }).join(",") + ")";
  }
  function style(feature) {
    var k = feature.properties.join_key;
    if (!(k in score)) return {fillColor: "#d9d9d9", color: "white", weight: 0.4, fillOpacity: 0.4};
    return {fillColor: color(score[k]), color: "white", weight: 0.4, fillOpacity: 0.82};
  }
  function fmt(v) { return (+v).toFixed(1); }

  function recompute() {
    var w = sliders.map(function (s) { return parseFloat(s.value); });
    var raw = keys.map(function (k) { return w[0] * R[k].wai + w[1] * R[k].iai - w[2] * R[k].dpi; });
    var lo = Math.min.apply(null, raw), hi = Math.max.apply(null, raw);
    keys.forEach(function (k, i) { score[k] = hi > lo ? (raw[i] - lo) / (hi - lo) * 100 : 50; });
    keys.slice().sort(function (a, b) { return score[b] - score[a]; })
      .forEach(function (k, i) { rank[k] = i + 1; });
    layer.eachLayer(function (l) {
      var p = l.feature.properties;
      if (p.join_key in score) { p.hri_now = Math.round(score[p.join_key] * 10) / 10; p.rank_now = rank[p.join_key]; }
    });
    layer.setStyle(style);
    sliders.forEach(function (s, i) { document.getElementById("hri-v" + i).textContent = (+s.value).toFixed(3); });
    if (selected) showRegion(selected);
  }

  function showRegion(k) {
    selected = k;
    var r = R[k], d = r.rank0 - rank[k];
    var change = d > 0 ? "▲ " + d : d < 0 ? "▼ " + (-d) : "변화 없음";
    var el = document.getElementById("hri-region");
    el.innerHTML = '<button class="hri-close" aria-label="닫기">×</button>' +
      "<h4>" + r.sido + " " + r.sgg + "</h4><div class='hri-sub'>" + r.cluster + "</div><table>" +
      "<tr><td>WAI · IAI · DPI</td><td>" + [r.wai, r.iai, r.dpi].map(fmt).join(" · ") + "</td></tr>" +
      "<tr><td>HRI (LASSO 가중치)</td><td>" + fmt(r.hri0) + " · " + r.rank0 + "위</td></tr>" +
      "<tr><td>HRI (현재 가중치)</td><td>" + fmt(score[k]) + " · " + rank[k] + "위</td></tr>" +
      "<tr><td>순위 변화</td><td>" + change + "</td></tr></table>";
    el.style.display = "block";
    el.querySelector(".hri-close").onclick = function () { el.style.display = "none"; selected = null; };
  }

  function markPreset(name) {
    document.querySelectorAll("#hri-presets button").forEach(function (b) {
      b.classList.toggle("on", b.dataset.name === name);
    });
  }
  function setPreset(name) {
    P[name].forEach(function (v, i) { sliders[i].value = v; });
    markPreset(name);
    recompute();
  }
  Object.keys(P).forEach(function (name) {
    var b = document.createElement("button");
    b.textContent = name;
    b.dataset.name = name;
    b.onclick = function () { setPreset(name); };
    document.getElementById("hri-presets").appendChild(b);
  });
  sliders.forEach(function (s) { s.addEventListener("input", function () { markPreset(null); recompute(); }); });

  layer.options.style = style;  // 마우스를 뗄 때 Folium이 부르는 resetStyle이 이 함수를 쓴다
  layer.eachLayer(function (l) { l.on("click", function () { showRegion(l.feature.properties.join_key); }); });
  setPreset("LASSO");
});
"""


def main():
    try:
        import folium
        from folium import GeoJsonTooltip
        import branca.colormap as cm
    except ImportError as e:
        raise SystemExit(f"folium 미설치. conda install -n hri folium branca -c conda-forge\n{e}")

    df = pd.read_csv(paths.PROCESSED / "hri_with_clusters.csv", encoding="utf-8-sig")
    df["join_key"] = df["sido"] + "|" + df["sgg"]
    df["rank"] = df["hri"].rank(ascending=False, method="first").astype(int)
    by_key = df.set_index("join_key")

    meta = json.loads((paths.REPORTS / "hri_weights.json").read_text(encoding="utf-8"))
    w, bs = meta["weights"], meta["bootstrap"]
    presets = {
        "등가중": [1 / 3, 1 / 3, 1 / 3],
        "LASSO": [w["w_wai"], w["w_iai"], w["w_dpi"]],
        "CI 하한": [bs[k]["ci_lo"] for k in ("w_wai", "w_iai", "w_dpi")],
        "CI 상한": [bs[k]["ci_hi"] for k in ("w_wai", "w_iai", "w_dpi")],
    }
    regions = {
        k: {"sido": r.sido, "sgg": r.sgg, "cluster": r.cluster_name,
            "wai": r.wai, "iai": r.iai, "dpi": r.dpi, "hri0": r.hri, "rank0": int(r["rank"])}
        for k, r in by_key.iterrows()
    }

    geo = enrich_geojson(paths.DATA / "geo" / "skorea_sgg.geojson")

    matched, unmatched = 0, []
    for ft in geo["features"]:
        k = ft["properties"].get("join_key")
        if k in by_key.index:
            row = by_key.loc[k]
            ft["properties"]["hri"] = float(row["hri"])
            ft["properties"]["hri_now"] = round(float(row["hri"]), 1)
            ft["properties"]["rank_now"] = int(row["rank"])
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

    # 컬러맵 — HRI는 항상 229곳 기준 0~100으로 정규화되므로 범위 고정 (JS 재채색과 같은 색)
    colors = ["#cb181d", "#fb6a4a", "#fdae6b", "#fee08b", "#a6d96a", "#1a9850"]
    colormap = cm.LinearColormap(
        colors=colors, vmin=0, vmax=100, caption="HRI 점수 (현재 가중치, 높을수록 의료 복원 수준 ↑)",
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
            "hri_now", "rank_now", "wai", "iai", "dpi",
            "total_population", "aging_rate",
            "outflow_cost_ratio", "unmet_std_pct", "medical_aid_recipient_rate",
        ],
        aliases=[
            "시·도", "시·군·구", "유형",
            "HRI(현재 가중치)", "순위(/229)", "WAI(인력)", "IAI(인프라)", "DPI(수요)",
            "총인구", "고령화율(%)",
            "관외이용률", "미충족의료율(%)", "의료급여율(%)",
        ],
        localize=True, sticky=False, labels=True,
        style="background-color: #fff; border: 1px solid #888; border-radius: 4px; "
              "box-shadow: 2px 2px 4px rgba(0,0,0,0.15); padding: 6px;",
    )

    layer = folium.GeoJson(
        geo,
        name="HRI",
        style_function=style_function,
        highlight_function=highlight,
        tooltip=tooltip,
    )
    layer.add_to(m)
    colormap.add_to(m)

    root = m.get_root()
    root.header.add_child(folium.Element(PANEL_CSS))
    root.html.add_child(folium.Element(PANEL_HTML))
    root.script.add_child(folium.Element(
        PANEL_JS
        .replace("__LAYER__", layer.get_name())
        .replace("__REGIONS__", json.dumps(regions, ensure_ascii=False))
        .replace("__PRESETS__", json.dumps(presets, ensure_ascii=False))
        .replace("__COLORS__", json.dumps(colors))
    ))

    out = DOCS / "index.html"
    m.save(str(out))
    print(f"\nsaved → {out}")
    print(f"size: {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
