# HRI 파이프라인 — 단계 정의는 src/hri/cli.py 한 곳에 있다.
#   make reproduce   원자료 없이, 커밋된 data/processed/master_dataset.csv 에서 끝까지 재실행
#   make full        원자료(data/raw)가 있을 때: 검사 → 전처리 → reproduce
#   make check_data  원자료 존재·해시 검사
#   make map         인터랙티브 지도(docs/index.html)만 다시 생성
#   make test        pytest
#
# 다른 인터프리터를 쓰려면: make reproduce PYTHON=/path/to/python

PYTHON ?= python
HRI := PYTHONPATH=src $(PYTHON) -m hri.cli

.PHONY: reproduce full check_data map test

reproduce:
	$(HRI) reproduce

full:
	$(HRI) run-all

check_data:
	$(HRI) check-data

map:
	$(HRI) map

test:
	PYTHONPATH=src $(PYTHON) -m pytest -q
