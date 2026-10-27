"""
Exporta recortes em CSV (além do parquet) para quem quiser abrir no Excel.

Uso: ./.venv/bin/python exportar.py
"""
import pathlib
import duckdb

BASE = pathlib.Path(__file__).parent
D = BASE / "dados"
con = duckdb.connect()
A = f"read_parquet('{(D / 'agregado.parquet').as_posix()}')"

exports = {
    "votos_por_uf_e_cargo.csv": f"""
        SELECT SG_UF AS uf, NM_UE AS estado, DS_CARGO AS cargo, NR_TURNO AS turno,
               tipo, SUM(QT_VOTOS) AS votos
        FROM {A} WHERE nivel = 'uf/cargo'
        GROUP BY ALL ORDER BY uf, turno, cargo, votos DESC""",
    "votos_por_municipio.csv": f"""
        SELECT SG_UF AS uf, NM_MUNICIPIO AS municipio, DS_CARGO AS cargo, NR_TURNO AS turno,
               tipo, SUM(QT_VOTOS) AS votos
        FROM {A} WHERE nivel = 'municipio'
        GROUP BY ALL ORDER BY uf, municipio, turno, cargo, votos DESC""",
    "votos_por_candidato.csv": f"""
        SELECT SG_UF AS uf, DS_CARGO AS cargo, NR_TURNO AS turno, SQ_CANDIDATO AS sq_candidato,
               NM_VOTAVEL AS nome, NR_VOTAVEL AS numero, tipo, SUM(QT_VOTOS) AS votos
        FROM {A} WHERE nivel = 'candidato'
        GROUP BY ALL ORDER BY cargo, turno, votos DESC""",
}

for nome, sql in exports.items():
    con.execute(f"COPY ({sql}) TO '{(D / nome).as_posix()}' (HEADER, DELIMITER ',')")
    print(nome, f"{(D / nome).stat().st_size / 1e6:.1f} MB")
