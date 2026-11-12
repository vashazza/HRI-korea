"""Phase 2 — 마스터 데이터셋 빌더.

229 시·군·구 × 다중 출처를 하나의 wide 테이블(master_dataset.csv)로 통합.
"""

from __future__ import annotations

import pandas as pd

from . import loader, paths


def _hira_sido_per_capita(df: pd.DataFrame, value_cols: list[str], pop_sido: pd.DataFrame) -> pd.DataFrame:
    """시·도 단위 HIRA 값을 시·도 1인당으로 환산.

    df: ['sido', *value_cols]  (HIRA 시·도 집계)
    pop_sido: ['sido', 'total_population'] (시·도 합계)
    반환: ['sido', *(c+'_per_capita' for c in value_cols)]
    """
    m = df.merge(pop_sido, on="sido", how="inner")
    out = m[["sido"]].copy()
    for c in value_cols:
        out[f"{c}_per_capita"] = pd.to_numeric(m[c], errors="coerce") / m["total_population"]
    return out


def build_master() -> pd.DataFrame:
    """229 시·군·구 마스터 데이터셋 생성."""

    # ── 인구 (마스터 키) ─────────────────────
    pop = loader.population_totals(paths.BASE_YEAR)
    pop_sido = pop.groupby("sido", as_index=False)["total_population"].sum()
    pop_sido.columns = ["sido", "sido_total_population"]

    master = pop.copy()  # 229 rows

    # ── 종속변수 (옵션 B): 미충족의료율 ─────
    unmet = loader.load_unmet_care().rename(
        columns={"n": "unmet_n", "crude": "unmet_crude_pct", "std": "unmet_std_pct"}
    )
    master = master.merge(unmet, on=["sido", "sgg"], how="left")

    # ── 보조 종속변수: 관외이용률 ─────────
    outflow = loader.load_outflow_ratio()[["sido", "sgg", "outflow_patient_ratio", "outflow_cost_ratio"]]
    master = master.merge(outflow, on=["sido", "sgg"], how="left")

    # ── DPI: 의료급여 수급률 ─────────────
    aid = loader.load_welfare_medical_aid()
    master = master.merge(aid, on=["sido", "sgg"], how="left")
    master["medical_aid_recipient_rate"] = (
        master["medical_aid_recipients"] / master["total_population"] * 100
    )

    # ── 진료현황 (관내·관외 합계 — 의료이용량 proxy) ─────────
    t_in = loader.load_treatment("in")[["sido", "sgg", "patients", "cost_krw_k"]].rename(
        columns={"patients": "patients_in", "cost_krw_k": "cost_in"}
    )
    t_out = loader.load_treatment("out")[["sido", "sgg", "patients", "cost_krw_k"]].rename(
        columns={"patients": "patients_out", "cost_krw_k": "cost_out"}
    )
    master = master.merge(t_in, on=["sido", "sgg"], how="left").merge(t_out, on=["sido", "sgg"], how="left")
    for c in ["patients_in", "patients_out", "cost_in", "cost_out"]:
        master[c] = master[c].fillna(0)
    master["total_patients"] = master["patients_in"] + master["patients_out"]
    master["total_cost_krw_k"] = master["cost_in"] + master["cost_out"]
    # 만성질환·일반 진료 분리는 disease코드가 없어 불가. 1인당 진료비를 proxy로.
    master["claims_cost_per_capita"] = master["total_cost_krw_k"] / master["total_population"]

    # ── IAI 1: facilities (유일한 시·군·구 단위 HIRA) ─────
    fac = loader.load_hira_facilities()
    # facilities는 한글 종별 컬럼들 (계, 상급종합병원, 종합병원, 병원, 의원, ...)
    fac_cols_keep = ["sido", "sgg"]
    fac_renames = {
        "계": "facilities_total",
        "상급종합병원": "facilities_tertiary",
        "종합병원": "facilities_general_hospital",
        "병원": "facilities_hospital",
        "요양병원": "facilities_long_term",
        "정신병원": "facilities_psychiatric",
        "의원": "facilities_clinic",
        "치과병원": "facilities_dental_hospital",
        "치과의원": "facilities_dental_clinic",
        "한방병원": "facilities_oriental_hospital",
        "한의원": "facilities_oriental_clinic",
        "보건소": "facilities_health_center",
        "보건지소": "facilities_health_sub_center",
        "보건진료소": "facilities_rural_health_post",
        "보건의료원": "facilities_public_health_medical",
        "조산원": "facilities_midwifery",
        "약국": "facilities_pharmacy",
    }
    fac_use = fac[[c for c in fac.columns if c in fac_renames or c in ("sido", "sgg")]].rename(columns=fac_renames)
    master = master.merge(fac_use, on=["sido", "sgg"], how="left")
    for c in fac_renames.values():
        if c in master.columns:
            master[c] = master[c].fillna(0)

    # ── IAI 2 / WAI: HIRA 시·도 단위 → 시·군·구 인구비례 분배 ─────
    # 분배 원칙: 시·도 합계 × (시·군·구 인구 / 시·도 인구). per_100k 표준화 시 시·도 값과 동일해짐.
    pop_sido_sum = pop.groupby("sido", as_index=False)["total_population"].sum().rename(
        columns={"total_population": "sido_pop"}
    )

    def _distribute_sido(df_sido: pd.DataFrame, value_cols: list[str], prefix: str) -> pd.DataFrame:
        """df_sido: [sido, *value_cols] → 229 시·군·구 단위로 인구 비례 분배."""
        if df_sido.empty:
            raise ValueError(f"{prefix}: 시·도 표가 비어 있다 (합계 행 필터 확인)")
        m = master[["sido", "sgg", "total_population"]].merge(pop_sido_sum, on="sido").merge(
            df_sido, on="sido", how="left"
        )
        share = (m["total_population"] / m["sido_pop"]).clip(lower=0)
        out = m[["sido", "sgg"]].copy()
        for c in value_cols:
            out[f"{prefix}_{c}"] = pd.to_numeric(m[c], errors="coerce").fillna(0) * share
        return out

    # 의사
    docs = loader.load_hira_doctors()
    doc_value_cols = [c for c in docs.columns if c != "sido"]
    doc_dist = _distribute_sido(docs, doc_value_cols, "doc")
    master = master.merge(doc_dist, on=["sido", "sgg"], how="left")

    # 간호사
    nurs = loader.load_hira_nurses()
    nur_value_cols = [c for c in nurs.columns if c != "sido"]
    nur_dist = _distribute_sido(nurs, nur_value_cols, "nur")
    master = master.merge(nur_dist, on=["sido", "sgg"], how="left")

    # 전문의 — 컬럼이 많아서 핵심 5과만
    spe = loader.load_hira_specialists()
    spe_cols_focus = [c for c in ["합계", "내과", "외과", "응급의학과", "소아청소년과", "산부인과", "정신건강의학과"] if c in spe.columns]
    spe_dist = _distribute_sido(spe[["sido"] + spe_cols_focus], spe_cols_focus, "spe")
    master = master.merge(spe_dist, on=["sido", "sgg"], how="left")

    # 장비
    eq = loader.load_hira_equipment()
    # 핵심 장비만 — CT/MRI/PET
    eq_cols_focus = [c for c in eq.columns if any(k in c for k in ["전산화단층", "자기공명", "양전자", "혈관조영", "유방촬영"])]
    if eq_cols_focus:
        eq_dist = _distribute_sido(eq[["sido"] + eq_cols_focus], eq_cols_focus, "eq")
        master = master.merge(eq_dist, on=["sido", "sgg"], how="left")

    # 특수진료실
    sr = loader.load_hira_special_rooms()
    sr_cols_focus = [c for c in sr.columns if any(k in c for k in ["분만", "신생아", "수술", "중환자"])]
    if sr_cols_focus:
        sr_dist = _distribute_sido(sr[["sido"] + sr_cols_focus], sr_cols_focus, "sr")
        master = master.merge(sr_dist, on=["sido", "sgg"], how="left")

    return master


def per_100k_standardize(master: pd.DataFrame, count_cols: list[str]) -> pd.DataFrame:
    """주어진 컬럼을 인구 10만명당으로 표준화."""
    out = master.copy()
    pop_100k = out["total_population"] / 100_000
    for c in count_cols:
        if c in out.columns:
            out[f"{c}_per_100k"] = out[c] / pop_100k
    return out


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    master = build_master()
    print(f"master shape: {master.shape}")
    print(f"columns ({len(master.columns)}): {master.columns.tolist()}")

    out_path = paths.PROCESSED / "master_dataset.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"saved → {out_path}")
