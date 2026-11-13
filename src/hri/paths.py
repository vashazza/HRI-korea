"""Project path constants — single source of truth for data file locations."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"

HIRA = RAW / "hira"
KOSIS = RAW / "KOSIS"
NEW = RAW / "new"

REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

# --- HIRA files (지역별 시·군·구 단위) ---
HIRA_FACILITIES = HIRA / "01_facilities_by_region.xlsx"
HIRA_SPECIALISTS = HIRA / "02_specialists_by_region.xlsx"   # 시·도 단위 (HIRA_INSTITUTIONS로 대체됨)
HIRA_DOCTORS = HIRA / "03_doctors_by_regions.xlsx"          # 시·도 단위 (HIRA_INSTITUTIONS로 대체됨)
HIRA_NURSES = HIRA / "03_nurses_by_region.xlsx"
HIRA_CLAIMS = HIRA / "04_claims_by_disease_region.csv"
HIRA_RESOURCES = HIRA / "05_resources_per_population.csv"
HIRA_SPECIAL_ROOMS = HIRA / "06_special_treatment_rooms.xlsx"   # 시·도 단위 (HIRA_INSTITUTIONS로 대체됨)
HIRA_EQUIPMENT = HIRA / "07_medical_equipment.xlsx"            # 시·도 단위 (HIRA_INSTITUTIONS로 대체됨)

# --- HIRA 요양기관 단위 자료 (시·군·구 집계용, 2024.12) — xlsx 12개 묶음 zip ---
HIRA_INSTITUTIONS = RAW / "hira_sgg" / "전국 병의원 및 약국 현황 2024.12.zip"

# --- KOSIS — 기존 ---
KOSIS_DEATH = KOSIS / "사망원인 50항목 1998.csv"          # 2024년 데이터

# --- new/ (보완 데이터, 2024년 기준) ---
POPULATION_OLD = NEW / "2023 주민등록 인구.csv"           # 시·도 단위만 (대체됨)
POPULATION = NEW / "101_DT_1B04005N_20260519220446.xls"   # 시·군·구 단위 5세별 인구 (KOSIS SpreadsheetML)
WELFARE = NEW / "복지사업 수급권자 현황 2024.csv"
UNMET_CARE = NEW / "시군구 연간 미충족 의료율.csv"        # 2024
PUBLIC_HOSPITAL_STAFF = NEW / "시도별 공공의료기관 인력 현황 2026.csv"  # 시도 단위만

# 관내 (residence-based, 거주지 내 진료)
INPATIENT_FILES = {
    "서울·인천·경기·강원": NEW / "서울 인천 경기 강원 진료현황 전체 2026-05-19.csv",
    "대전·세종·충북·충남": NEW / "시군구_대전_세종_충북_충남_별_관내_진료현황전체_20260519173640.csv",
    "부산·대구·울산·경북·경남": NEW / "시군구_부산_대구_울산_경북_경남_별_관내_진료현황전체_20260519173733.csv",
    "광주·전북·전남·제주": NEW / "시군구_광주_전북_전남_제주_별_관내_진료현황전체_20260519173708.csv",
}

# 관외 (out-of-region, 거주지 밖 진료)
OUTPATIENT_FILES = {
    "서울·인천·경기·강원": NEW / "시군구_서울_인천_경기_강원_별_관외_진료현황전체_20260519173624.csv",
    "대전·세종·충북·충남": NEW / "대전 세종 충북 충남 관외 진료현황 전체 2026-05-19.csv",
    "부산·대구·울산·경북·경남": NEW / "부산 대구 울산 경북 경남 관외 진료현황 전체 2026.csv",
    "광주·전북·전남·제주": NEW / "관외 진료현황 전체 2026-05-19.csv",
}

# --- 기준 연도 ---
BASE_YEAR = 2024
