"""hri CLI — 파이프라인 단계를 한 명령으로 실행한다.

    hri reproduce     원자료 없이: indices → model → cluster → simulate → figures → map
    hri run-all       원자료부터: check-data → preprocess → reproduce
    hri <단계>        check-data | preprocess | indices | model | cluster | simulate | figures | map

각 단계는 별도 프로세스로 실행한다 (python -m hri.X / python scripts/X.py 와 동일).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request

from . import paths

GEOJSON = paths.DATA / "geo" / "skorea_sgg.geojson"
GEOJSON_URL = (
    "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/"
    "kostat/2013/json/skorea_municipalities_geo_simple.json"
)

STEPS = {
    "check-data": ["-m", "hri.check_data"],
    "preprocess": ["-m", "hri.preprocess"],
    "indices": ["-m", "hri.indices"],
    "model": ["-m", "hri.hri"],
    "cluster": ["-m", "hri.clustering"],
    "simulate": ["-m", "hri.simulation"],
    "figures": [str(paths.ROOT / "scripts" / "05_visualize.py")],
    "map": [str(paths.ROOT / "scripts" / "06_build_map.py")],
}
REPRODUCE = ["indices", "model", "cluster", "simulate", "figures", "map"]
RUN_ALL = ["check-data", "preprocess", *REPRODUCE]


def run_step(name: str) -> None:
    if name == "map" and not GEOJSON.exists():
        print(f"GeoJSON 내려받는 중 → {GEOJSON}")
        GEOJSON.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(GEOJSON_URL, GEOJSON)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(paths.ROOT / "src"), env.get("PYTHONPATH")]))
    print(f"▶ {name}", flush=True)
    subprocess.run([sys.executable, *STEPS[name]], cwd=paths.ROOT, env=env, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hri", description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=[*STEPS, "reproduce", "run-all"])
    args = parser.parse_args(argv)

    steps = {"reproduce": REPRODUCE, "run-all": RUN_ALL}.get(args.command, [args.command])
    try:
        for s in steps:
            run_step(s)
    except subprocess.CalledProcessError as e:
        print(f"✗ 실패: {e.cmd[-1]} (exit {e.returncode})", file=sys.stderr)
        return e.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
