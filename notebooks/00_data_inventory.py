"""Phase 1 — 데이터 인벤토리 점검 스크립트.

data/raw/ 하위 모든 파일의 스키마·헤더·결측·시군구 커버리지를 출력한다.
결과는 reports/inventory_report.md 로 기록한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hri import paths  # noqa: E402


def header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def read_kosis_csv(path: Path, header_rows: int = 2) -> pd.DataFrame:
    """KOSIS / KOSIS-like CSV는 cp949 + 2~3행 다중 헤더가 표준이다."""
    return pd.read_csv(path, encoding="cp949", header=list(range(header_rows)))


def inspect_csv(path: Path, encoding: str = "cp949", header_rows: int = 1) -> None:
    print(f"\n📄 {path.name}")
    print(f"   size: {path.stat().st_size:,} bytes")
    try:
        df_raw = pd.read_csv(path, encoding=encoding, header=None, nrows=5)
        print(f"   raw shape head: {df_raw.shape}")
        print(f"   first row: {list(df_raw.iloc[0])}")
        if df_raw.shape[0] > 1:
            print(f"   second row: {list(df_raw.iloc[1])}")
        df = pd.read_csv(path, encoding=encoding, header=list(range(header_rows)))
        print(f"   total rows: {len(df):,}")
        print(f"   columns ({len(df.columns)}): {list(df.columns)[:8]}{' ...' if len(df.columns) > 8 else ''}")
    except Exception as e:
        print(f"   ❌ read failed: {e}")


def inspect_excel(path: Path) -> None:
    print(f"\n📄 {path.name}")
    print(f"   size: {path.stat().st_size:,} bytes")
    try:
        xl = pd.ExcelFile(path)
        print(f"   sheets: {xl.sheet_names}")
        for sheet in xl.sheet_names:
            df_raw = pd.read_excel(path, sheet_name=sheet, header=None, nrows=6)
            print(f"   [{sheet}] preview shape: {df_raw.shape}")
            for i in range(min(3, df_raw.shape[0])):
                row_vals = [str(v)[:30] for v in df_raw.iloc[i].tolist()[:10]]
                print(f"     row{i}: {row_vals}")
    except Exception as e:
        print(f"   ❌ read failed: {e}")


def main() -> None:
    header("HIRA 보건의료빅데이터 (시·군·구 단위)")
    for p in [
        paths.HIRA_FACILITIES,
        paths.HIRA_SPECIALISTS,
        paths.HIRA_DOCTORS,
        paths.HIRA_NURSES,
        paths.HIRA_SPECIAL_ROOMS,
        paths.HIRA_EQUIPMENT,
    ]:
        if p.exists():
            inspect_excel(p)
        else:
            print(f"❌ MISSING: {p}")
    for p in [paths.HIRA_CLAIMS, paths.HIRA_RESOURCES]:
        if p.exists():
            inspect_csv(p, encoding="cp949", header_rows=1)
        else:
            print(f"❌ MISSING: {p}")

    header("KOSIS 기존")
    inspect_csv(paths.KOSIS_DEATH, encoding="cp949", header_rows=2)

    header("new/ — 보완 데이터 (2024 기준)")
    inspect_csv(paths.POPULATION, encoding="cp949", header_rows=1)
    inspect_csv(paths.WELFARE, encoding="cp949", header_rows=1)
    inspect_csv(paths.UNMET_CARE, encoding="cp949", header_rows=2)
    inspect_csv(paths.PUBLIC_HOSPITAL_STAFF, encoding="cp949", header_rows=3)

    header("관내 진료현황 (4개 권역)")
    for region, p in paths.INPATIENT_FILES.items():
        print(f"\n— {region} —")
        inspect_csv(p, encoding="cp949", header_rows=2)

    header("관외 진료현황 (4개 권역)")
    for region, p in paths.OUTPATIENT_FILES.items():
        print(f"\n— {region} —")
        inspect_csv(p, encoding="cp949", header_rows=2)


if __name__ == "__main__":
    main()
