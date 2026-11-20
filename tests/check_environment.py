"""Verify the CI environment against the selected Home Assistant release."""

import argparse
import json
from importlib.metadata import metadata, version
from pathlib import Path
from platform import python_version

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home-assistant", required=True)
    parser.add_argument("--python-version-file", type=Path, required=True)
    parser.add_argument("--constraints", type=Path, required=True)
    parser.add_argument("--serialx-floor", default="")
    args = parser.parse_args()

    ha = metadata("homeassistant")
    if ha["Version"] != args.home_assistant:
        raise SystemExit(f"Home Assistant {ha['Version']} != {args.home_assistant}")

    python = Version(python_version())
    python_target = Version(args.python_version_file.read_text().strip())
    supported_python = SpecifierSet(ha["Requires-Python"])
    if python not in supported_python:
        raise SystemExit(
            f"Python {python} is outside Home Assistant's {supported_python}"
        )
    patch_wildcard = ".*" if len(python_target.release) == 2 else ""
    if python not in SpecifierSet(f"=={python_target}{patch_wildcard}"):
        raise SystemExit(f"Python {python} does not match target {python_target}")

    manifest = json.loads(
        (ROOT / "custom_components/connectpro/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    requirement = next(
        requirement
        for value in manifest["requirements"]
        if (requirement := Requirement(value)).name == "serialx"
    )
    serialx = Version(version("serialx"))
    if serialx not in requirement.specifier:
        raise SystemExit(f"serialx {serialx} is outside {requirement}")

    upstream = []
    for line in args.constraints.read_text(encoding="utf-8").splitlines():
        value = line.partition("#")[0].strip()
        if value:
            constraint = Requirement(value)
            if constraint.name == "serialx" and (
                constraint.marker is None or constraint.marker.evaluate()
            ):
                upstream.append(constraint.specifier)

    if args.serialx_floor:
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        if args.home_assistant != hacs["homeassistant"]:
            raise SystemExit(
                f"Minimum job must test Home Assistant {hacs['homeassistant']}"
            )
        if not any(
            bound.operator == ">="
            and Version(bound.version).release[:2] == python_target.release[:2]
            for bound in supported_python
        ):
            raise SystemExit(
                f"Python {python_target} is not the Home Assistant minimum series"
            )
        if f">={args.serialx_floor}" not in {
            str(bound) for bound in requirement.specifier
        }:
            raise SystemExit(
                f"serialx {args.serialx_floor} is not the ConnectPro minimum"
            )
        if serialx != Version(args.serialx_floor):
            raise SystemExit(f"serialx {serialx} != minimum {args.serialx_floor}")
    elif len(upstream) != 1 or str(upstream[0]) != f"=={serialx}":
        raise SystemExit(
            f"Expected a Home Assistant pin matching serialx {serialx}; found {upstream}"
        )
    if any(serialx not in specifier for specifier in upstream):
        raise SystemExit(
            f"serialx {serialx} conflicts with Home Assistant constraints {upstream}"
        )

    print(
        f"Verified Home Assistant {ha['Version']}, Python {python}, and serialx {serialx}"
    )


if __name__ == "__main__":
    main()
