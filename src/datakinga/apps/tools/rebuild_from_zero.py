"""
Rebuild pipeline from zero:
1) Backup current SQLite DB
2) Clean downloaded Excel staging folders
3) Re-download data month-by-month with main.py
4) Audit extraction coverage (expected sucursales)
5) Upload with pre-Supabase audit gate
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / "DataBase" / "datakinga.db"
STAGING_FOLDERS = [
    ROOT / "DataBase" / "Detalle",
    ROOT / "DataBase" / "Consumos",
    ROOT / "DataBase" / "Cinta",
]

DEFAULT_EXPECTED = [
    "COSTAVERDE",
    "PASADENA",
    "ENTRE RIOS",
    "SAAVEDRA",
    "SAENZ PENA",
]


def month_ranges(start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
    chunks: List[Tuple[datetime, datetime]] = []
    current = start.replace(day=1)
    while current <= end:
        month_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        chunk_start = max(current, start)
        chunk_end = min(month_end, end)
        chunks.append((chunk_start, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


def fmt_dmy(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y")


def backup_db() -> Path | None:
    if not DB_FILE.exists():
        print("[backup] SQLite DB not found, skipping backup.")
        return None

    backup_dir = ROOT / "DataBase" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"datakinga_{stamp}.db"
    shutil.copy2(DB_FILE, dest)
    print(f"[backup] DB backup created: {dest}")
    return dest


def clean_staging() -> int:
    removed = 0
    for folder in STAGING_FOLDERS:
        folder.mkdir(parents=True, exist_ok=True)
        for pattern in ("*.xls", "*.xlsx"):
            for file_path in glob.glob(str(folder / pattern)):
                try:
                    os.remove(file_path)
                    removed += 1
                except OSError as exc:
                    print(f"[clean] Could not remove {file_path}: {exc}")
    print(f"[clean] Removed {removed} staged excel files.")
    return removed


def run_python(script: str, args: List[str], env: dict | None = None) -> int:
    cmd = [sys.executable, script, *args]
    print("[run]", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return result.returncode


def parse_expected_sucursales(raw: str | None) -> List[str]:
    if raw and raw.strip():
        return [x.strip().upper().replace("_", " ") for x in raw.split(",") if x.strip()]
    env_raw = os.getenv("EXPECTED_SUCURSALES", "")
    if env_raw.strip():
        return [x.strip().upper().replace("_", " ") for x in env_raw.split(",") if x.strip()]
    return DEFAULT_EXPECTED[:]


def _extract_sucursal_from_detalle_name(stem: str) -> str:
    parts = stem.split("_")
    if len(parts) > 3:
        suc = " ".join(parts[:-3])
    else:
        suc = stem
    return suc.upper().replace("_", " ").strip()


def _extract_sucursal_from_consumos_name(stem: str) -> str:
    parts = stem.split("_")
    if len(parts) >= 5 and parts[0].lower() == "consumos":
        suc = " ".join(parts[1:-3])
    elif len(parts) > 3:
        suc = " ".join(parts[:-3])
    else:
        suc = stem
    return suc.upper().replace("_", " ").strip()


def audit_extraction_coverage(expected_sucursales: List[str]) -> bool:
    detalle_files = list((ROOT / "DataBase" / "Detalle").glob("*.xls*"))
    consumos_files = list((ROOT / "DataBase" / "Consumos").glob("*.xls*"))

    if not detalle_files:
        print("[coverage] ERROR: no Detalle files found after extraction.")
        return False
    if not consumos_files:
        print("[coverage] ERROR: no Consumos files found after extraction.")
        return False

    detalle_suc = {_extract_sucursal_from_detalle_name(f.stem) for f in detalle_files}
    consumos_suc = {_extract_sucursal_from_consumos_name(f.stem) for f in consumos_files}

    expected = {x.upper().replace("_", " ").strip() for x in expected_sucursales}
    miss_det = sorted(expected - detalle_suc)
    miss_con = sorted(expected - consumos_suc)

    print("[coverage] Expected sucursales:", sorted(expected))
    print("[coverage] Detalle sucursales found:", sorted(detalle_suc))
    print("[coverage] Consumos sucursales found:", sorted(consumos_suc))

    ok = True
    if miss_det:
        print("[coverage] ERROR missing in Detalle:", ", ".join(miss_det))
        ok = False
    if miss_con:
        print("[coverage] ERROR missing in Consumos:", ", ".join(miss_con))
        ok = False

    if ok:
        print("[coverage] OK: all expected sucursales were extracted.")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Full rebuild from zero with audit-before-upload")
    parser.add_argument("start", help="Start date DD/MM/YYYY")
    parser.add_argument("end", nargs="?", default=datetime.now().strftime("%d/%m/%Y"), help="End date DD/MM/YYYY")
    parser.add_argument("--expected-sucursales", default=None, help="Comma-separated expected sucursales")
    parser.add_argument("--no-upload", action="store_true", help="Download and audit coverage only")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing extraction/upload")
    args = parser.parse_args()

    try:
        start = datetime.strptime(args.start, "%d/%m/%Y")
        end = datetime.strptime(args.end, "%d/%m/%Y")
    except ValueError:
        print("ERROR: dates must use DD/MM/YYYY")
        return 2

    if start > end:
        print("ERROR: start date must be <= end date")
        return 2

    expected = parse_expected_sucursales(args.expected_sucursales)
    chunks = month_ranges(start, end)

    print("=" * 72)
    print("REBUILD FROM ZERO")
    print("=" * 72)
    print(f"Range: {fmt_dmy(start)} -> {fmt_dmy(end)}")
    print(f"Chunks: {len(chunks)}")
    print("Expected sucursales:", expected)
    print("Upload enabled:", not args.no_upload)
    print("Dry run:", args.dry_run)

    if args.dry_run:
        for i, (d, h) in enumerate(chunks, 1):
            print(f"  Chunk {i}: {fmt_dmy(d)} -> {fmt_dmy(h)}")
        return 0

    backup_db()
    clean_staging()

    for i, (d, h) in enumerate(chunks, 1):
        print("\n" + "-" * 72)
        print(f"Chunk {i}/{len(chunks)}: {fmt_dmy(d)} -> {fmt_dmy(h)}")
        print("-" * 72)
        code = run_python("main.py", [fmt_dmy(d), fmt_dmy(h)])
        if code != 0:
            print(f"ERROR: extraction failed on chunk {i} with code {code}")
            return code

    coverage_ok = audit_extraction_coverage(expected)
    if not coverage_ok:
        print("\nERROR: extraction coverage audit failed. Upload aborted.")
        return 3

    if args.no_upload:
        print("\nDone: extraction and coverage audit completed. Upload skipped by flag.")
        return 0

    env = os.environ.copy()
    env["EXPECTED_SUCURSALES"] = ",".join(expected)
    code = run_python("upload_from_local.py", [], env=env)
    if code != 0:
        print("\nERROR: upload_from_local.py failed (includes pre-Supabase audit gate).")
        return code

    print("\nSuccess: full rebuild and audited upload completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
