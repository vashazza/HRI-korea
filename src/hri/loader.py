"""원본 데이터 로더 + 시도명 정규화 + 진료현황 통합."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import paths

# 시도명을 표준 풀네임으로 통일. 표기는 입력원마다 제각각.
SIDO_FULL = {
    "서울": "서울특별시", "서울시": "서울특별시", "서울특별시": "서울특별시",
    "부산": "부산광역시", "부산시": "부산광역시", "부산광역시": "부산광역시",
    "대구": "대구광역시", "대구광역시": "대구광역시",
    "인천": "인천광역시", "인천광역시": "인천광역시",
    "광주": "광주광역시", "광주광역시": "광주광역시",
    "대전": "대전광역시", "대전광역시": "대전광역시",
    "울산": "울산광역시", "울산광역시": "울산광역시",
    "세종": "세종특별자치시", "세종시": "세종특별자치시", "세종특별자치시": "세종특별자치시",
    "경기": "경기도", "경기도": "경기도",
    "강원": "강원특별자치도", "강원도": "강원특별자치도", "강원특별자치도": "강원특별자치도",
    "충북": "충청북도", "충청북도": "충청북도",
    "충남": "충청남도", "충청남도": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도", "전북특별자치도": "전북특별자치도",
    "전남": "전라남도", "전라남도": "전라남도",
    "경북": "경상북도", "경상북도": "경상북도",
    "경남": "경상남도", "경상남도": "경상남도",
    "제주": "제주특별자치도", "제주도": "제주특별자치도", "제주특별자치도": "제주특별자치도",
}


def normalize_sido(s: pd.Series) -> pd.Series:
    """시도 표기를 표준 풀네임으로 통일. 매핑 실패 시 원본 유지."""
    return s.map(lambda v: SIDO_FULL.get(str(v).strip(), str(v).strip()))


# 시도 풀네임 → 데이터에 prefix로 붙는 짧은 형태
_SIDO_PREFIX_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전",
    "울산광역시": "울산",
}

# 특례시·일반구 분화 도시 — pop은 시 단위, 다른 데이터는 구 단위로 옴
# → 구 단위 값을 sum해서 시 단위로 통합
_SPECIAL_CITY_PREFIXES = (
    "수원", "고양", "성남", "부천", "안산", "안양", "용인",
    "창원", "포항", "전주", "천안", "청주", "화성",
)


def _normalize_one_sgg(sido: str, sgg: str) -> str:
    """sgg 표기를 pop 마스터(229)에 맞도록 정규화.
    - 세종은 단일 단위
    - 광역시 일반구: 'sido short' prefix 제거
    - 특례시 일반구: 시 단위로 집계 키 통일
    """
    if sido == "세종특별자치시":
        return "세종특별자치시"

    sgg = str(sgg).strip()
    # 광역시 prefix 제거 (대구중구→중구, 광주북구→북구). 예외: 부산진구는 자체가 행정구.
    short = _SIDO_PREFIX_SHORT.get(sido)
    if short and sgg.startswith(short) and sgg != short and not (sido == "부산광역시" and sgg == "부산진구"):
        sgg = sgg[len(short):]

    # 특례시 구 통합 (수원권선구·수원시권선구·수원시 권선구 → 수원시)
    s_compact = sgg.replace(" ", "")
    for pref in _SPECIAL_CITY_PREFIXES:
        if s_compact.startswith(pref) and s_compact != pref + "시":
            # "수원시권선구" / "수원권선구" 모두 → "수원시"
            tail = s_compact[len(pref):]
            if tail.startswith("시") and len(tail) > 1:
                return pref + "시"
            if not tail.startswith("시") and tail:
                return pref + "시"
    return sgg


def normalize_sgg(df: pd.DataFrame, *, agg_numeric: bool = True) -> pd.DataFrame:
    """sgg를 pop 마스터 키에 맞춰 정규화. 정규화 결과 같은 (sido, sgg)는 합산."""
    if "sgg" not in df.columns or "sido" not in df.columns:
        return df
    out = df.copy()
    out["sgg"] = [_normalize_one_sgg(s, g) for s, g in zip(out["sido"], out["sgg"])]
    if agg_numeric:
        num_cols = out.select_dtypes("number").columns.tolist()
        if num_cols:
            out = out.groupby(["sido", "sgg"], as_index=False)[num_cols].sum(min_count=1)
        else:
            out = out.drop_duplicates(subset=["sido", "sgg"])
    return out.reset_index(drop=True)


SIDO_FULL_NAMES = set(SIDO_FULL.values())


def _parse_kosis_spreadsheetml(path: Path) -> pd.DataFrame:
    """KOSIS의 .xls는 사실 SpreadsheetML XML. lxml로 직접 파싱한다."""
    from lxml import etree

    with open(path, "rb") as f:
        raw = f.read()
    xml = raw[raw.find(b"<?xml") :]
    root = etree.fromstring(xml, etree.XMLParser(huge_tree=True, recover=True))
    ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

    rows_data = []
    rows_xml = root.findall(".//ss:Worksheet[1]/ss:Table/ss:Row", ns)
    header = None
    for r in rows_xml:
        cells = r.findall("ss:Cell", ns)
        if not cells:
            continue
        vals = []
        for c in cells:
            d = c.find("ss:Data", ns)
            vals.append(d.text if d is not None else None)
        if header is None and any(v == "행정구역(동읍면)별" for v in vals):
            header = vals
            continue
        if header is None:
            continue
        rows_data.append(vals + [None] * (len(header) - len(vals)))

    df = pd.DataFrame(rows_data, columns=header)
    return df


def load_population(year: int = paths.BASE_YEAR) -> pd.DataFrame:
    """주민등록 인구 (KOSIS SpreadsheetML).

    반환: [sido, sgg, age_group, total, male, female]
    sgg='소계' 행은 시·도 합계. 외 행은 시·군·구.
    """
    df = _parse_kosis_spreadsheetml(paths.POPULATION)
    year_col_candidates = [c for c in df.columns if str(year) in str(c)]
    if not year_col_candidates:
        raise ValueError(f"year {year} not found. cols={df.columns.tolist()}")
    year_col = year_col_candidates[0]

    df = df.rename(columns={"행정구역(동읍면)별": "region", "5세별": "age_group", "항목": "item"})
    df[year_col] = pd.to_numeric(df[year_col], errors="coerce")
    df = df[df["region"].notna()].copy()

    # 시·도와 시·군·구가 같은 컬럼에 섞임 → 순서로 계층 추론.
    current_sido = None
    sidos, sggs = [], []
    for v in df["region"]:
        if v in SIDO_FULL_NAMES:
            current_sido = v
            sidos.append(v)
            sggs.append("소계")
        elif v == "세종특별자치시":
            current_sido = v
            sidos.append(v)
            sggs.append("세종특별자치시")
        else:
            sidos.append(current_sido)
            sggs.append(v)
    df["sido"] = sidos
    df["sgg"] = sggs

    # wide-ify: item을 컬럼으로
    df = df.pivot_table(
        index=["sido", "sgg", "age_group"], columns="item", values=year_col, aggfunc="first"
    ).reset_index()
    df.columns.name = None
    df = df.rename(columns={"총인구수[명]": "total", "남자인구수[명]": "male", "여자인구수[명]": "female"})
    df = df[df["age_group"] != "5세별"]
    df = df[df["sido"] != "전국"].dropna(subset=["sido"]).reset_index(drop=True)
    return df


def population_totals(year: int = paths.BASE_YEAR) -> pd.DataFrame:
    """시·군·구 단위 핵심 인구 지표.

    반환: [sido, sgg, total_population, pop_0_19, pop_20_64, pop_65_plus,
            pop_20_39_female, aging_rate, extinction_index]
    """
    df = load_population(year)
    # 세종특별자치시는 단일 단위라 시·도='세종', sgg='소계'로만 옴 → sgg를 시·도명으로 치환해 데이터로 살림.
    sejong_mask = (df["sido"] == "세종특별자치시") & (df["sgg"] == "소계")
    df.loc[sejong_mask, "sgg"] = "세종특별자치시"
    df = df[df["sgg"] != "소계"].copy()

    # 연령 그룹 정의
    YOUNG = ["0 - 4세", "5 - 9세", "10 - 14세", "15 - 19세"]
    MID = [f"{a} - {a+4}세" for a in range(20, 60, 5)] + ["60 - 64세"]
    OLD = ["65 - 69세", "70 - 74세", "75 - 79세", "80 - 84세", "85 - 89세", "90 - 94세", "95 - 99세", "100+"]
    F2039 = ["20 - 24세", "25 - 29세", "30 - 34세", "35 - 39세"]

    def sum_total(ages):
        return df[df["age_group"].isin(ages)].groupby(["sido", "sgg"])["total"].sum()

    def sum_female(ages):
        return df[df["age_group"].isin(ages)].groupby(["sido", "sgg"])["female"].sum()

    total = df[df["age_group"] == "계"].groupby(["sido", "sgg"])["total"].sum().rename("total_population")
    p0_19 = sum_total(YOUNG).rename("pop_0_19")
    p20_64 = sum_total(MID).rename("pop_20_64")
    p65 = sum_total(OLD).rename("pop_65_plus")
    pf2039 = sum_female(F2039).rename("pop_20_39_female")

    out = pd.concat([total, p0_19, p20_64, p65, pf2039], axis=1).reset_index()
    # 출장소·면 단위 등 인구 0 또는 매우 작은 잡데이터 제거 (행정구역 분석 대상 아님)
    out = out[out["total_population"] > 1000].copy()
    out["aging_rate"] = out["pop_65_plus"] / out["total_population"] * 100
    out["extinction_index"] = out["pop_20_39_female"] / out["pop_65_plus"].replace(0, pd.NA)
    return out.reset_index(drop=True)


def load_unmet_care() -> pd.DataFrame:
    """미충족 의료율 (2024). 종속변수 메인."""
    df = pd.read_csv(paths.UNMET_CARE, encoding="cp949", header=[0, 1])
    df.columns = ["sido", "sgg2", "sgg3", "n", "crude", "crude_se", "std", "std_se"]
    df["sido"] = normalize_sido(df["sido"])
    df = df[(df["sgg3"] == "소계") & (df["sgg2"] != "소계")].copy()
    df["sgg"] = df["sgg2"]
    # 세종시는 단일 단위라 sgg가 "세종시"로 옴 → 마스터 키 "세종특별자치시"로 통일
    df.loc[df["sgg"] == "세종시", "sgg"] = "세종특별자치시"
    out = df[["sido", "sgg", "n", "crude", "std"]].reset_index(drop=True)
    # 미충족의료율은 응답률이라 sum이 의미 없음. 정규화만 적용하고 가중평균은 별도 처리.
    out["sgg"] = [_normalize_one_sgg(s, g) for s, g in zip(out["sido"], out["sgg"])]
    # 정규화 후 같은 (sido,sgg)가 여럿이면 응답자수 가중 평균
    grouped = out.groupby(["sido", "sgg"], as_index=False).apply(
        lambda g: pd.Series({
            "n": g["n"].sum(),
            "crude": (g["crude"] * g["n"]).sum() / g["n"].sum() if g["n"].sum() else float("nan"),
            "std": (g["std"] * g["n"]).sum() / g["n"].sum() if g["n"].sum() else float("nan"),
        })
    ).reset_index(drop=True)
    return grouped


def load_welfare_medical_aid() -> pd.DataFrame:
    """복지사업 수급권자 중 기초의료급여만. 시·군·구 단위로 정규화."""
    df = pd.read_csv(paths.WELFARE, encoding="cp949")
    df = df[df["사업명"] == "기초의료급여"].copy()
    df["sido"] = normalize_sido(df["시도"])
    df = df.rename(columns={"시군구": "sgg", "수급권자수": "medical_aid_recipients", "수급가구수": "medical_aid_households"})
    out = df[["sido", "sgg", "medical_aid_recipients", "medical_aid_households"]].reset_index(drop=True)
    return normalize_sgg(out)


def _load_treatment_part(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949", header=[0, 1])
    df.columns = ["sido", "sgg", "patients", "visit_days", "benefit_days", "cost_krw_k", "benefit_krw_k"]
    df["sido"] = normalize_sido(df["sido"])
    # 세종은 단일 단위라 sgg='소계'만 옴 → 마스터 키로 치환해서 살림
    sejong_mask = (df["sido"] == "세종특별자치시") & (df["sgg"] == "소계")
    df.loc[sejong_mask, "sgg"] = "세종특별자치시"
    df = df[df["sgg"] != "소계"].copy()
    return df


def load_treatment(kind: str) -> pd.DataFrame:
    """진료현황 4개 권역을 합쳐서 반환. kind ∈ {'in', 'out'}.
    특례시 구는 시 단위로 합산.
    """
    sources = paths.INPATIENT_FILES if kind == "in" else paths.OUTPATIENT_FILES
    parts = [_load_treatment_part(p) for p in sources.values()]
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates(subset=["sido", "sgg"]).reset_index(drop=True)
    return normalize_sgg(df)


def load_outflow_ratio() -> pd.DataFrame:
    """관외이용률 = 관외 진료비 / (관내 + 관외 진료비). robustness check용."""
    inn = load_treatment("in").rename(columns={"patients": "p_in", "cost_krw_k": "c_in"})
    out = load_treatment("out").rename(columns={"patients": "p_out", "cost_krw_k": "c_out"})
    m = inn[["sido", "sgg", "p_in", "c_in"]].merge(out[["sido", "sgg", "p_out", "c_out"]], on=["sido", "sgg"], how="outer")
    for c in ["p_in", "p_out", "c_in", "c_out"]:
        m[c] = m[c].fillna(0)
    m["outflow_patient_ratio"] = m["p_out"] / (m["p_in"] + m["p_out"]).replace(0, pd.NA)
    m["outflow_cost_ratio"] = m["c_out"] / (m["c_in"] + m["c_out"]).replace(0, pd.NA)
    return m


# ─────────── HIRA (시·도 단위) ───────────


def _hira_xlsx_drop_title(df: pd.DataFrame) -> pd.DataFrame:
    """HIRA xlsx는 row0이 타이틀, row1이 빈 행, row2~3이 헤더 구조."""
    return df.iloc[3:].reset_index(drop=True)


def load_hira_facilities() -> pd.DataFrame:
    """01_facilities — 유일한 시·군·구 단위 HIRA. 시도 + 시군구 + 종별 시설수.
    표기에 시도 prefix("대구중구")가 붙어 있어 정규화 + 특례시 합산.
    """
    df = pd.read_excel(paths.HIRA_FACILITIES, sheet_name=0, header=2)
    df = df.rename(columns={df.columns[0]: "sido", df.columns[1]: "sgg"})
    df["sido"] = normalize_sido(df["sido"])
    df = df[df["sgg"] != "계"].copy().reset_index(drop=True)
    # "-"(데이터 없음/0)를 0으로 치환하고 숫자형 변환
    for c in df.columns:
        if c in ("sido", "sgg"):
            continue
        df[c] = pd.to_numeric(df[c].astype(str).str.replace("-", "0").str.replace(",", ""), errors="coerce").fillna(0)
    return normalize_sgg(df)


def load_hira_doctors() -> pd.DataFrame:
    """03_doctors — 시·도 × 요양기관종별. '소계' 행이 시도 총합."""
    df = pd.read_excel(paths.HIRA_DOCTORS, sheet_name=0, header=[2, 3])
    df.columns = ["_".join([str(x) for x in c if "Unnamed" not in str(x) and str(x) != "nan"]).strip("_") for c in df.columns]
    first2 = df.columns[:2]
    df = df.rename(columns={first2[0]: "sido", first2[1]: "kind"})
    df["sido"] = normalize_sido(df["sido"])
    df = df[df["kind"] == "소계"].copy().drop(columns=["kind"]).reset_index(drop=True)
    return df


def load_hira_nurses() -> pd.DataFrame:
    df = pd.read_excel(paths.HIRA_NURSES, sheet_name=0, header=[2, 3])
    df.columns = ["_".join([str(x) for x in c if "Unnamed" not in str(x) and str(x) != "nan"]).strip("_") for c in df.columns]
    first2 = df.columns[:2]
    df = df.rename(columns={first2[0]: "sido", first2[1]: "kind"})
    df["sido"] = normalize_sido(df["sido"])
    df = df[df["kind"] == "소계"].copy().drop(columns=["kind"]).reset_index(drop=True)
    return df


def load_hira_specialists() -> pd.DataFrame:
    """02_specialists — 시·도 × 요양기관종별 × 전문과목. '계' 행이 시도 총합."""
    df = pd.read_excel(paths.HIRA_SPECIALISTS, sheet_name=0, header=2)
    df = df.rename(columns={df.columns[0]: "sido", df.columns[1]: "kind"})
    df["sido"] = normalize_sido(df["sido"])
    df = df[df["kind"] == "계"].copy().drop(columns=["kind"]).reset_index(drop=True)
    return df


def load_hira_equipment() -> pd.DataFrame:
    df = pd.read_excel(paths.HIRA_EQUIPMENT, sheet_name=0, header=2)
    df = df.rename(columns={df.columns[0]: "sido", df.columns[1]: "kind"})
    df["sido"] = normalize_sido(df["sido"])
    df = df[df["kind"] == "계"].copy().drop(columns=["kind"]).reset_index(drop=True)
    return df


def load_hira_special_rooms() -> pd.DataFrame:
    df = pd.read_excel(paths.HIRA_SPECIAL_ROOMS, sheet_name=0, header=[2, 3])
    df.columns = ["_".join([str(x) for x in c if "Unnamed" not in str(x) and str(x) != "nan"]).strip("_") for c in df.columns]
    first2 = df.columns[:2]
    df = df.rename(columns={first2[0]: "sido", first2[1]: "kind"})
    df["sido"] = normalize_sido(df["sido"])
    df = df[df["kind"] == "계"].copy().drop(columns=["kind"]).reset_index(drop=True)
    return df
