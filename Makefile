# HRI 파이프라인
#   make reproduce  원자료 없이, 커밋된 data/processed/master_dataset.csv 에서 끝까지 재실행
#   make full       원자료(data/raw)가 있을 때: 검사 → 전처리 → reproduce
#   make test       pytest
#   make map        인터랙티브 지도(docs/index.html)만 다시 생성
#
# 다른 인터프리터를 쓰려면: make reproduce PYTHON=/path/to/python

PYTHON ?= python
export PYTHONPATH := src

GEOJSON := data/geo/skorea_sgg.geojson
GEOJSON_URL := https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_municipalities_geo_simple.json

.PHONY: reproduce full check_data preprocess indices hri clustering simulation figures map test

reproduce: indices hri clustering simulation figures map

full: check_data preprocess reproduce

check_data:
	$(PYTHON) -m hri.check_data

preprocess:
	$(PYTHON) -m hri.preprocess

indices:
	$(PYTHON) -m hri.indices

hri:
	$(PYTHON) -m hri.hri

clustering:
	$(PYTHON) -m hri.clustering

simulation:
	$(PYTHON) -m hri.simulation

figures:
	$(PYTHON) notebooks/05_visualize.py

map: $(GEOJSON)
	$(PYTHON) notebooks/06_build_map.py

$(GEOJSON):
	mkdir -p $(dir $@)
	curl -fsSL -o $@ $(GEOJSON_URL)

test:
	$(PYTHON) -m pytest -q
