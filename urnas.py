"""
Gráfico 14 — a apuração pelo HORÁRIO DE FECHAMENTO de cada urna.

Enquanto o gráfico 13 ordena as urnas pela hora em que o arquivo chegou ao TSE
(transmissão), este ordena pela hora em que a urna fechou (DT_ENCERRAMENTO, do
Boletim de Urna). É o mais perto que o dado público chega de "votos depois das 17h":
só urnas que fecharam com fila registraram voto depois do horário legal.

Fonte: dataset "Resultados - 2026 - Boletim de Urna" (28 arquivos, 1 por UF + exterior).

Uso:
    ./.venv/bin/python urnas.py            # usa o cache / baixa o que faltar
    ./.venv/bin/python urnas.py --forcar   # refaz o cruzamento dos BUs

Saídas:
    dados/urnas_fechamento_2026.parquet   1 linha por urna (fechamento, votos)
    dados/urnas_series_fechamento.csv     série cumulativa minuto a minuto
    graficos/14_urnas_fechamento.png
"""
import os
import pathlib
import sys
import time
import zipfile
import urllib.request

import duckdb
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

BASE = pathlib.Path(__file__).parent
DADOS = BASE / "dados"
OUT = BASE / "graficos"
CACHE = pathlib.Path(os.environ.get("TSE_CACHE", BASE / ".cache")) / "bu2"
SERIE = DADOS / "urnas_series_fechamento.csv"
URNAS = DADOS / "urnas_fechamento_2026.parquet"

CDN = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb"
UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ").split()
URL = "bweb_2t_{uf}_261020260742.zip"


# ---------------------------------------------------------------- ingestão
def baixar_bus():
    CACHE.mkdir(parents=True, exist_ok=True)
    for uf in UFS:
        destino = CACHE / URL.format(uf=uf)
        if destino.exists():
            continue
        print(f"baixando BU 2º turno {uf}…", flush=True)
        with urllib.request.urlopen(f"{CDN}/{URL.format(uf=uf)}") as r, open(destino, "wb") as f:
            while bloco := r.read(1 << 20):
                f.write(bloco)


