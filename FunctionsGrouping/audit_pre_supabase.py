"""
Pre-upload audits for Supabase ingestion.
Blocks writes when critical consistency checks fail.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class AuditReport:
    ok: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


CONSUMO_REQUIRED_COLS = ["Codigo", "Articulo", "Sucursal"]


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_name(name: str) -> str:
    s = _strip_accents(name)
    s = re.sub(r"\s+", "", s)
    return s.strip().lower()


def normalize_ticket_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = _normalize_name(str(col))
        if key == "numero":
            mapping[col] = "Numero"
        elif key == "codigo":
            mapping[col] = "Codigo"
        elif key == "descripcion":
            mapping[col] = "Descripcion"
        elif key == "sucursal":
            mapping[col] = "Sucursal"
        elif key == "fecha":
            mapping[col] = "Fecha"
        elif key == "hora":
            mapping[col] = "Hora"
    return df.rename(columns=mapping)


def _normalize_sucursal(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return _strip_accents(str(value)).strip().upper().replace("_", " ")


def _parse_expected_sucursales(default: List[str] | None = None) -> List[str]:
    raw = os.getenv("EXPECTED_SUCURSALES", "")
    if not raw.strip():
        return [_normalize_sucursal(x) for x in (default or []) if str(x).strip()]
    return [_normalize_sucursal(x) for x in raw.split(",") if x.strip()]


def _missing_expected(actual: pd.Series, expected: List[str]) -> Tuple[List[str], List[str]]:
    actual_set = set(_normalize_sucursal(x) for x in actual.dropna().astype(str))
    expected_set = set(_normalize_sucursal(x) for x in expected)
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    return missing, extra


def audit_tickets(df_tickets: pd.DataFrame, expected_sucursales: List[str] | None = None) -> AuditReport:
    errors: List[str] = []
    warnings: List[str] = []

    if df_tickets is None or df_tickets.empty:
        return AuditReport(
            ok=False,
            errors=["tickets dataset is empty"],
            warnings=[],
            metrics={"tickets_rows": 0},
        )

    df = normalize_ticket_columns(df_tickets.copy())

    required_cols = ["Numero", "Codigo", "Sucursal"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        return AuditReport(
            ok=False,
            errors=[f"tickets missing required columns: {', '.join(missing_cols)}"],
            warnings=[],
            metrics={"tickets_rows": len(df)},
        )

    for col in required_cols:
        df[col] = df[col].astype(str).str.strip()

    null_numero = int((df["Numero"] == "").sum())
    null_codigo = int((df["Codigo"] == "").sum())
    null_sucursal = int((df["Sucursal"] == "").sum())

    if null_numero > 0:
        errors.append(f"tickets with empty Numero: {null_numero}")
    if null_codigo > 0:
        errors.append(f"tickets with empty Codigo: {null_codigo}")
    if null_sucursal > 0:
        errors.append(f"tickets with empty Sucursal: {null_sucursal}")

    grp_num_cod = df.groupby(["Numero", "Codigo"]).size()
    grp_num_cod_suc = df.groupby(["Numero", "Codigo", "Sucursal"]).size()

    dup_groups_numero_codigo = int(grp_num_cod.gt(1).sum())
    dup_extra_numero_codigo = int((grp_num_cod - 1).clip(lower=0).sum())
    dup_groups_numero_codigo_sucursal = int(grp_num_cod_suc.gt(1).sum())

    if dup_groups_numero_codigo > 0:
        warnings.append(
            f"tickets duplicate Numero+Codigo groups: {dup_groups_numero_codigo} (extra rows: {dup_extra_numero_codigo})"
        )

    payload_cols = [c for c in df.columns if c not in ["Numero", "Codigo"]]
    conflicting = 0
    if payload_cols:
        conflicting = int(
            df.groupby(["Numero", "Codigo"])[payload_cols]
            .nunique(dropna=False)
            .max(axis=1)
            .gt(1)
            .sum()
        )

    if conflicting > 0:
        errors.append(f"tickets conflicting duplicate Numero+Codigo groups: {conflicting}")

    expected = _parse_expected_sucursales(expected_sucursales)
    if expected:
        missing, extra = _missing_expected(df["Sucursal"], expected)
        if missing:
            errors.append("tickets missing expected sucursales: " + ", ".join(missing))
        if extra:
            warnings.append("tickets extra sucursales found: " + ", ".join(extra))

    metrics = {
        "tickets_rows": int(len(df)),
        "tickets_unique_numero_codigo": int(df[["Numero", "Codigo"]].drop_duplicates().shape[0]),
        "tickets_dup_groups_numero_codigo": dup_groups_numero_codigo,
        "tickets_dup_groups_numero_codigo_sucursal": dup_groups_numero_codigo_sucursal,
        "tickets_conflicting_groups_numero_codigo": conflicting,
    }

    return AuditReport(ok=len(errors) == 0, errors=errors, warnings=warnings, metrics=metrics)


def audit_consumos(df_consumos: pd.DataFrame, expected_sucursales: List[str] | None = None) -> AuditReport:
    errors: List[str] = []
    warnings: List[str] = []

    if df_consumos is None or df_consumos.empty:
        return AuditReport(
            ok=False,
            errors=["consumos dataset is empty"],
            warnings=[],
            metrics={"consumos_rows": 0},
        )

    df = df_consumos.copy()
    missing_cols = [c for c in CONSUMO_REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        return AuditReport(
            ok=False,
            errors=[f"consumos missing required columns: {', '.join(missing_cols)}"],
            warnings=[],
            metrics={"consumos_rows": len(df)},
        )

    for col in CONSUMO_REQUIRED_COLS:
        df[col] = df[col].astype(str).str.strip()

    null_codigo = int((df["Codigo"] == "").sum())
    null_articulo = int((df["Articulo"] == "").sum())
    null_sucursal = int((df["Sucursal"] == "").sum())

    if null_codigo > 0:
        errors.append(f"consumos with empty Codigo: {null_codigo}")
    if null_articulo > 0:
        errors.append(f"consumos with empty Articulo: {null_articulo}")
    if null_sucursal > 0:
        errors.append(f"consumos with empty Sucursal: {null_sucursal}")

    grp_cas = df.groupby(["Codigo", "Articulo", "Sucursal"]).size()
    grp_cs = df.groupby(["Codigo", "Sucursal"]).size()

    dup_groups_cas = int(grp_cas.gt(1).sum())
    dup_groups_cs = int(grp_cs.gt(1).sum())

    if dup_groups_cas > 0:
        warnings.append(f"consumos duplicate Codigo+Articulo+Sucursal groups: {dup_groups_cas}")

    multi_articulo_cs = int(df.groupby(["Codigo", "Sucursal"])["Articulo"].nunique(dropna=False).gt(1).sum())
    if multi_articulo_cs > 0:
        warnings.append(f"consumos Codigo+Sucursal mapped to multiple Articulo: {multi_articulo_cs}")

    expected = _parse_expected_sucursales(expected_sucursales)
    if expected:
        missing, extra = _missing_expected(df["Sucursal"], expected)
        if missing:
            errors.append("consumos missing expected sucursales: " + ", ".join(missing))
        if extra:
            warnings.append("consumos extra sucursales found: " + ", ".join(extra))

    metrics = {
        "consumos_rows": int(len(df)),
        "consumos_unique_codigo_articulo_sucursal": int(df[["Codigo", "Articulo", "Sucursal"]].drop_duplicates().shape[0]),
        "consumos_dup_groups_codigo_articulo_sucursal": dup_groups_cas,
        "consumos_dup_groups_codigo_sucursal": dup_groups_cs,
        "consumos_multi_articulo_codigo_sucursal": multi_articulo_cs,
    }

    return AuditReport(ok=len(errors) == 0, errors=errors, warnings=warnings, metrics=metrics)


def run_pre_supabase_audit(
    df_tickets: pd.DataFrame,
    df_consumos: pd.DataFrame,
    expected_sucursales: List[str] | None = None,
) -> Dict[str, dict]:
    tickets_report = audit_tickets(df_tickets, expected_sucursales=expected_sucursales)
    consumos_report = audit_consumos(df_consumos, expected_sucursales=expected_sucursales)

    return {
        "ok": tickets_report.ok and consumos_report.ok,
        "tickets": tickets_report.to_dict(),
        "consumos": consumos_report.to_dict(),
    }


def print_audit_report(report: Dict[str, dict]) -> None:
    print("\n" + "=" * 72)
    print("PRE-SUPABASE AUDIT")
    print("=" * 72)
    print(f"OVERALL OK: {report.get('ok')}")

    for section in ["tickets", "consumos"]:
        data = report.get(section, {})
        print("\n" + "-" * 72)
        print(section.upper())
        print("-" * 72)
        print(f"OK: {data.get('ok')}")
        print("METRICS:")
        for k, v in (data.get("metrics") or {}).items():
            print(f"  - {k}: {v}")

        errs = data.get("errors") or []
        warns = data.get("warnings") or []

        if errs:
            print("ERRORS:")
            for err in errs:
                print(f"  - {err}")
        else:
            print("ERRORS: none")

        if warns:
            print("WARNINGS:")
            for warn in warns:
                print(f"  - {warn}")
        else:
            print("WARNINGS: none")
