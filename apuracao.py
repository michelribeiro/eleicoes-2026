"""
Reconstrói a apuração do 2º turno presidencial minuto a minuto (Lula x Flávio)
e desenha o gráfico da virada.

A base "votação por seção" só tem o resultado final. O horário de cada urna vem
de outro arquivo do TSE, o "Detalhe da apuração por seção eleitoral"
(DT_RECEBIMENTO_BU_HOR_TSE). Cruzando os dois pelo endereço da seção
(UF + município + zona + seção) sai a evolução da contagem ao longo da noite.

Uso:
    ./.venv/bin/python apuracao.py            # usa o cache / baixa o que faltar
    ./.venv/bin/python apuracao.py --forcar   # refaz o cruzamento

Saídas:
    dados/apuracao_presidente_2026.csv
    graficos/13_apuracao_presidente.png
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
CACHE = pathlib.Path(os.environ.get("TSE_CACHE", BASE / ".cache"))
SERIE = DADOS / "apuracao_presidente_2026.csv"

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
FONTES = {
    "votacao_secao_2026_BR.zip": f"{CDN}/votacao_secao/votacao_secao_2026_BR.zip",
    "detalhe_votacao_secao_2026.zip": f"{CDN}/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip",
}
VOTOS = "votacao_secao_2026_BR.csv"
DETALHE = "detalhe_votacao_secao_2026_BRASIL.csv"


# ---------------------------------------------------------------- ingestão
def baixar(nome, url):
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / nome
    if destino.exists():
        return destino
    print(f"baixando {nome} (~{ '230' } MB)…", flush=True)
    with urllib.request.urlopen(url) as r, open(destino, "wb") as f:
        while bloco := r.read(1 << 20):
            f.write(bloco)
    return destino


def garantir_zips():
    for nome, url in FONTES.items():
        z = baixar(nome, url)
        alvo = CACHE / (VOTOS if "votacao_secao" in nome else DETALHE)
        if not alvo.exists():
            print(f"extraindo {nome}…", flush=True)
            with zipfile.ZipFile(z) as zf:
                membros = [m for m in zf.namelist() if m.endswith(".csv")]
                for m in membros:
                    if m.endswith(("_BR.csv", "_BRASIL.csv")):
                        zf.extract(m, CACHE)


def montar_serie():
    garantir_zips()
    t0 = time.time()
    con = duckdb.connect()
    con.execute("SET threads=10")
    con.execute("SET memory_limit='6GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{CACHE}/duck_tmp'")

    v = (f"(select * from read_csv('{(CACHE / VOTOS).as_posix()}', delim=';', header=true, "
         f"encoding='latin-1', all_varchar=true))")
    d = (f"(select * from read_csv('{(CACHE / DETALHE).as_posix()}', delim=';', header=true, "
         f"encoding='latin-1', all_varchar=true))")

    # 1 voto por urna/candidato; o horário vem do detalhe da apuração (1 por seção)
    con.execute(f"""
        CREATE OR REPLACE TABLE sec AS
        SELECT v.SG_UF uf, v.CD_MUNICIPIO mun, v.NR_ZONA zona, v.NR_SECAO secao,
               v.NM_VOTAVEL nome, v.SQ_CANDIDATO sq, CAST(v.QT_VOTOS AS BIGINT) votos,
               strptime(t.DT_RECEBIMENTO_BU_HOR_TSE, '%d/%m/%Y %H:%M:%S') ts
        FROM {v} v
        JOIN (SELECT SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, DT_RECEBIMENTO_BU_HOR_TSE
              FROM {d} WHERE CD_CARGO = '1' AND NR_TURNO = '2') t
          ON t.SG_UF = v.SG_UF AND t.CD_MUNICIPIO = v.CD_MUNICIPIO
         AND t.NR_ZONA = v.NR_ZONA AND t.NR_SECAO = v.NR_SECAO
        WHERE v.CD_CARGO = '1' AND v.NR_TURNO = '2'
    """)

    serie = con.execute("""
        WITH urna AS (
            SELECT uf, mun, zona, secao, ts,
                   SUM(CASE WHEN nome LIKE 'LUIZ%LULA%' THEN votos ELSE 0 END) lula,
                   SUM(CASE WHEN nome LIKE 'FLAVIO%'      THEN votos ELSE 0 END) flavio,
                   SUM(CASE WHEN sq <> '-1' THEN votos ELSE 0 END) validos
            FROM sec GROUP BY ALL
        ), por_minuto AS (
            SELECT date_trunc('minute', ts) AS minuto,
                   SUM(lula) lula, SUM(flavio) flavio, SUM(validos) validos,
                   COUNT(*) urnas
            FROM urna GROUP BY 1
        )
        SELECT strftime(minuto, '%Y-%m-%d %H:%M') AS hora,
               SUM(lula)    OVER (ORDER BY minuto) AS votos_lula,
               SUM(flavio)  OVER (ORDER BY minuto) AS votos_flavio,
               SUM(validos) OVER (ORDER BY minuto) AS votos_validos,
               SUM(urnas)   OVER (ORDER BY minuto) AS urnas
        FROM por_minuto ORDER BY minuto
    """).df()

    serie["pct_lula"] = serie.votos_lula / serie.votos_validos * 100
    serie["pct_flavio"] = serie.votos_flavio / serie.votos_validos * 100
    serie["pct_urnas"] = serie.urnas / serie.urnas.iloc[-1] * 100
    SERIE.parent.mkdir(exist_ok=True)
    serie.to_csv(SERIE, index=False, float_format="%.6f")
    print(f"série salva em {SERIE.relative_to(BASE)} · {len(serie)} minutos · "
          f"{time.time() - t0:.0f}s")
    return serie


# ---------------------------------------------------------------- desenho
PAPER, INK, INK_SOFT, HAIR, CINZA = "#FAF7F1", "#1A2129", "#5D6673", "#E5DCCC", "#9AA1AB"
RUST, INDIGO, TEAL = "#C2543D", "#4A5C82", "#2F6F6B"

plt.rcParams.update({
    "font.family": "Avenir Next", "font.size": 10, "text.color": INK,
    "axes.labelcolor": INK_SOFT, "axes.edgecolor": HAIR,
    "xtick.color": INK_SOFT, "ytick.color": INK_SOFT,
    "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER,
    "figure.dpi": 200,
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

    fig = plt.figure(figsize=(13.6, 7.9))
    H = fig.get_figheight()
    fig.text(0.03, 1 - 0.42 / H, "A virada do 2º turno, urna por urna",
             fontsize=20, weight="demi", color=INK, va="top")
    fig.text(0.03, 1 - 0.84 / H,
             "Percentual dos votos válidos para presidente conforme as urnas chegam ao TSE · "
             "25 de outubro de 2026 · 499.205 urnas e 124.082.273 votos válidos",
             fontsize=10.2, color=INK_SOFT, va="top")
    fig.text(0.03, 0.14 / H,
             "Fonte: TSE · Dados Abertos · votação por seção eleitoral + detalhe da apuração "
             "(DT_RECEBIMENTO_BU_HOR_TSE) · 499.205 urnas cruzadas por UF, município, zona e seção",
             fontsize=7.6, color=CINZA, va="bottom")

    ax = fig.add_axes([0.065, 0.235, 0.885, 0.53])
    ax_ritmo = fig.add_axes([0.065, 0.105, 0.885, 0.085], sharex=ax)

    x0 = pd.Timestamp("2026-10-25 17:00")
    x1 = pd.Timestamp("2026-10-26 00:25")

    # faixa de quem lidera
    ax.fill_between(x, s.pct_lula, s.pct_flavio, where=s.pct_lula >= s.pct_flavio,
                    color=RUST, alpha=0.07, interpolate=True, zorder=1)
    ax.fill_between(x, s.pct_lula, s.pct_flavio, where=s.pct_lula < s.pct_flavio,
                    color=INDIGO, alpha=0.09, interpolate=True, zorder=1)

    ax.plot(x, s.pct_lula, color=RUST, lw=2.6, zorder=4, solid_capstyle="round")
    ax.plot(x, s.pct_flavio, color=INDIGO, lw=2.6, zorder=4, solid_capstyle="round")
    ax.axhline(50, color=HAIR, lw=1.1, zorder=2)

    # cruzamentos
    d = (s.pct_lula - s.pct_flavio).values
    cruzes = [i for i in range(1, len(d)) if np.sign(d[i]) != np.sign(d[i - 1])]
    for i in cruzes:
        t = s.t.iloc[i]
        sobe = d[i] > d[i - 1]  # Lula passou à frente
        ax.axvline(t, color=INK, lw=1, ls=(0, (4, 3)), zorder=3)
        y = s.pct_lula.iloc[i]
        ax.annotate(f"{t:%Hh%M}".replace("h0", "h"),
                    xy=(t, 57.6), ha="center", va="bottom", fontsize=9.6,
                    weight="demi", color=INK,
                    bbox=dict(boxstyle="round,pad=0.3", fc="#FBF8F2", ec=HAIR, lw=0.7))
        txt = ("Lula retoma a liderança\ne não perde mais"
               if sobe else "Flávio passa à frente,\npuxado por SP e pelo Sul")
        ax.annotate(txt, xy=(t, y), xytext=(18, 100) if sobe else (12, 56),
                    textcoords="offset points", fontsize=9.2, color=INK, linespacing=1.4,
                    ha="left", weight="demi",
                    arrowprops=dict(arrowstyle="-", color="#D8CFC0", lw=0.9))

    # primeira leitura
    ax.annotate(f"1ª leitura, {s.t.iloc[0]:%Hh%M}: Lula {n(s.pct_lula.iloc[0], 1)}%\n"
                f"com só {compacto(s.urnas.iloc[0])} urnas, quase todas do exterior",
                xy=(s.t.iloc[0], s.pct_lula.iloc[0]), xytext=(30, -18),
                textcoords="offset points", fontsize=8.6, color=INK_SOFT, linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color="#D8CFC0", lw=1))

    # buraco entre 17h e 19h
    ini, fim = pd.Timestamp("2026-10-25 17:08"), pd.Timestamp("2026-10-25 19:02")
    ax.axvspan(ini, fim, color="#EFE8DA", alpha=0.55, zorder=0)
    ax.text(ini + (fim - ini) / 2, 56.6, "sem novas urnas\naté 19h02",
            ha="center", va="bottom", fontsize=8, color=CINZA, linespacing=1.35)

    # rótulos finais
    ax.plot([x[-1]], [s.pct_lula.iloc[-1]], "o", color=RUST, ms=6, zorder=5)
    ax.text(x[-1] + pd.Timedelta(minutes=10), s.pct_lula.iloc[-1],
            f"Lula  {n(s.pct_lula.iloc[-1], 2)}%", fontsize=11.5, weight="demi", color=RUST,
            va="center")
    ax.text(x[-1] + pd.Timedelta(minutes=10), s.pct_lula.iloc[-1] - 0.85,
            f"{n(s.votos_lula.iloc[-1])} votos", fontsize=8.6, color=INK_SOFT, va="center")
    ax.plot([x[-1]], [s.pct_flavio.iloc[-1]], "o", color=INDIGO, ms=6, zorder=5)
    ax.text(x[-1] + pd.Timedelta(minutes=10), s.pct_flavio.iloc[-1],
            f"Flávio  {n(s.pct_flavio.iloc[-1], 2)}%", fontsize=11.5, weight="demi",
            color=INDIGO, va="center")
    ax.text(x[-1] + pd.Timedelta(minutes=10), s.pct_flavio.iloc[-1] - 0.85,
            f"{n(s.votos_flavio.iloc[-1])} votos", fontsize=8.6, color=INK_SOFT, va="center")

    # margem final
    ax.annotate("", xy=(x[-1], s.pct_lula.iloc[-1]), xytext=(x[-1], s.pct_flavio.iloc[-1]),
                arrowprops=dict(arrowstyle="<->", color=INK_SOFT, lw=0.9, shrinkA=0, shrinkB=0))
    ax.text(pd.Timestamp("2026-10-25 22:15"), 50.2,
            f"margem final\n{n(s.pct_lula.iloc[-1] - s.pct_flavio.iloc[-1], 2)} p.p.",
            fontsize=8.6, color=INK_SOFT, ha="right", va="bottom", linespacing=1.35)

    ax.set_xlim(x0, x1)
    ax.set_ylim(46, 59.6)
    ax.set_yticks(range(46, 60, 2))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.0f}%"))
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(17, 24)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Hh"))
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(HAIR)
    ax.tick_params(length=0)
    ax.yaxis.grid(True, color=HAIR, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("% dos votos válidos apurados", fontsize=9)

    # eixo de cima: quanto da apuração já entrou
    ax_top = ax.twiny()
    ax_top.set_xlim(ax.get_xlim())
    marcos = [(p, s.t.iloc[int((s.pct_urnas.values >= p).argmax())]) for p in (5, 25, 50, 75, 90)]
    ax_top.set_xticks([t for _, t in marcos])
    ax_top.set_xticklabels([f"{p}%" for p, _ in marcos], fontsize=8.6)
    ax_top.tick_params(length=0, colors=CINZA)
    for lado in ("top", "right", "left", "bottom"):
        ax_top.spines[lado].set_visible(False)
    ax_top.set_xlabel("urnas já apuradas (%)", fontsize=8.6, color=CINZA, labelpad=6)

    # painel do ritmo
    ax_ritmo.fill_between(x, s.pct_urnas, color=TEAL, alpha=0.16, zorder=2, lw=0)
    ax_ritmo.plot(x, s.pct_urnas, color=TEAL, lw=1.6, zorder=3)
    ax_ritmo.set_ylim(0, 108)
    ax_ritmo.set_yticks([0, 50, 100])
    ax_ritmo.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.0f}%"))
    ax_ritmo.tick_params(labelsize=8, length=0)
    for lado in ("top", "right", "left"):
        ax_ritmo.spines[lado].set_visible(False)
    ax_ritmo.spines["bottom"].set_color(HAIR)
    ax_ritmo.xaxis.set_major_formatter(mdates.DateFormatter("%Hh"))
    ax_ritmo.set_xlabel("horário de recebimento da urna no TSE", fontsize=9, labelpad=6)
    ax_ritmo.yaxis.grid(True, color=HAIR, lw=0.8)
    ax_ritmo.set_axisbelow(True)
    ax_ritmo.set_ylabel("urnas\napuradas", fontsize=8, color=INK_SOFT)
    i90 = (s.pct_urnas >= 90).idxmax()
    ax_ritmo.annotate(f"90% das urnas às {s.t.iloc[i90]:%Hh%M}",
                      xy=(s.t.iloc[i90], s.pct_urnas.iloc[i90]), xytext=(16, -16),
                      textcoords="offset points", fontsize=8.6, color=TEAL, weight="demi",
                      arrowprops=dict(arrowstyle="-", color=TEAL, lw=0.8, alpha=0.5))

    OUT.mkdir(exist_ok=True)
    destino = OUT / "13_apuracao_presidente.png"
    fig.savefig(destino)
    plt.close(fig)
    print("gráfico:", destino.relative_to(BASE))

    # resumo no terminal
    print(f"\n1ª leitura  {s.t.iloc[0]:%H:%M}  Lula {s.pct_lula.iloc[0]:.2f}% x "
          f"Flávio {s.pct_flavio.iloc[0]:.2f}%  ({n(s.urnas.iloc[0])} urnas)")
    for i in cruzes:
        print(f"cruzamento  {s.t.iloc[i]:%H:%M}  urnas {s.pct_urnas.iloc[i]:.1f}%  "
              f"Lula {s.pct_lula.iloc[i]:.2f}% x Flávio {s.pct_flavio.iloc[i]:.2f}%")
    print(f"final       {s.t.iloc[-1]:%H:%M}  Lula {s.pct_lula.iloc[-1]:.2f}% "
          f"({n(s.votos_lula.iloc[-1])}) x Flávio {s.pct_flavio.iloc[-1]:.2f}% "
          f"({n(s.votos_flavio.iloc[-1])})  margem "
          f"{s.pct_lula.iloc[-1] - s.pct_flavio.iloc[-1]:.2f} p.p.")


if __name__ == "__main__":
    if "--forcar" in sys.argv or not SERIE.exists():
        serie = montar_serie()
    else:
        serie = pd.read_csv(SERIE)
        print(f"usando série existente ({len(serie)} minutos) — use --forcar para refazer")
    desenhar(serie)
