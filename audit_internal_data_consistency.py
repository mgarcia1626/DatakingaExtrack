import sqlite3
from pathlib import Path


DB_PATH = Path('DataBase/datakinga.db')


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def get_columns(cur, table: str):
    return [r[1] for r in cur.execute(f"pragma table_info({table})").fetchall()]


def ticket_colnames(cols):
    num = next((c for c in cols if 'mero' in c.lower()), None)
    cod = next((c for c in cols if 'digo' in c.lower()), None)
    suc = next((c for c in cols if 'sucursal' in c.lower()), None)
    return num, cod, suc


def count_rows(cur, table: str) -> int:
    return cur.execute(f"select count(*) from {table}").fetchone()[0]


def scalar(cur, sql: str, params=()):
    return cur.execute(sql, params).fetchone()[0]


def top_rows(cur, sql: str, limit: int = 10):
    return cur.execute(sql + f" limit {limit}").fetchall()


def audit_tickets(cur):
    cols = get_columns(cur, 'tickets_detalle')
    num_col, cod_col, suc_col = ticket_colnames(cols)

    if not num_col or not cod_col:
        return {'error': 'Could not infer Numero/Codigo columns.'}

    qn = qident(num_col)
    qc = qident(cod_col)
    qs = qident(suc_col) if suc_col else None

    null_num = scalar(cur, f"select count(*) from tickets_detalle where {qn} is null or trim(cast({qn} as text))='' ")
    null_cod = scalar(cur, f"select count(*) from tickets_detalle where {qc} is null or trim(cast({qc} as text))='' ")

    dup_groups_num_cod = scalar(cur, f"""
        select count(*) from (
            select {qn}, {qc}, count(*) c
            from tickets_detalle
            group by {qn}, {qc}
            having c > 1
        )
    """)
    dup_extra_num_cod = scalar(cur, f"""
        select coalesce(sum(c - 1), 0) from (
            select count(*) c
            from tickets_detalle
            group by {qn}, {qc}
            having c > 1
        )
    """)

    dup_groups_num_cod_suc = 0
    dup_extra_num_cod_suc = 0
    if qs:
        dup_groups_num_cod_suc = scalar(cur, f"""
            select count(*) from (
                select {qn}, {qc}, {qs}, count(*) c
                from tickets_detalle
                group by {qn}, {qc}, {qs}
                having c > 1
            )
        """)
        dup_extra_num_cod_suc = scalar(cur, f"""
            select coalesce(sum(c - 1), 0) from (
                select count(*) c
                from tickets_detalle
                group by {qn}, {qc}, {qs}
                having c > 1
            )
        """)

    other_cols = [c for c in cols if c not in (num_col, cod_col)]
    payload_expr = " || '|' || ".join([f"ifnull(cast({qident(c)} as text),'')" for c in other_cols])

    conflicting_groups = scalar(cur, f"""
        select count(*) from (
            select {qn}, {qc}, count(*) total_rows, count(distinct {payload_expr}) payloads
            from tickets_detalle
            group by {qn}, {qc}
            having total_rows > 1 and payloads > 1
        )
    """)

    top_dup = top_rows(cur, f"""
        select {qn} as numero, {qc} as codigo, count(*) c
        from tickets_detalle
        group by {qn}, {qc}
        having c > 1
        order by c desc
    """)

    return {
        'columns': {'numero': num_col, 'codigo': cod_col, 'sucursal': suc_col},
        'null_numero': null_num,
        'null_codigo': null_cod,
        'dup_groups_numero_codigo': dup_groups_num_cod,
        'dup_extra_numero_codigo': dup_extra_num_cod,
        'dup_groups_numero_codigo_sucursal': dup_groups_num_cod_suc,
        'dup_extra_numero_codigo_sucursal': dup_extra_num_cod_suc,
        'conflicting_groups_numero_codigo': conflicting_groups,
        'top_duplicate_keys': top_dup,
    }


