# HRI-korea — 시·군·구 의료 복원 지수

[![CI](https://github.com/vashazza/HRI-korea/actions/workflows/ci.yml/badge.svg)](https://github.com/vashazza/HRI-korea/actions/workflows/ci.yml)
[![Pages](https://github.com/vashazza/HRI-korea/actions/workflows/pages.yml/badge.svg)](https://github.com/vashazza/HRI-korea/actions/workflows/pages.yml)

[![HRI 지도](docs/map_preview.png)](https://vashazza.github.io/HRI-korea/)

**[라이브 지도 →](https://vashazza.github.io/HRI-korea/)** 시·군·구에 마우스를 올리면 하위 지수·군집·관외이용률이 나온다. 가중치 슬라이더(프리셋: 등가중 / LASSO 점추정 / 부트스트랩 CI 하한·상한)를 움직이면 브라우저에서 HRI와 순위를 다시 계산해 지도를 다시 칠하고, 지역을 클릭하면 LASSO 가중치 대비 순위 변화가 나온다.

> **Summary.** HRI-korea builds a *Healthcare Restoration Index* for all 229 South Korean municipalities (si·gun·gu) from public HIRA and KOSIS statistics. Three PCA sub-indices — workforce (WAI), infrastructure (IAI) and demand pressure (DPI) — are combined with LASSO-derived weights, grouped into six regional types with K-Means, and probed with what-if policy scenarios. The whole chain, from a hashed raw-data manifest to the interactive map, re-runs with one command. It is a resource-distribution index, not a predictive model: across 200 random train/test splits it explains a median 21% of held-out variance in out-of-region care use, and it correlates only −0.06 with self-reported unmet medical need. Replacing province-level workforce figures with municipality-level counts fixed a wrong-signed coefficient and showed that the infrastructure index adds nothing once workforce is measured properly (LASSO weight 0). The Limitations section says what that means.

| **229** | **3** | **0.21** | **−0.06** |
|:---:|:---:|:---:|:---:|
| 시·군·구 | 하위 지수 (WAI·IAI·DPI) | holdout R² 중앙값 (관외이용률, 80:20 분할 200회) | HRI–미충족의료율 상관 (Pearson) |

**예측 모델이 아니라 자원 분포 지수다.** 관외이용률은 가중치 추정과 내부 검증에 모두 쓰여 순환성이 있다.

## 방법

```mermaid
flowchart LR
    A["원자료<br/>HIRA · KOSIS · 행안부<br/>(MANIFEST + SHA256)"] --> B["전처리<br/>229 시·군·구 × 85 변수"]
    B --> W["WAI<br/>인력"]
    B --> I["IAI<br/>인프라"]
    B --> D["DPI<br/>수요 압력"]
    W & I & D -->|"각각 PCA 1주성분<br/>→ 0~100"| L["LASSO 가중치<br/>target: 관외이용률"]
    L --> H["HRI = w₁·WAI + w₂·IAI − w₃·DPI"]
    H --> K["K-Means 군집<br/>K=6"]
    H --> S["정책 시나리오<br/>baseline 좌표 고정 what-if"]
    K & S --> M["지도 · 리포트"]
```

1. **하위 지수** — 인구 10만 명당 인력(전문의·간호사·필수 5과), 인프라(의원~상급종합·보건소·수술실·CT·MRI), 수요(고령화·지방소멸·의료급여·1인당 진료비)를 각각 표준화한 뒤 PCA 첫 주성분으로 압축한다. 설명분산은 WAI 72.2%, IAI 33.3%, DPI 80.5%. 의사·전문의 수는 요양기관 단위 신고 자료를 소재지 시·군·구로 집계한 실측치다.
2. **가중치** — 세 지수로 관외 의료이용률(거주 시·군·구 밖에서 쓴 진료비 비중)을 LASSO 회귀하고, 계수 절댓값 비율을 가중치로 쓴다. 결과 w = (0.454, 0, 0.546) — LASSO가 IAI 계수를 0으로 만들었다(아래 "WAI 자료 교체").
3. **군집** — WAI·IAI·DPI 공간에서 K-Means. 실루엣과 Ward 계층군집 일치도(ARI)를 합친 기준으로 K=6 (실루엣 0.384, ARI 0.751). 실루엣만 보면 K=4가 가장 높고(0.446), 경계가 뚜렷한 군집은 아니다.
4. **시나리오** — 하위 30% 지역에 자원을 더했을 때 HRI 변화. baseline에서 학습한 PCA·정규화 좌표를 고정하고 입력만 바꾼다.

## 실행

```bash
pip install -r requirements.txt && pip install -e . --no-deps
```

**원자료 없이 돌려보기 (권장).** 원자료는 라이선스·용량 문제로 레포에 없다. 대신 전처리 결과인 `data/processed/master_dataset.csv`가 커밋되어 있어, 그 이후 단계는 누구나 재실행할 수 있다.

```bash
make reproduce   # = hri reproduce : indices → model → cluster → simulate → figures → map
make test
```

같은 환경에서는 커밋된 `data/processed/*.csv`·`reports/hri_weights.json`과 바이트 단위로 같은 결과가 나온다. 수치 라이브러리(BLAS) 빌드가 다르면 마지막 자리 부동소수점만 달라지므로, CI는 새 환경에서 재실행한 결과를 `scripts/check_reproduced.py`로 커밋본과 허용오차 1e-9로 비교한다. (`docs/index.html`은 Folium이 빌드마다 요소 ID를 새로 붙여서 그 부분만 달라진다.)

**원자료부터 전부.** 원자료 목록·출처·기준시점·SHA256은 [`data/raw/MANIFEST.yaml`](data/raw/MANIFEST.yaml)에 있다.

```bash
make check_data  # = hri check-data : 존재·해시 검사, 누락 파일은 받는 곳 안내
make full        # = hri run-all    : check-data → preprocess → reproduce
```

단계별로는 `hri <check-data|preprocess|indices|model|cluster|simulate|figures|map>`.

## 결과

**지역 유형 (K=6)** — HRI 평균 순

| 유형 | 시·군·구 | WAI | IAI | DPI | HRI | 예 |
|---|---:|---:|---:|---:|---:|---|
| 대형병원 밀집 도심형 | 7 | 64.3 | 83.8 | 35.9 | 73.5 | 서울 종로·강남·중구, 대구 중구·남구, 부산 서구, 광주 동구 |
| 대도시·신도시 저수요형 | 57 | 13.0 | 26.3 | 17.1 | 57.8 | 수원, 용인, 고양, 화성, 세종 |
| 도시 거점형 | 59 | 20.2 | 60.5 | 31.3 | 52.5 | 창원, 전주, 서울 송파·강서 |
| 중소도시 중간형 | 49 | 9.1 | 27.1 | 47.2 | 35.9 | 여수, 경주, 충주, 안동 |
| 고령지역 자원부족형 | 22 | 6.0 | 18.0 | 77.9 | 14.0 | 논산, 영천, 상주, 의성 |
| 고령지역 인프라보유형 | 35 | 8.5 | 40.1 | 81.4 | 13.0 | 정읍, 밀양, 김제, 고흥 |

WAI는 대형병원이 있는 몇 곳에 몰려 있다(중앙값 11.3, 종로구 100). 고령지역 두 유형은 HRI가 거의 같고 인프라(IAI)에서만 갈린다.

**시나리오 — 군집 평균 ΔHRI** (LASSO 가중치 기준)

| 시나리오 | 대상 | 고령·자원부족 | 고령·인프라보유 | 중소도시 | 대도시·신도시 | 도시 거점 | 대형병원 도심 |
|---|---:|---:|---:|---:|---:|---:|---:|
| S1 필수 5과 전문의 +10% (WAI 하위 30%) | 69곳 | +0.26 | +0.16 | +0.13 | +0.07 | 0 | 0 |
| S2 의원 +5개 (IAI 하위 30%) | 69곳 | 0 | 0 | 0 | 0 | 0 | 0 |
| S3 CT·MRI 각 +1대 (보유 하위 30%) | 40곳 | 0 | 0 | 0 | 0 | 0 | 0 |
| S4 보건의료원 없는 곳에 신설 | 213곳 | 0 | 0 | 0 | 0 | 0 | 0 |

S2~S4가 전부 0인 것은 계산 오류가 아니라 IAI 가중치가 0이기 때문이다. 이 지수는 인프라 투입을 평가하지 못한다. 지도의 슬라이더로 IAI에 가중치를 주면 값이 생기지만, 그 가중치는 자료가 지지하지 않는다.

## WAI 자료 교체 — 진단, 교체, 그리고 드러난 것

처음에는 HIRA 인력 통계가 시·도 단위라 시·군·구 인구 비례로 나눠 썼다. 그러면 같은 시·도 안에서는 인구당 값이 똑같아져 WAI가 17개 값밖에 갖지 못했고, 회귀에서 WAI 계수가 "인력이 많을수록 관외이용이 많다"는 반대 방향으로 나왔다. 원인을 자료 해상도로 진단하고, 요양기관 단위 신고 자료(78,482곳, 2024년 12월)를 받아 의사·전문의 수를 소재지 시·군·구로 직접 집계해 교체했다.

| | 시·도 값 분배 (이전) | 시·군·구 실측 (현재) |
|---|---:|---:|
| WAI가 갖는 서로 다른 값 | 17 | 229 |
| WAI 계수 (관외이용률에 대해) | +0.0020 | **−0.0017** |
| LASSO 가중치 (WAI, IAI, DPI) | 0.241, 0.431, 0.328 | 0.454, 0, 0.546 |
| holdout R² 중앙값 (분할 200회) | 0.24 | 0.21 |
| holdout R², 분할 1회 (seed 42) | 0.145 | −0.36 |
| HRI–미충족의료율 상관 | −0.13 | −0.06 |

- **부호는 바로잡혔다.** 진단이 맞았다.
- **IAI 가중치가 0이 됐다.** WAI가 제대로 측정되자 IAI와 상관이 0.66이고, IAI가 따로 설명하는 몫이 없다. 이전에 IAI 가중치가 가장 컸던 것은 평탄화된 WAI 대신 "병원이 몰린 정도"를 대리했기 때문으로 보인다. 다만 IAI에서 적재값이 큰 MRI·수술실·CT는 아직 시·도 값 분배다. 인프라가 정말 인력과 중복인지, IAI가 덜 정확하게 측정돼서 밀려난 것인지는 지금 자료로 구분하지 못한다.
- **설명력은 좋아지지 않았다.** 더 정확한 측정이 더 나은 예측으로 이어지지는 않았다. 외부 지표(미충족의료율)와의 상관도 약해졌다.
- **분할 한 번짜리 holdout은 믿을 수 없다.** seed 42 분할에서는 종로구가 검증셋에 들어가 그 한 곳이 오차 제곱합의 27%를 차지한다. 그래서 분할을 200번 바꾼 분포를 보고한다(중앙값 0.21, 사분위 0.13~0.27, 7.5%는 음수). 이전에 헤드라인으로 쓴 0.13도 이 한 번의 분할에서 나온 값이었고, 당시 분포의 중앙값은 0.24였다.

함께 고친 버그: 간호사 로더가 합계 행 이름을 잘못 걸러 간호사 관련 22개 열이 전부 0이었다. 위 표의 "이전" 열은 이 수정을 반영한 값이다. 간호사·장비·특수진료실은 시·군·구 자료를 찾지 못해 여전히 시·도 값 분배다.

자세한 경과(시행착오 포함)는 [`reports/comprehensive_report.md`](reports/comprehensive_report.md), 검증 수치는 [`reports/hri_validation.md`](reports/hri_validation.md).

## Limitations

1. **IAI가 지수에 기여하지 않는다.** LASSO 가중치가 0이라 HRI는 사실상 0.45·WAI − 0.55·DPI다. IAI는 PC1 설명분산이 33%로 한 축에 잘 묶이지도 않고, 보건소·보건의료원 적재값은 음수다(병원 적은 농촌에 주로 있어서). 인프라 시나리오(S2~S4)는 이 지수로 평가할 수 없다.
2. **가중치가 불안정하다.** 부트스트랩 95% 구간이 w₁ 0.00~0.73, w₂ 0~0.18, w₃ 0.18~0.90이다. 순위는 가중치에 따라 달라지며, 지도의 슬라이더로 직접 볼 수 있다.
3. **WAI가 극단값에 끌린다.** 인구당 전문의 수는 대형병원 소재지에 몰려 있어(왜도 3.45) 0~100 눈금의 대부분을 몇 곳이 차지한다. 로그 변환 같은 처리는 하지 않았다.
4. **간호사·장비·특수진료실은 여전히 시·도 값이다.** 시·군·구 인구 비례로 나눴으므로 같은 시·도 안에서는 인구당 값이 같다. IAI의 주된 입력이 이 변수들이어서 1번(IAI 가중치 0)의 해석도 이 한계에 걸려 있다. 장비는 같은 요양기관 단위 자료에 기관별 보유 대수가 있어 같은 방식으로 교체할 수 있지만 하지 않았다.
5. **연도가 맞지 않는다.** 의사·전문의는 2024년 12월, 나머지 HIRA 공급측 자료는 2026년 1분기, 수요·결과측(인구·미충족의료·관외이용·의료급여)은 2024년 기준이다 ([MANIFEST](data/raw/MANIFEST.yaml) `reference_period`).
6. **검증에 순환성이 있다.** 관외이용률로 가중치를 추정하고 같은 변수로 내부 검증을 했다. 이 변수와 독립인 외부 지표는 미충족의료율 하나이고 상관은 −0.06이다.
7. **치료가능사망률로 외부 검증하지 못했다.** 사망원인통계가 시·도 단위만 공개돼 시·군·구 비교가 불가능했다.
8. **미충족의료율은 잡음이 크다.** 지역사회건강조사 응답자가 시·군·구당 중앙값 848명이다. 이 변수를 종속변수로 쓰면 R²가 0.02였다.
9. **의사 수는 소재지 기준이다.** 종로구의 전문의는 종로구 주민만 보지 않는다. 공간 자기상관이나 이웃 지역 이용을 모형이 모른다.
10. **시나리오는 인과 추정이 아니다.** 지수 정의 안에서 입력을 바꿨을 때의 상관 기반 what-if다.
11. **2024년 횡단면 하나다.** 시간에 따른 변화나 정책 전후 비교는 없다.

**의도적으로 다루지 않은 것** — 공간시차·공간오차 모형과 GWR, DiD 기반 시나리오 보정, 가중치 방법 비교(PCA·AHP)와 Monte Carlo 순위 강건성 검토, 학술지 투고.

## 구조

```
data/
  raw/MANIFEST.yaml  # 원자료 23개의 출처·기준시점·SHA256 (원자료 자체는 gitignore)
  processed/         # master_dataset.csv 이하 모든 산출 CSV (커밋됨)
src/hri/
  paths.py           # 경로 중앙화 (MANIFEST와 1:1)
  check_data.py      # 원자료 검사
  loader.py          # 원자료 로드, 시·도/시·군·구 표기 정규화
  preprocess.py      # master_dataset 빌드
  indices.py         # WAI/IAI/DPI PCA (fit/transform 분리)
  hri.py             # LASSO 가중치, HRI, 검증
  clustering.py      # K-Means + Ward 교차 검증
  simulation.py      # baseline 좌표 고정 시나리오
  cli.py             # hri 명령
scripts/             # 정적 그림, 지도 빌드, 진단 스크립트
reports/             # 검증·군집·시나리오 리포트, figures/
docs/                # GitHub Pages (index.html)
tests/
```

지도는 2013년 기준 시·군·구 경계(southkorea-maps)를 쓰고, 이후 행정구역 변동(군위군 → 대구, 청원군 → 청주, 인천 남구 → 미추홀구)은 매핑으로 맞췄다. `make map`이 GeoJSON이 없으면 내려받는다.
