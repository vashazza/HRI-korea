# 지역 의료 복원 지수 (HRI)

전국 시·군·구의 의료 복원 지수(Healthcare Restoration Index)를 산출하고, 정책 시나리오의 효과를 시뮬레이션한다.

[인터랙티브 지도](docs/index.html) — GitHub Pages 배포 후 시·군·구별 HRI 및 하위 지수 조회.

## 분석 단위

- 공간: 시·군·구 229개 (법정동 5자리)
- 시간: 2024년 횡단면

## 지수

WAI·IAI·DPI 세 하위 지수를 LASSO 회귀로 가중합한다.

- WAI: 의료 인력 적정성
- IAI: 의료 인프라 적정성
- DPI: 의료 수요 압력
- HRI = w₁·WAI + w₂·IAI − w₃·DPI

종속변수는 관외 의료이용률(`healthcare_outflow_ratio`, KOSIS 2024). 미충족의료율은 R²=0.015로 fit이 약해 robustness check에서만 사용한다. 외부 검증에 치료가능사망률 사용.

## 디렉토리

```
data/
  raw/        # 원본 (gitignore)
  interim/    # 정제 중간 (gitignore)
  processed/  # 최종 데이터셋
  geo/        # GeoJSON (gitignore)
notebooks/    # 분석 노트북
src/hri/      # 모듈
reports/      # 보고서 + figures
tests/
```


## 실행

```bash
pip install -r requirements.txt && pip install -e . --no-deps
```

**원자료 없이 돌려보기 (권장)** — 원자료는 라이선스·용량 문제로 레포에 없다. 대신 전처리 결과인 `data/processed/master_dataset.csv`가 커밋되어 있어, 그 이후 단계는 누구나 그대로 재실행할 수 있다.

```bash
make reproduce   # indices → hri → clustering → simulation → figures → map
```

커밋된 `data/processed/*.csv`·`reports/hri_weights.json`과 바이트 단위로 같은 결과가 다시 나온다. (`docs/index.html`은 Folium이 빌드마다 요소 ID를 새로 붙여서 그 부분만 달라진다.)

**원자료부터 전부** — 원자료 목록·출처·SHA256은 [`data/raw/MANIFEST.yaml`](data/raw/MANIFEST.yaml)에 있다.

```bash
make check_data  # 원자료 존재·해시 검사, 누락 파일은 받는 곳 안내
make full        # check_data → preprocess → reproduce
```

## 산출물

`data/processed/`

- `master_dataset.csv` — 229 × 101
- `master_with_indices.csv` — + WAI/IAI/DPI
- `hri_results.csv` — + HRI
- `hri_with_clusters.csv` — + 클러스터 라벨
- `cluster_profiles.csv` — 클러스터별 평균
- `scenario_simulations.csv` — 4개 시나리오 × 229
- `scenario_cluster_matrix.csv` — 클러스터 × 시나리오

`reports/`

- `inventory_raw_output.txt` — 데이터 인벤토리
- `master_summary.txt` — 마스터 요약 및 face validity
- `indices_summary.txt` — PCA 설명분산
- `hri_validation.md` — LASSO 가중치 및 검증
- `hri_weights.json` — 가중치 + 부트스트랩 CI
- `clustering.txt` — K 진단 + 프로파일
- `cluster_profiles.md` — 클러스터 해석
- `scenario_report.md` — 시나리오 결과 및 정책 함의

## 모듈

`src/hri/`

- `paths.py` — 경로 중앙화
- `loader.py` — 원본 로드, 시·도/시·군·구 정규화
- `preprocess.py` — master_dataset 빌드
- `indices.py` — WAI/IAI/DPI PCA (fit/transform 분리)
- `hri.py` — LASSO + HRI 산출 및 검증
- `clustering.py` — K-Means + Ward 교차 검증
- `simulation.py` — baseline 고정 시나리오

## 지도 빌드

```bash
mkdir -p data/geo
curl -L -o data/geo/skorea_sgg.geojson \
  https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_municipalities_geo_simple.json

python notebooks/06_build_map.py
```

2013 GeoJSON 기준 행정구역 변동(군위군 → 대구, 청원군 → 청주, 인천 남구 → 미추홀구)은 매핑에 반영했다.

## 분석 결정

- 종속변수는 관외 의료이용률 채택. 미충족의료율은 fit이 약해 robustness check 용도로만 사용
- 시·도 단위 HIRA 데이터는 시·군·구 인구비례로 분배 → 시·군·구 변별력이 시·도 평균에 의존하는 한계
- 최적 K=3 (Silhouette 0.474, Ward ARI 0.651)
- 시뮬레이션은 baseline PCA와 HRI min-max 좌표계를 고정해 transform-only 적용
