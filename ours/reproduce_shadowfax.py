"""Re-run the Shadowfax artifact on Windows with MSYS2 UCRT64.

This runner invokes the authors' unmodified cryptographic implementation.
The accompanying patch changes only Windows build/benchmark compatibility.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


WORK = Path(__file__).resolve().parent.parent
SOURCE = WORK / "source"
LOGS = WORK / "logs"
PATCH = Path(__file__).resolve().with_name("windows-compat.patch")
BASH = Path(r"D:\msys64\usr\bin\bash.exe")
COMMIT = "20d9d2e60487d317d38f9e4070dde16630beeb1b"
CONFIGS = (("mlkem", "GandalfFalcon"), ("BAT", "GandalfMitaka"))
TRIALS = 3


def command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def cpu_name() -> str:
    result = command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name",
        ],
        check=False,
    )
    return result.stdout.strip() or platform.processor()


def apply_compat_patch() -> None:
    actual = command(["git", "-C", str(SOURCE), "rev-parse", "HEAD"]).stdout.strip()
    if actual != COMMIT:
        raise RuntimeError(f"Expected upstream commit {COMMIT}, found {actual}")
    reverse = command(
        ["git", "-C", str(SOURCE), "apply", "--reverse", "--check", str(PATCH)],
        check=False,
    )
    if reverse.returncode == 0:
        return
    forward = command(
        ["git", "-C", str(SOURCE), "apply", "--check", str(PATCH)], check=False
    )
    if forward.returncode != 0:
        raise RuntimeError(f"Compatibility patch cannot be applied:\n{forward.stderr}")
    command(["git", "-C", str(SOURCE), "apply", str(PATCH)])


def bash(command_text: str, log_name: str) -> str:
    env = os.environ.copy()
    env["MSYSTEM"] = "UCRT64"
    env["CHERE_INVOKING"] = "yes"
    env["SHADOWFAX_SOURCE"] = str(SOURCE)
    script = (
        'set -euo pipefail; cd "$(cygpath -u "$SHADOWFAX_SOURCE")/src"; '
        + command_text
    )
    result = subprocess.run(
        [str(BASH), "-lc", script], env=env, text=True, capture_output=True
    )
    text = result.stdout + result.stderr
    (LOGS / log_name).write_text(text, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"{log_name} failed with exit {result.returncode}")
    return text


def verify_test(text: str, log_name: str) -> None:
    expected = ((2048, 2048), (0, 4096), (0, 2048))
    found = [
        (int(a), int(b))
        for a, b in re.findall(r"(\d+)/(\d+)[^\n]*\(ok\)", text)
    ]
    if tuple(found) != expected:
        raise RuntimeError(f"Unexpected correctness results in {log_name}: {found}")


def parse_benchmark(text: str) -> dict[str, int]:
    def one(pattern: str) -> int:
        found = re.search(pattern, text)
        if not found:
            raise RuntimeError(f"Benchmark field missing: {pattern}")
        return int(found.group(1))

    return {
        "public_key_bytes": one(r"Hybrid AKEM public key bytes:\s*(\d+)"),
        "secret_key_bytes": one(r"Hybrid AKEM secret key bytes:\s*(\d+)"),
        "ciphertext_bytes": one(r"Hybrid AKEM ciphertext bytes:\s*(\d+)"),
        "keygen_kcycles": one(r"HybridAKEMKeyGen\{(\d+)\}"),
        "encap_kcycles": one(r"HybridAKEMEnc\{(\d+)\}"),
        "decap_kcycles": one(r"HybridAKEMDec\{(\d+)\}"),
    }


def main() -> None:
    if not BASH.is_file():
        raise RuntimeError(f"MSYS2 Bash missing: {BASH}")
    if not SOURCE.is_dir() or not PATCH.is_file():
        raise RuntimeError("Place the upstream clone and windows-compat.patch first")
    LOGS.mkdir(exist_ok=True)
    apply_compat_patch()

    metadata = {
        "upstream_url": "https://github.com/vincentvbh/shadowfax",
        "upstream_commit": COMMIT,
        "patch_sha256": hashlib.sha256(PATCH.read_bytes()).hexdigest(),
        "run_time_china": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "windows": platform.platform(),
        "cpu": cpu_name(),
        "gcc": bash("gcc --version | head -n 1", "gcc_version.log").strip(),
        "make": bash("make --version | head -n 1", "make_version.log").strip(),
    }
    results: dict[str, object] = {"environment": metadata, "configs": {}}

    for kem, rsig in CONFIGS:
        label = f"{kem}_{rsig}"
        print(f"Building {label}", flush=True)
        bash("make clean", f"{label}_clean.log")
        bash(
            f"make -j12 KEM_PATH={kem} RSIG_PATH={rsig}",
            f"{label}_build.log",
        )

        tests: dict[str, str] = {}
        for binary in ("test_dh_akem", "test_pq_akem", "test_h_akem"):
            log_name = f"{label}_{binary}.log"
            print(f"Testing {label}: {binary}", flush=True)
            output = bash(f"./{binary}", log_name)
            verify_test(output, log_name)
            tests[binary] = "passed (2048 valid; 4096 and 2048 negative checks)"

        trials: list[dict[str, int]] = []
        for trial in range(1, TRIALS + 1):
            print(f"Benchmarking {label}: trial {trial}/{TRIALS}", flush=True)
            output = bash(
                "./speed_h_akem", f"{label}_speed_h_trial{trial}.log"
            )
            trials.append(parse_benchmark(output))

        sizes = {
            key: trials[0][key]
            for key in ("public_key_bytes", "secret_key_bytes", "ciphertext_bytes")
        }
        if any(
            trial[key] != size for trial in trials for key, size in sizes.items()
        ):
            raise RuntimeError(f"Size changed between trials for {label}")
        summary = {
            key: {
                "median": statistics.median(trial[key] for trial in trials),
                "minimum": min(trial[key] for trial in trials),
                "maximum": max(trial[key] for trial in trials),
            }
            for key in ("keygen_kcycles", "encap_kcycles", "decap_kcycles")
        }
        results["configs"][label] = {
            "tests": tests,
            "sizes": sizes,
            "trials": trials,
            "summary": summary,
        }
        (WORK / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"All required experiments completed. Results: {WORK / 'results.json'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
