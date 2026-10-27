"""
Consolida os CSVs de votação por seção eleitoral (TSE - Eleições 2026)
em uma tabela agregada única, pronta para os gráficos.

Saída: dados/agregado.parquet
"""
import duckdb, pathlib, time

BASE = pathlib.Path(__file__).parent
CSV = str(BASE / "csv" / "votacao_secao_2026_*.csv")
OUT = BASE / "dados"
OUT.mkdir(exist_ok=True)

TIPO = """
    CASE
        WHEN SQ_CANDIDATO = '-1' AND NM_VOTAVEL = 'VOTO BRANCO' THEN 'Branco'
        WHEN SQ_CANDIDATO = '-1' THEN 'Nulo'
        WHEN SQ_CANDIDATO = '-3' THEN 'Legenda'
        ELSE 'Candidato'
    END
"""

t0 = time.time()
con = duckdb.connect()
con.execute("SET threads=10")
con.execute("SET preserve_insertion_order=false")
con.execute("SET memory_limit='6GB'")
con.execute(f"SET temp_directory='{BASE}/.duck_tmp'")

src = f"""
    SELECT SG_UF, NM_UE, NM_MUNICIPIO, CD_CARGO, DS_CARGO, NR_TURNO,
           NR_VOTAVEL, NM_VOTAVEL, SQ_CANDIDATO,
           CAST(QT_VOTOS AS BIGINT) AS QT_VOTOS
    FROM read_csv('{CSV}', delim=';', header=true, encoding='latin-1',
                  all_varchar=true, filename=false)
"""

con.execute(f"""
CREATE OR REPLACE TABLE agg AS
WITH base AS MATERIALIZED (
    SELECT SG_UF, NM_UE, NM_MUNICIPIO, CD_CARGO, DS_CARGO, NR_TURNO,
           NR_VOTAVEL, NM_VOTAVEL, SQ_CANDIDATO, QT_VOTOS,
           {TIPO} AS tipo
    FROM ({src})
)
SELECT 'uf/cargo' AS nivel, SG_UF, NM_UE,
       CAST(NULL AS VARCHAR) AS NM_MUNICIPIO, CD_CARGO, DS_CARGO, NR_TURNO, tipo,
       CAST(NULL AS VARCHAR) AS NR_VOTAVEL, CAST(NULL AS VARCHAR) AS NM_VOTAVEL,
       CAST(NULL AS VARCHAR) AS SQ_CANDIDATO, SUM(QT_VOTOS) AS QT_VOTOS
FROM base GROUP BY ALL
UNION ALL
SELECT 'municipio', SG_UF, NM_UE, NM_MUNICIPIO, CD_CARGO, DS_CARGO, NR_TURNO, tipo,
       NULL, NULL, NULL, SUM(QT_VOTOS)
FROM base GROUP BY ALL
UNION ALL
SELECT 'candidato', SG_UF, NM_UE, CAST(NULL AS VARCHAR), CD_CARGO, DS_CARGO, NR_TURNO, tipo,
       NR_VOTAVEL, NM_VOTAVEL, SQ_CANDIDATO, SUM(QT_VOTOS)
FROM base GROUP BY ALL
""")

con.execute(f"COPY agg TO '{(OUT / 'agregado.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")

print(con.execute("SELECT nivel, count(*) linhas, SUM(QT_VOTOS) votos FROM agg GROUP BY 1 ORDER BY 1").df().to_string(index=False))
print(con.execute("SELECT tipo, SUM(QT_VOTOS) votos FROM agg WHERE nivel='uf/cargo' GROUP BY 1 ORDER BY 2 DESC").df().to_string(index=False))
print(con.execute("SELECT NR_TURNO, DS_CARGO, SUM(QT_VOTOS) v FROM agg WHERE nivel='uf/cargo' GROUP BY ALL ORDER BY 1,2").df().to_string(index=False))
print(f"\ntempo: {time.time()-t0:.1f}s")
print("arquivo:", (OUT / 'agregado.parquet').stat().st_size / 1e6, "MB")
