"""reproduce 결과가 커밋된 결과와 같은지 확인한다 (수치는 허용오차 1e-9, 나머지는 정확히).

BLAS 빌드가 다르면 마지막 자리 부동소수점이 달라 바이트 비교 대신 이걸 쓴다.

    hri reproduce && python scripts/check_reproduced.py
"""

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-9


def committed(rel: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT)


def json_close(a, b) -> bool:
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(json_close(a[k], b[k]) for k in a)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return bool(np.isclose(a, b, rtol=TOL, atol=TOL))
    return a == b


def main() -> int:
    failed = 0
    for p in sorted((ROOT / "data" / "processed").glob("*.csv")):
        rel = p.relative_to(ROOT).as_posix()
        try:
            pd.testing.assert_frame_equal(
                pd.read_csv(io.BytesIO(committed(rel))), pd.read_csv(p),
                check_exact=False, rtol=TOL, atol=TOL,
            )
            print(f"[OK]   {rel}")
        except AssertionError as e:
            print(f"[DIFF] {rel}\n{e}")
            failed += 1

    rel = "reports/hri_weights.json"
    if json_close(json.loads(committed(rel)), json.loads((ROOT / rel).read_text(encoding="utf-8"))):
        print(f"[OK]   {rel}")
    else:
        print(f"[DIFF] {rel}")
        failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
