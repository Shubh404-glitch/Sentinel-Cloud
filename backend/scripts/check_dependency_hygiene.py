"""
Dependency-hygiene check (Section 15, Section 7).

"Cloud never scans" is a structural property of this architecture, not a
configuration choice -- Section 7 requires this be enforced as a
dependency-manifest check in CI, not left to code review alone. This
script fails (non-zero exit) if any known raw-socket-capable,
packet-crafting, or port-scanning package appears anywhere in the
resolved dependency tree.

Run this:
  - Locally, any time before committing a dependency change.
  - In CI, on every build (Section 16: CI/CD pipeline), against the
    actual installed environment (`pip freeze`), not just this static
    manifest file -- a transitive dependency can introduce a forbidden
    package even if pyproject.toml/requirements.txt never mention it by
    name directly.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

FORBIDDEN_PACKAGES = {
    "scapy",
    "pypcap",
    "pcapy",
    "pcapy-ng",
    "python-libpcap",
    "netfilterqueue",
    "python-nmap",
    "nmap",
    "python-masscan",
    "impacket",
    "dpkt",
    "libnetfilter-queue",
    "pyshark",
    "raw-socket",
}

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]


def check_manifest_file(path: pathlib.Path) -> list[str]:
    """Check a static requirements.txt / pyproject.toml for forbidden
    package names (best-effort text scan -- the real gate is
    check_installed_environment below, run against a fully resolved
    install including transitive dependencies)."""
    if not path.exists():
        return []
    text = path.read_text().lower()
    hits = []
    for pkg in FORBIDDEN_PACKAGES:
        if re.search(rf"\b{re.escape(pkg)}\b", text):
            hits.append(f"{pkg} (found in {path.name})")
    return hits


def check_installed_environment() -> list[str]:
    """Check every package actually installed in the current Python
    environment (i.e. the full resolved dependency tree, transitive
    dependencies included) via `pip freeze`. This is the authoritative
    check; the manifest-file check above only catches direct,
    intentional additions before anything is even installed."""
    try:
        output = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=30, check=False,
        ).stdout.lower()
    except Exception as exc:  # noqa: BLE001
        return [f"COULD NOT RUN pip freeze -- {exc} (see Stage 1 Completion Report: Environment Blocked)"]

    hits = []
    for pkg in FORBIDDEN_PACKAGES:
        if re.search(rf"^{re.escape(pkg)}==", output, re.MULTILINE):
            hits.append(f"{pkg} (installed in current environment)")
    return hits


def main() -> int:
    findings: list[str] = []
    findings += check_manifest_file(BACKEND_DIR / "requirements.txt")
    findings += check_manifest_file(BACKEND_DIR / "pyproject.toml")
    findings += check_installed_environment()

    if findings:
        print("FAILED -- forbidden raw-socket/packet-crafting/scanning package(s) detected:")
        for f in findings:
            print(f"  ✗ {f}")
        return 1

    print("PASSED -- no raw-socket, packet-crafting, or port-scanning package found in manifest or installed environment.")
    print(f"Checked against a blocklist of {len(FORBIDDEN_PACKAGES)} known package names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
