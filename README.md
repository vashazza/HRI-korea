# 지역 의료 복원 지수 (HRI) 프로젝트

전국 시·군·구 단위 의료 복원 지수(Healthcare Restoration Index)를 산출하고, 정책 시뮬레이션으로 개입 효과를 사전 예측한다.

**🗺️ 인터랙티브 지도:** [docs/index.html](docs/index.html) — GitHub Pages 배포 시 `https://<user>.github.io/<repo>/`에서 시·군·구 호버로 HRI/WAI/IAI/DPI·인구·고령화·관외이용률 조회 가능.

## 분석 단위
- 공간: 전국 약 229개 시·군·구 (법정동 5자리)
- 시간: **2024년** 기준 (단일 횡단면)

## 핵심 지수
- **WAI** Workforce Adequacy Index — 의료 인력 적정성
- **IAI** Infrastructure Adequacy Index — 의료 인프라 적정성
- **DPI** Demand Pressure Index — 의료 수요 압력
- **HRI** = w₁·WAI + w₂·IAI − w₃·DPI (LASSO 회귀로 가중치 추정)

## 종속변수
- Main: `unmet_care_rate` (미충족 의료 경험률, 지역사회건강조사 2024)
- Robustness: `healthcare_outflow_ratio` (관외 의료이용률, KOSIS 거주지 기준 2024)
- External validation: `amenable_mortality_rate` (치료가능사망률, 사망원인통계)

## 디렉토리

```
.
├── data/
│   ├── raw/        # 원본 (gitignore) — hira/, KOSIS/, new/
│   ├── interim/    # 정제 중간 산출 (gitignore)
│   ├── processed/  # 최종 데이터셋
│   └── geo/        # GeoJSON (gitignore)
├── notebooks/      # 분석 노트북
├── src/hri/        # 재사용 가능한 모듈
├── reports/        # 보고서 + figures
└── tests/
```

## 셋업 (conda)

```bash
conda create -n hri -c conda-forge python=3.11 pandas=2.2 numpy scikit-learn scipy \
    statsmodels matplotlib seaborn openpyxl tqdm jupyter ipykernel lxml beautifulsoup4 -y
conda activate hri
pip install -e .
```

## 산출물 (data/processed/)

| 파일 | 설명 |
|---|---|
| `master_dataset.csv` | 229 × 101 — 시·군·구 단위 통합 데이터 (2024) |
| `master_with_indices.csv` | + WAI/IAI/DPI 컬럼 |
| `hri_results.csv` | + HRI 점수 |
| `hri_with_clusters.csv` | + 클러스터 라벨 |
| `cluster_profiles.csv` | 클러스터별 평균 프로파일 |
| `scenario_simulations.csv` | 4개 시나리오 × 229 시·군·구 ΔHRI |
| `scenario_cluster_matrix.csv` | 클러스터 × 시나리오 ΔHRI 매트릭스 |

## 보고서 (reports/)

| 파일 | 설명 |
|---|---|
| `inventory_raw_output.txt` | Phase 1 데이터 인벤토리 |
| `master_summary.txt` | Phase 2 마스터 요약 + face validity |
| `indices_summary.txt` | Phase 3 PCA 결과 + 설명분산 |
| `hri_validation.md` | Phase 4 HRI 가중치 + 3단계 검증 |
| `hri_weights.json` | LASSO 가중치 + 부트스트랩 CI |
| `clustering.txt` | Phase 5 K 진단 + 클러스터 프로파일 |
| `cluster_profiles.md` | 클러스터 유형 해석 |
| `scenario_report.md` | Phase 6 시나리오 결과 + 정책 함의 |
| `figures/` | 5개 시각화 PNG |

## 모듈 (src/hri/)

- `paths.py` — 데이터 파일 경로 중앙화
- `loader.py` — 원본 데이터 로드 + 시도/시·군·구 정규화
- `preprocess.py` — 229 시·군·구 × 101 컬럼 master_dataset 빌더
- `indices.py` — WAI/IAI/DPI PCA (fit/transform 분리)
- `hri.py` — LASSO 가중치 + HRI 산출 + 검증
- `clustering.py` — K-Means + Ward 교차 검증
- `simulation.py` — baseline-고정 시나리오 시뮬레이션

## 실행 방법

```bash
# 순차 실행 (원본 데이터가 data/raw/에 배치된 상태에서)
python -m hri.preprocess        # master_dataset.csv
python -m hri.indices           # WAI/IAI/DPI
python -m hri.hri               # HRI + 검증
python -m hri.clustering        # 클러스터
python -m hri.simulation        # 시나리오 ΔHRI
python notebooks/05_visualize.py  # 정적 시각화 (PNG)
python notebooks/06_build_map.py  # 인터랙티브 지도 (docs/index.html)
```

## 인터랙티브 지도 빌드 (Folium)

```bash
# 한국 시·군·구 GeoJSON 다운로드 (1회)
mkdir -p data/geo
curl -L -o data/geo/skorea_sgg.geojson \
  https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_municipalities_geo_simple.json

# 지도 생성
python notebooks/06_build_map.py
```

`docs/index.html` 한 파일에 GeoJSON + 데이터 + Leaflet/Folium JS가 모두 내장되므로 GitHub Pages에 별도 설정 없이 배포 가능. GitHub 레포의 Settings → Pages → Branch: `main`, Folder: `/docs` 로 설정.

지도 구성:
- **Choropleth**: HRI 점수 (RdYlGn 컬러맵, 낮을수록 의료 취약)
- **Tooltip**: 시도·시군구·클러스터 유형 · HRI/WAI/IAI/DPI · 총인구·고령화율·관외이용률·미충족의료율·의료급여율
- **행정구역 패치**: 2013 GeoJSON 기준에 군위군(→대구), 청원군(→청주), 인천 남구(→미추홀구) 매핑 반영

## 분석 의사결정 기록

- **종속변수**: 옵션 A (관외 의료이용률) 채택. 옵션 B (미충족의료율)는 R²=0.015로 fit 약함 → robustness check로만 활용
- **시·도 단위 HIRA 데이터**: 시·군·구 인구비례 분배. 시·군·구 변별력이 시·도 평균에 종속되는 한계 명시
- **최적 K**: 3 (Silhouette 0.474로 최댓값, Ward ARI 0.651)
- **시뮬레이션 좌표계**: baseline PCA + HRI min-max를 고정해 transform-only 적용
