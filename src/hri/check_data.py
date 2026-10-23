"""원자료 검사 — data/raw/MANIFEST.yaml 기준으로 파일 존재·SHA256을 확인한다.

    python -m hri.check_data

- paths.py의 원자료 상수와 MANIFEST 항목이 1:1로 맞는지 먼저 확인
- used=true 파일이 없거나 해시가 다르면 종료코드 1
- 누락 파일은 어디서 받는지(출처·통계표명·URL) 안내
"""

from __future__ import annotations

import hashlib
import sys
import unicodedata
from pathlib import Path

import yaml

from . import paths

MANIFEST = paths.RAW / "MANIFEST.yaml"


def _nfc(s: str) -> str:
    # macOS 파일명은 NFD로 들어오는 경우가 있어 비교 전 정규화
    return unicodedata.normalize("NFC", s)


def raw_constants() -> dict[str, str]:
    """paths.py의 원자료 상수 → {key: data/raw 기준 상대경로}."""
    out = {}
    for name, value in vars(paths).items():
        if not name.isupper():
            continue
        items = value.items() if isinstance(value, dict) else [(None, value)]
        for sub, p in items:
            if isinstance(p, Path) and p.suffix and paths.RAW in p.parents:
                key = f"{name}[{sub}]" if sub else name
                out[key] = _nfc(p.relative_to(paths.RAW).as_posix())
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not MANIFEST.exists():
        print(f"MANIFEST 없음: {MANIFEST}")
        return 1
    entries = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["files"]
    manifest = {e["key"]: e for e in entries}

    errors = 0
    consts = raw_constants()
    for key in sorted(set(consts) - set(manifest)):
        print(f"[SYNC] paths.py의 {key} 가 MANIFEST에 없음")
        errors += 1
    for key in sorted(set(manifest) - set(consts)):
        print(f"[SYNC] MANIFEST의 {key} 가 paths.py에 없음")
        errors += 1
    for key in sorted(set(consts) & set(manifest)):
        if consts[key] != _nfc(manifest[key]["path"]):
            print(f"[SYNC] {key} 경로 불일치: paths.py={consts[key]} MANIFEST={manifest[key]['path']}")
            errors += 1

    missing = []
    for e in entries:
        p = paths.RAW / e["path"]
        tag = "" if e["used"] else " (미사용)"
        if not p.exists():
            print(f"[MISSING]  {e['path']}{tag}")
            if e["used"]:
                missing.append(e)
                errors += 1
        elif sha256(p) != e["sha256"]:
            print(f"[MISMATCH] {e['path']}{tag} — 해시가 다름 (파일이 갱신됐거나 다른 버전)")
            if e["used"]:
                errors += 1
        else:
            print(f"[OK]       {e['path']}{tag}")

    if missing:
        print("\n누락된 원자료 받는 곳:")
        for e in missing:
            print(f"  - {e['path']}")
            print(f"      출처: {e.get('org') or '미기록'} / {e.get('source') or ''}")
            print(f"      통계표: {e.get('table_name')}" + (f" ({e['table_id']})" if e.get("table_id") else ""))
            print(f"      URL: {e.get('url') or '미기록'}  기준시점: {e.get('reference_period')}")
        print("\n받은 파일을 위 경로(data/raw/ 기준)에 두면 됩니다.")
        print("원자료 없이 결과만 재현하려면: make reproduce")

    print(f"\n{'문제 없음' if errors == 0 else f'문제 {errors}건'}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