def audit_consumos(cur):
    cols = get_columns(cur, 'consumos')
    required = {'Codigo', 'Articulo', 'Sucursal'}
    if not required.issubset(set(cols)):
        return {'error': 'Expected columns Codigo, Articulo, Sucursal were not found.'}

    dup_groups_cas = scalar(cur, """
        select count(*) from (
            select Codigo, Articulo, Sucursal, count(*) c
            from consumos
            group by Codigo, Articulo, Sucursal
            having c > 1
        )
    """)
    dup_extra_cas = scalar(cur, """
        select coalesce(sum(c - 1), 0) from (
            select count(*) c
            from consumos
            group by Codigo, Articulo, Sucursal
            having c > 1
        )
    """)

    dup_groups_cs = scalar(cur, """
        select count(*) from (
            select Codigo, Sucursal, count(*) c
            from consumos
            group by Codigo, Sucursal
            having c > 1
        )
    """)

    multi_articulo_cs = scalar(cur, """
        select count(*) from (
            select Codigo, Sucursal, count(distinct Articulo) a
            from consumos
            group by Codigo, Sucursal
            having a > 1
        )
    """)

    top_multi = top_rows(cur, """
        select Codigo, Sucursal, count(distinct Articulo) articulos, count(*) filas
        from consumos
        group by Codigo, Sucursal
        having articulos > 1
        order by articulos desc, filas desc
    """)

    return {
        'dup_groups_codigo_articulo_sucursal': dup_groups_cas,
        'dup_extra_codigo_articulo_sucursal': dup_extra_cas,
        'dup_groups_codigo_sucursal': dup_groups_cs,
        'multi_articulo_codigo_sucursal': multi_articulo_cs,
        'top_codigo_sucursal_multi_articulo': top_multi,
    }


def main():
    print('=' * 72)
    print('DATA AUDIT - INTERNAL CONSISTENCY')
    print('=' * 72)
    print(f'Database: {DB_PATH}')

    if not DB_PATH.exists():
        print('ERROR: Database file not found.')
        return 1

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table' order by name")]
        print('Tables:', tables)

        print('\n[1] Row counts')
        if 'tickets_detalle' in tables:
            print('tickets_detalle:', count_rows(cur, 'tickets_detalle'))
        if 'consumos' in tables:
            print('consumos:', count_rows(cur, 'consumos'))

        if 'tickets_detalle' in tables:
            t = audit_tickets(cur)
            print('\n[2] Tickets audit')
            if 'error' in t:
                print('ERROR:', t['error'])
            else:
                print('Numero column:', t['columns']['numero'])
                print('Codigo column:', t['columns']['codigo'])
                print('Sucursal column:', t['columns']['sucursal'])
                print('Null Numero:', t['null_numero'])
                print('Null Codigo:', t['null_codigo'])
                print('Duplicate groups Numero+Codigo:', t['dup_groups_numero_codigo'])
                print('Duplicate extra rows Numero+Codigo:', t['dup_extra_numero_codigo'])
                print('Duplicate groups Numero+Codigo+Sucursal:', t['dup_groups_numero_codigo_sucursal'])
                print('Duplicate extra rows Numero+Codigo+Sucursal:', t['dup_extra_numero_codigo_sucursal'])
                print('Conflicting duplicate groups (same Numero+Codigo, different payload):', t['conflicting_groups_numero_codigo'])
                print('Top duplicated keys (Numero, Codigo, Count):')
                for row in t['top_duplicate_keys']:
                    print(' ', row)

        if 'consumos' in tables:
            c = audit_consumos(cur)
            print('\n[3] Consumos audit')
            if 'error' in c:
                print('ERROR:', c['error'])
            else:
                print('Duplicate groups Codigo+Articulo+Sucursal:', c['dup_groups_codigo_articulo_sucursal'])
                print('Duplicate extra rows Codigo+Articulo+Sucursal:', c['dup_extra_codigo_articulo_sucursal'])
                print('Duplicate groups Codigo+Sucursal:', c['dup_groups_codigo_sucursal'])
                print('Codigo+Sucursal with multiple Articulo values:', c['multi_articulo_codigo_sucursal'])
                print('Top Codigo+Sucursal with multiple Articulo values:')
                for row in c['top_codigo_sucursal_multi_articulo']:
                    print(' ', row)

        print('\n[4] Suggested checks')
        print('- Verify dedup key in tickets includes enough fields (at least Numero, Codigo, Sucursal, Fecha, Hora).')
        print('- Align consumos upsert key with DB unique index.')
        print('- Add DB constraints in SQLite to prevent silent duplicate accumulation.')
        print('- Add per-run reconciliation metrics: extracted rows, inserted rows, updated rows, skipped rows.')

    finally:
        conn.close()

    print('\nAudit finished.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