def montar():
    baixar_bus()
    t0 = time.time()
    for z in CACHE.glob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            for m in zf.namelist():
                if m.endswith(".csv") and not (CACHE / m).exists():
                    zf.extract(m, CACHE)

    con = duckdb.connect()
    con.execute("SET threads=10")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{CACHE}/duck_tmp'")
    b = (f"(select * from read_csv('{(CACHE / '*.csv').as_posix()}', delim=';', header=true, "
         f"encoding='latin-1', all_varchar=true, union_by_name=true))")

    # 1 linha por urna; votos de presidente (Lula 13 / Flávio 22)
    con.execute(f"""
        CREATE OR REPLACE TABLE sec AS
        SELECT SG_UF uf, CD_MUNICIPIO mun, NM_MUNICIPIO nome_mun, NR_ZONA zona, NR_SECAO secao,
               MAX(strptime(DT_ENCERRAMENTO, '%Y-%m-%d %H:%M:%S')) fechamento,
               MAX(strptime(DT_BU_RECEBIDO, '%Y-%m-%d %H:%M:%S')) recebimento,
               SUM(CASE WHEN DS_CARGO_PERGUNTA = 'Presidente' AND DS_TIPO_VOTAVEL = 'Nominal'
                        THEN CAST(QT_VOTOS AS BIGINT) ELSE 0 END) validos,
               SUM(CASE WHEN DS_CARGO_PERGUNTA = 'Presidente' AND NR_VOTAVEL = '13'
                         AND DS_TIPO_VOTAVEL = 'Nominal' THEN CAST(QT_VOTOS AS BIGINT) ELSE 0 END) lula,
               SUM(CASE WHEN DS_CARGO_PERGUNTA = 'Presidente' AND NR_VOTAVEL = '22'
                         AND DS_TIPO_VOTAVEL = 'Nominal' THEN CAST(QT_VOTOS AS BIGINT) ELSE 0 END) flavio
        FROM {b}
        GROUP BY ALL
    """)

    # fuso por município, inferido do horário legal: as urnas que fecham na hora
    # marcam 17h em Brasília. 15h local = UTC-5 (AC, oeste do AM), 16h = UTC-4, etc.
    con.execute("""
        CREATE OR REPLACE TABLE fuso AS
        SELECT uf, mun,
               CAST(ROUND(17 - quantile_cont(
                   CAST(substr(strftime(fechamento, '%H:%M'), 1, 2) AS INT), 0.10)) AS INT) h
        FROM sec GROUP BY 1, 2
    """)
    con.execute("""
        CREATE OR REPLACE TABLE u AS
        SELECT s.*, f.h fuso,
               s.fechamento + to_hours(f.h) fech_brt,
               s.recebimento + to_hours(f.h) rec_brt
        FROM sec s LEFT JOIN fuso f USING (uf, mun)
    """)
    con.execute(f"COPY u TO '{(URNAS).as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    serie = con.execute("""
        WITH m AS (
            SELECT date_trunc('minute', fech_brt) minuto, COUNT(*) urnas,
                   SUM(validos) validos, SUM(lula) lula, SUM(flavio) flavio
            FROM u WHERE fech_brt >= '2026-10-25 17:00'
            GROUP BY 1
        )
        SELECT strftime(minuto, '%Y-%m-%d %H:%M') hora, urnas, validos, lula, flavio,
               SUM(urnas)   OVER (ORDER BY minuto) urnas_ac,
               SUM(validos) OVER (ORDER BY minuto) votos_ac,
               SUM(lula)    OVER (ORDER BY minuto) lula_ac,
               SUM(flavio)  OVER (ORDER BY minuto) flavio_ac
        FROM m ORDER BY minuto
    """).df()
    serie["pct_lula"] = serie.lula_ac / serie.votos_ac * 100
    serie["pct_flavio"] = serie.flavio_ac / serie.votos_ac * 100
    serie["pct_urnas"] = serie.urnas_ac / serie.urnas_ac.iloc[-1] * 100
    serie.to_csv(SERIE, index=False, float_format="%.6f")

    # o CSV extraído (1 GB) não precisa ficar: os zips continuam no cache
    for c in CACHE.glob("*.csv"):
        c.unlink()
    print(f"série salva ({len(serie)} minutos, {time.time() - t0:.0f}s)")
    return serie


# ---------------------------------------------------------------- desenho
PAPER, INK, INK_SOFT, HAIR, CINZA = "#FAF7F1", "#1A2129", "#5D6673", "#E5DCCC", "#9AA1AB"
RUST, INDIGO, TEAL = "#C2543D", "#4A5C82", "#2F6F6B"

plt.rcParams.update({
    "font.family": "Avenir Next", "font.size": 10, "text.color": INK,
    "axes.labelcolor": INK_SOFT, "axes.edgecolor": HAIR, "xtick.color": INK_SOFT,
    "ytick.color": INK_SOFT, "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER, "figure.dpi": 200,
})


def n(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def compacto(v):
    if abs(v) >= 1e6:
        c = f"{v/1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return c.replace(",0", "") + " mi"
    return f"{v/1e3:,.0f}".replace(",", ".") + " mil"


def desenhar(serie):
    s = serie.copy()
    s["t"] = pd.to_datetime(s.hora)
    x = s.t.values

    fig = plt.figure(figsize=(13.8, 7.9))
    H = fig.get_figheight()
    fig.text(0.03, 1 - 0.42 / H, "Quem estava na frente, urna por urna",
             fontsize=20, weight="demi", color=INK, va="top")
    fig.text(0.03, 1 - 0.84 / H,
             "Percentual dos votos válidos para presidente somando as urnas pela hora em que "
             "FECHARAM · 2º turno, 25/10/2026 · horário de Brasília · sem o exterior\n"
             "A votação termina às 19h59: depois disso só 2 urnas fecharam (20h e 23h04), com 309 votos",
             fontsize=10.2, color=INK_SOFT, va="top")
    fig.text(0.03, 0.14 / H,
             "Fonte: TSE · Dados Abertos · Boletim de Urna (DT_ENCERRAMENTO) · "
             f"{n(s.urnas_ac.iloc[-1])} urnas e {n(s.votos_ac.iloc[-1])} votos válidos · "
             "fuso do horário inferido por município",
             fontsize=7.6, color=CINZA, va="bottom")

    ax = fig.add_axes([0.072, 0.30, 0.355, 0.46])
    az = fig.add_axes([0.525, 0.30, 0.40, 0.46], sharey=ax)
    ax_ritmo = fig.add_axes([0.072, 0.165, 0.355, 0.075], sharex=ax)

    x0, x1 = pd.Timestamp("2026-10-25 17:00"), pd.Timestamp("2026-10-25 20:12")
    z1 = pd.Timestamp("2026-10-25 17:06")

    for a in (ax, az):
        a.fill_between(x, s.pct_lula, s.pct_flavio, where=s.pct_lula >= s.pct_flavio,
                       color=RUST, alpha=0.08, zorder=1)
        a.fill_between(x, s.pct_lula, s.pct_flavio, where=s.pct_lula < s.pct_flavio,
                       color=INDIGO, alpha=0.10, zorder=1)
        a.plot(x, s.pct_lula, color=RUST, lw=2.6, zorder=4, solid_capstyle="round")
        a.plot(x, s.pct_flavio, color=INDIGO, lw=2.6, zorder=4, solid_capstyle="round")
        a.axhline(50, color=HAIR, lw=1.1, zorder=2)
        a.set_ylim(47.85, 52.55)
        a.set_yticks([49, 50, 51, 52])
        a.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.0f}%"))
        for lado in ("top", "right", "left"):
            a.spines[lado].set_visible(False)
        a.spines["bottom"].set_color(HAIR)
        a.tick_params(length=0)
        a.yaxis.grid(True, color=HAIR, lw=0.8)
        a.set_axisbelow(True)

    ax.set_xlim(x0, x1)
    ax.set_ylabel("% dos votos válidos já apurados", fontsize=9)
    ax.set_xticks([pd.Timestamp(f"2026-10-25 {h}:00") for h in range(17, 21)])
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Hh"))
    ax.tick_params(labelbottom=False)
    ax.set_title("a votação inteira · 17h a 19h59", fontsize=10, color=INK_SOFT,
                 loc="left", pad=8)
    ax.annotate("as duas linhas se cruzam\nno primeiro minuto",
                xy=(pd.Timestamp("2026-10-25 17:02"), 50.4),
                xytext=(pd.Timestamp("2026-10-25 17:45"), 49.2),
                fontsize=8.8, color=INK, linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color="#D8CFC0", lw=1))
    ax.text(pd.Timestamp("2026-10-25 19:55"), s.pct_lula.iloc[-1] + 0.28,
            f"Lula {n(s.pct_lula.iloc[-1], 2)}%", fontsize=9.4, weight="demi", color=RUST,
            ha="right")
    ax.text(pd.Timestamp("2026-10-25 19:55"), s.pct_flavio.iloc[-1] - 0.38,
            f"Flávio {n(s.pct_flavio.iloc[-1], 2)}%", fontsize=9.4, weight="demi", color=INDIGO,
            ha="right")

    # ---- painel da direita: os primeiros 6 minutos, onde tudo acontece
    az.set_xlim(x0, z1)
    az.set_xticks([pd.Timestamp(f"2026-10-25 17:0{m}") for m in range(0, 7)])
    az.xaxis.set_major_formatter(mdates.DateFormatter("%Hh%M"))
    az.set_title("zoom · 17h00 a 17h06 (96% das urnas fecham aqui)",
                 fontsize=10, color=INK_SOFT, loc="left", pad=8)
    az.tick_params(labelleft=False)

    d = (s.pct_lula - s.pct_flavio).values
    cruz = [i for i in range(1, len(d)) if np.sign(d[i]) != np.sign(d[i - 1])]
    for i in cruz:
        t = s.t.iloc[i]
        for a in (ax, az):
            a.axvline(t, color=INK, lw=1, ls=(0, (4, 3)), zorder=3)
    i0 = cruz[0] if cruz else 0
    az.annotate(f"{s.t.iloc[i0]:%Hh%M} · Lula passa à frente\n"
                f"{n(s.pct_lula.iloc[i0], 2)}% x {n(s.pct_flavio.iloc[i0], 2)}%",
                xy=(s.t.iloc[i0], 50.05), xytext=(pd.Timestamp("2026-10-25 17:01:30"), 51.9),
                fontsize=9, weight="demi", color=INK, va="top",
                arrowprops=dict(arrowstyle="-", color="#D8CFC0", lw=0.9))

    ult = s[s.t <= z1].iloc[-1]
    az.plot([ult.t], [ult.pct_lula], "o", color=RUST, ms=5, zorder=5)
    az.text(ult.t, ult.pct_lula + 0.22, f"Lula {n(ult.pct_lula, 2)}%", fontsize=9,
            weight="demi", color=RUST, ha="right")
    az.text(ult.t, ult.pct_flavio - 0.35, f"Flávio {n(ult.pct_flavio, 2)}%", fontsize=9,
            weight="demi", color=INDIGO, ha="right")

    # ---- faixa de ritmo: urnas fechando
    ax_ritmo.fill_between(x, s.pct_urnas, color=TEAL, alpha=0.16, lw=0, zorder=2)
    ax_ritmo.plot(x, s.pct_urnas, color=TEAL, lw=1.6, zorder=3)
    ax_ritmo.set_ylim(0, 108)
    ax_ritmo.set_yticks([0, 50, 100])
    ax_ritmo.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.0f}%"))
    ax_ritmo.tick_params(labelsize=8, length=0)
    for lado in ("top", "right", "left"):
        ax_ritmo.spines[lado].set_visible(False)
    ax_ritmo.spines["bottom"].set_color(HAIR)
    ax_ritmo.set_xlabel("horário de fechamento da urna (Brasília)", fontsize=8.6, labelpad=4)
    ax_ritmo.tick_params(axis="x", labelsize=8)
    ax_ritmo.yaxis.grid(True, color=HAIR, lw=0.8)
    ax_ritmo.set_axisbelow(True)
    ax_ritmo.set_ylabel("urnas\nfechadas", fontsize=8, color=INK_SOFT)
    ax_ritmo.annotate("89% das urnas já fecharam às 17h04",
                      xy=(pd.Timestamp("2026-10-25 17:05"), 89), xytext=(10, -16),
                      textcoords="offset points", fontsize=8.2, color=TEAL, weight="demi")

    OUT.mkdir(exist_ok=True)
    destino = OUT / "14_urnas_fechamento.png"
    fig.savefig(destino)
    plt.close(fig)
    print("gráfico:", destino.relative_to(BASE))

    print(f"\n17h00  Flávio {s.pct_flavio.iloc[0]:.2f}% x Lula {s.pct_lula.iloc[0]:.2f}% "
          f"({n(s.urnas.iloc[0])} urnas)")
    for i in cruz:
        print(f"virada {s.t.iloc[i]:%H:%M}  Lula {s.pct_lula.iloc[i]:.2f}% x "
              f"Flávio {s.pct_flavio.iloc[i]:.2f}%")
    print(f"fim    {s.t.iloc[-1]:%H:%M}  Lula {s.pct_lula.iloc[-1]:.2f}% "
          f"({n(s.lula_ac.iloc[-1])}) x Flávio {s.pct_flavio.iloc[-1]:.2f}% "
          f"({n(s.flavio_ac.iloc[-1])})")


if __name__ == "__main__":
    if "--forcar" in sys.argv or not SERIE.exists():
        serie = montar()
    else:
        serie = pd.read_csv(SERIE)
        print(f"usando série existente ({len(serie)} minutos) — use --forcar para refazer")
    desenhar(serie)
