"""
Gera os gráficos do relatório (PNG) a partir de dados/agregado.parquet.

Uso: ./.venv/bin/python graficos.py
"""
import json
import pathlib

import duckdb
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.ticker import FuncFormatter

BASE = pathlib.Path(__file__).parent
OUT = BASE / "graficos"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- estilo
PAPER = "#FAF7F1"
INK = "#1A2129"
INK_SOFT = "#5D6673"
HAIR = "#E5DCCC"
CINZA = "#9AA1AB"

REG = {"N": "#2F6F6B", "NE": "#C2543D", "CO": "#B08A3E", "SE": "#4A5C82", "S": "#8A8F5B"}
REG_NOME = {"N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul"}
UF_REG = {
    "AC": "N", "AM": "N", "AP": "N", "PA": "N", "RO": "N", "RR": "N", "TO": "N",
    "AL": "NE", "BA": "NE", "CE": "NE", "MA": "NE", "PB": "NE", "PE": "NE",
    "PI": "NE", "RN": "NE", "SE": "NE",
    "DF": "CO", "GO": "CO", "MT": "CO", "MS": "CO",
    "ES": "SE", "MG": "SE", "RJ": "SE", "SP": "SE",
    "PR": "S", "RS": "S", "SC": "S",
}
COD_UF = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
SIGLA_PARTIDO = {
    "PARTIDO DOS TRABALHADORES": "PT", "PARTIDO LIBERAL": "PL",
    "MOVIMENTO DEMOCRÁTICO BRASILEIRO": "MDB", "PROGRESSISTAS": "PP",
    "PARTIDO SOCIAL DEMOCRÁTICO": "PSD", "REPUBLICANOS": "REPUBLICANOS",
    "PARTIDO DEMOCRÁTICO TRABALHISTA": "PDT", "PARTIDO SOCIALISTA BRASILEIRO": "PSB",
    "UNIÃO BRASIL": "UNIÃO", "PARTIDO SOCIALISMO E LIBERDADE": "PSOL",
    "PARTIDO DA SOCIAL DEMOCRACIA BRASILEIRA": "PSDB", "REDE SUSTENTABILIDADE": "REDE",
    "PARTIDO NOVO": "NOVO", "PODEMOS": "PODEMOS", "PARTIDO MISSÃO": "MISSÃO",
    "PARTIDO COMUNISTA DO BRASIL": "PCdoB", "SOLIDARIEDADE": "SOLIDARIEDADE",
    "AVANTE": "AVANTE", "PARTIDO RENOVAÇÃO DEMOCRÁTICA": "PRD",
    "PARTIDO DA MOBILIZAÇÃO NACIONAL": "PMN", "AGIR": "AGIR",
    "DEMOCRACIA CRISTÃ": "DC", "PARTIDO VERDE": "PV", "CIDADANIA": "CIDADANIA",
}

plt.rcParams.update({
    "font.family": "Avenir Next",
    "font.size": 10,
    "text.color": INK,
    "axes.labelcolor": INK_SOFT,
    "axes.edgecolor": HAIR,
    "xtick.color": INK_SOFT,
    "ytick.color": INK_SOFT,
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "figure.dpi": 200,
})


# ---------------------------------------------------------------- helpers
def n(v, dec=0):
    if v is None:
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def compacto(v):
    if abs(v) >= 1e6:
        c = f"{v/1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return c.replace(",0", "") + " mi"
    if abs(v) >= 1e3:
        return f"{v/1e3:,.0f}".replace(",", ".") + " mil"
    return n(v)


MESCLAS = {"de", "da", "do", "das", "dos", "e", "d'", "di"}


def nome_proprio(s):
    partes = []
    for i, p in enumerate(str(s).lower().split()):
        partes.append(p if (p in MESCLAS and i > 0) else p[:1].upper() + p[1:])
    return " ".join(partes)


def sigla_partido(nome):
    return SIGLA_PARTIDO.get(str(nome).upper(), nome_proprio(nome))


def novo(titulo, sub, w, h):
    fig = plt.figure(figsize=(w, h))
    fig.text(0.035, 1 - 0.42 / h, titulo, fontsize=17, weight="demi", color=INK,
             ha="left", va="top")
    fig.text(0.035, 1 - 0.80 / h, sub, fontsize=10, color=INK_SOFT, ha="left", va="top",
             linespacing=1.5)
    fig.text(0.035, 0.16 / h,
             "Fonte: TSE · Dados Abertos · votação por seção eleitoral · Eleições 2026",
             fontsize=7.6, color=CINZA, ha="left", va="bottom")
    return fig


def fechar(fig, nome, cabecalho_altura=1.30, rodape=0.70):
    h = fig.get_figheight()
    fig.tight_layout(rect=[0.0, rodape / h, 1.0, 1 - cabecalho_altura / h])
    fig.savefig(OUT / nome)
    plt.close(fig)


def limpar(ax, grid="x"):
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(HAIR)
    ax.tick_params(length=0)
    if grid == "x":
        ax.xaxis.grid(True, color=HAIR, lw=0.8)
        ax.yaxis.grid(False)
    elif grid == "y":
        ax.yaxis.grid(True, color=HAIR, lw=0.8)
        ax.xaxis.grid(False)
    else:
        ax.grid(False)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- dados
con = duckdb.connect()
A = "read_parquet('dados/agregado.parquet')"
q = lambda s: con.execute(s).df()

T1 = "NR_TURNO = '1'"
VALIDO = "tipo IN ('Candidato', 'Legenda')"

uf = q(f"""
    SELECT SG_UF,
           SUM(QT_VOTOS) FILTER (WHERE tipo = 'Candidato') cand,
           SUM(QT_VOTOS) FILTER (WHERE tipo = 'Legenda') legenda,
           SUM(QT_VOTOS) FILTER (WHERE tipo = 'Branco') branco,
           SUM(QT_VOTOS) FILTER (WHERE tipo = 'Nulo') nulo,
           SUM(QT_VOTOS) FILTER ({VALIDO}) validos,
           SUM(QT_VOTOS) total
    FROM {A} WHERE nivel = 'uf/cargo' AND {T1}
    GROUP BY 1 ORDER BY validos DESC
""")
uf["regiao"] = uf.SG_UF.map(UF_REG)

gov = q(f"""
    SELECT SG_UF,
           SUM(QT_VOTOS) FILTER ({VALIDO}) validos,
           SUM(QT_VOTOS) total
    FROM {A} WHERE nivel = 'uf/cargo' AND {T1} AND DS_CARGO = 'Governador'
    GROUP BY 1 ORDER BY validos DESC
""")
gov["regiao"] = gov.SG_UF.map(UF_REG)

gov2 = q(f"""
    SELECT SG_UF, SUM(QT_VOTOS) FILTER ({VALIDO}) validos
    FROM {A} WHERE nivel = 'uf/cargo' AND NR_TURNO = '2' AND DS_CARGO = 'Governador'
    GROUP BY 1 ORDER BY 2 DESC
""")

cargos = q(f"""
    SELECT NR_TURNO, DS_CARGO, SUM(QT_VOTOS) FILTER ({VALIDO}) validos,
           SUM(QT_VOTOS) total
    FROM {A} WHERE nivel = 'uf/cargo' GROUP BY ALL ORDER BY 1, 3 DESC
""")

validos_cargo_turno = q(f"""
    SELECT DS_CARGO, NR_TURNO, SUM(QT_VOTOS) FILTER ({VALIDO}) validos
    FROM {A} WHERE nivel = 'uf/cargo' GROUP BY ALL
""").set_index(["DS_CARGO", "NR_TURNO"]).validos

# candidatos: nome + UF + votos + total do estado (para % dentro do estado)
cand = q(f"""
    SELECT SG_UF, DS_CARGO, NR_TURNO, SQ_CANDIDATO, MAX(NM_VOTAVEL) AS nome,
           SUM(QT_VOTOS) AS votos
    FROM {A} WHERE nivel = 'candidato' AND tipo = 'Candidato'
    GROUP BY SG_UF, DS_CARGO, NR_TURNO, SQ_CANDIDATO
""")
val_uf = q(f"""
    SELECT SG_UF, DS_CARGO, NR_TURNO, SUM(QT_VOTOS) FILTER ({VALIDO}) validos
    FROM {A} WHERE nivel = 'uf/cargo' GROUP BY ALL
""")
cand = cand.merge(val_uf, on=["SG_UF", "DS_CARGO", "NR_TURNO"])
cand["pct_uf"] = cand.votos / cand.validos * 100

legenda = q(f"""
    SELECT NM_VOTAVEL partido, SUM(QT_VOTOS) votos
    FROM {A} WHERE nivel = 'candidato' AND tipo = 'Legenda' AND {T1}
    GROUP BY 1 ORDER BY 2 DESC
""")

municipios = q(f"""
    SELECT SG_UF, NM_MUNICIPIO, SUM(QT_VOTOS) FILTER ({VALIDO}) validos
    FROM {A} WHERE nivel = 'municipio' AND {T1} AND DS_CARGO = 'Governador'
    GROUP BY ALL ORDER BY 3 DESC
""")

reg = (gov.groupby("regiao")[["validos", "total"]].sum().reindex(list(REG)).reset_index())
reg["share"] = reg.validos / reg.validos.sum() * 100
reg["pct_val"] = reg.validos / reg.total * 100

tot_validos = int(uf.validos.sum())
tot_total = int(uf.total.sum())
tot_branco = int(uf.branco.sum())
tot_nulo = int(uf.nulo.sum())
eleitores = int(gov.validos.sum())

# ---------------------------------------------------------------- 01 mapa
# rótulos absolutos (lon, lat) para os estados pequenos: pilha no oceano
ABS_LABEL = {
    "RN": (-30.6, -4.6), "PB": (-30.6, -6.6), "PE": (-30.6, -8.6),
    "AL": (-30.6, -10.6), "SE": (-30.6, -12.6),
}
DESLOC = {"DF": (-1.3, -0.9), "GO": (-0.9, 0.8), "ES": (1.0, -0.1), "RJ": (0.95, 0.25),
          "AP": (0.1, 0.4), "SC": (0.35, -0.2), "MS": (-0.2, -0.35), "SE2": (0, 0)}

cmap_map = LinearSegmentedColormap.from_list("tse", ["#F1E9DA", "#E3BCA4", "#C2543D", "#83321F"])


def desenha_mapa(ax, valores, norm, titulo):
    gj = json.load(open(BASE / "dados" / "br_ufs.geojson"))
    xs_all, ys_all = [], []
    for f in gj["features"]:
        sig = COD_UF.get(f["properties"]["codarea"])
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        anel, area_maior, centro = None, -1, (0, 0)
        for poly in polys:
            c = poly[0]
            xs = [p[0] for p in c]
            ys = [p[1] for p in c]
            xs_all += xs
            ys_all += ys
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if area > area_maior:
                area_maior, anel = area, c
                centro = (sum(xs) / len(xs), sum(ys) / len(ys))
        if anel is None:
            continue
        v = valores.get(sig, 0)
        ax.add_patch(mpatches.Polygon(anel, closed=True, facecolor=cmap_map(norm(v)),
                                      edgecolor=PAPER, lw=0.9, zorder=2))
        if sig in ABS_LABEL:
            ax.annotate(sig, xy=centro, xytext=ABS_LABEL[sig], ha="center", va="center",
                        fontsize=7, weight="demi", zorder=5, color=INK,
                        bbox=dict(boxstyle="round,pad=0.15", fc="#FBF8F2", ec="#DCD2C1",
                                  lw=0.6),
                        arrowprops=dict(arrowstyle="-", color="#C9BFAE", lw=0.7,
                                        shrinkA=2, shrinkB=3))
        else:
            dx, dy = DESLOC.get(sig, (0, 0))
            ax.text(centro[0] + dx, centro[1] + dy, sig, ha="center", va="center",
                    zorder=4, color="#FFFDF8" if norm(v) > 0.55 else INK,
                    fontsize=7, weight="demi")
    ax.set_xlim(min(xs_all) - 1.0, -28.6)
    ax.set_ylim(min(ys_all) - 1.0, max(ys_all) + 1.0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(titulo, fontsize=10.5, color=INK_SOFT, loc="left", pad=2)


def gradiente(fig, retangulo, norm, lo, hi, fmt=compacto):
    ax = fig.add_axes(retangulo)
    ax.imshow(np.linspace(0, 1, 256).reshape(1, -1), extent=[0, 1, 0, 1], aspect="auto",
              origin="lower", cmap=cmap_map)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.text(0, 1.8, fmt(lo), fontsize=7, color=INK_SOFT, ha="left", va="bottom")
    ax.text(1, 1.8, fmt(hi), fontsize=7, color=INK_SOFT, ha="right", va="bottom")


fig = plt.figure(figsize=(14.4, 7.6))
ax1 = fig.add_axes([0.015, 0.17, 0.46, 0.62])
ax2 = fig.add_axes([0.505, 0.17, 0.46, 0.62])

v_gov = dict(zip(gov.SG_UF, gov.validos))
norm1 = PowerNorm(0.45, vmin=min(v_gov.values()), vmax=max(v_gov.values()))
desenha_mapa(ax1, v_gov, norm1, "Votos válidos para Governador — 1º turno")
gradiente(fig, [0.035, 0.115, 0.15, 0.014], norm1, min(v_gov.values()), max(v_gov.values()))

bn = {r.SG_UF: (r.branco + r.nulo) / r.total * 100 for r in uf.itertuples()}
norm2 = PowerNorm(0.6, vmin=min(bn.values()), vmax=max(bn.values()))
desenha_mapa(ax2, bn, norm2, "Brancos + nulos — % dos votos depositados")
gradiente(fig, [0.525, 0.115, 0.15, 0.014], norm2, min(bn.values()), max(bn.values()),
          fmt=lambda v: f"{n(v,1)}%")
fig.text(0.72, 0.118, f"país: {n(tot_branco/tot_total*100,1)}% brancos · "
                      f"{n(tot_nulo/tot_total*100,1)}% nulos", fontsize=8.5, color=INK_SOFT)
fig.text(0.035, 1 - 0.42 / 7.6, "Onde estão os votos — e onde eles se perdem",
         fontsize=17, weight="demi", color=INK, va="top")
fig.text(0.035, 1 - 0.80 / 7.6,
         "Eleições 2026 · 1º turno · todos os cargos somados por unidade da federação",
         fontsize=10, color=INK_SOFT, va="top")
fig.text(0.035, 0.16 / 7.6, "Fonte: TSE · Dados Abertos · votação por seção eleitoral · Eleições 2026",
         fontsize=7.6, color=CINZA, va="bottom")
fig.savefig(OUT / "01_mapa.png")
plt.close(fig)

# ---------------------------------------------------------------- 02 votos por UF
d = gov.sort_values("validos")
fig = novo("Votos válidos por estado",
           "Votos válidos para Governador no 1º turno — um voto por eleitor; cor = região", 11.5, 9)
ax = fig.add_subplot(111)
y = list(range(len(d)))
ax.barh(y, d.validos, color=[REG[r] for r in d.regiao], height=0.62, zorder=3)
for i, r in enumerate(d.itertuples()):
    ax.text(r.validos * 1.012, i, compacto(r.validos), va="center", fontsize=8.2, color=INK_SOFT)
ax.set_yticks(y)
ax.set_yticklabels(d.SG_UF, fontsize=9.5, weight="demi", color=INK)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: compacto(v)))
limpar(ax, "x")
ax.set_xlim(0, d.validos.max() * 1.12)
ax.legend(handles=[mpatches.Patch(color=REG[k], label=REG_NOME[k]) for k in REG],
          loc="lower right", frameon=False, fontsize=9, handlelength=1.1, labelspacing=0.7)
fig.subplots_adjust(left=0.09)
fechar(fig, "02_votos_uf.png", 1.25)

# ---------------------------------------------------------------- 03 brancos + nulos
d = uf.assign(pct=(uf.branco + uf.nulo) / uf.total * 100).sort_values("pct")
media = (tot_branco + tot_nulo) / tot_total * 100
fig = novo("Onde o voto se perde",
           "Brancos + nulos como % dos votos depositados · 1º turno · todos os cargos", 11.5, 8.0)
ax = fig.add_subplot(111)
y = list(range(len(d)))
ax.scatter(d.pct, y, s=[36 + 240 * p / 100 for p in d.pct],
           color=[REG[r] for r in d.regiao], zorder=3, edgecolor=PAPER, lw=1.2)
for i, r in enumerate(d.itertuples()):
    ax.text(r.pct + 0.5, i, f"{n(r.pct,1)}%", va="center", fontsize=8.4, color=INK_SOFT)
ax.axvline(media, color=INK, lw=1, ls=(0, (4, 3)), zorder=4)
ax.text(media + 0.3, -0.9, f"média nacional {n(media,1)}%", fontsize=8.5, color=INK,
        va="center")
ax.set_yticks(y)
ax.set_yticklabels(d.SG_UF, fontsize=9.5, weight="demi", color=INK)
ax.set_ylim(-1.6, len(d) - 0.4)
ax.set_xlim(0, d.pct.max() * 1.16)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.0f}%"))
limpar(ax, "x")
fig.subplots_adjust(left=0.09)
fechar(fig, "03_brancos_nulos.png", 1.25)

# ---------------------------------------------------------------- 04 cargos
ordem = ["Governador", "Senador", "Deputado Federal", "Deputado Estadual", "Deputado Distrital"]
d1 = cargos[cargos.NR_TURNO == "1"].set_index("DS_CARGO").reindex(ordem).dropna(subset=["validos"])
t2 = cargos[cargos.NR_TURNO == "2"]
fig = novo("Quantos votos em disputa por cargo",
           "Votos válidos no 1º turno nas 27 unidades da federação · Senador tem duas vagas por estado\n"
           "e Deputado Distrital existe apenas no DF"
           + (f" · o 2º turno de Governador em {len(gov2)} estados somou {compacto(t2.validos.sum())} votos válidos"
              if len(t2) else ""),
           11.5, 5.8)
ax = fig.add_subplot(111)
y = list(range(len(d1)))
ax.barh(y, d1.validos, color="#4A5C82", height=0.55, zorder=3)
for i, r in enumerate(d1.itertuples()):
    ax.text(r.validos * 1.012, i, f"{compacto(r.validos)}  ·  {n(r.validos/tot_validos*100,1)}%",
            va="center", fontsize=8.6, color=INK_SOFT)
ax.set_yticks(y)
ax.set_yticklabels(d1.index, fontsize=10, weight="demi", color=INK)
ax.invert_yaxis()
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: compacto(v)))
ax.set_xlim(0, d1.validos.max() * 1.26)
limpar(ax, "x")
fig.subplots_adjust(left=0.16)
fechar(fig, "04_cargos.png", 1.75)

# ---------------------------------------------------------------- 05/06/07 top candidatos
def top_candidatos(cargo, k, arquivo, titulo, sub, cor, turno="1", extra=None):
    d = (cand.query("DS_CARGO == @cargo and NR_TURNO == @turno")
         .sort_values("votos", ascending=False).head(k).iloc[::-1])
    fig = novo(titulo, sub, 11.5, 0.45 * k + 1.55)
    ax = fig.add_subplot(111)
    y = list(range(len(d)))
    ax.barh(y, d.votos, color=cor, height=0.58, zorder=3)
    for yy, r in zip(y, d.itertuples()):
        ax.text(r.votos * 1.01, yy, f"{compacto(r.votos)}  ·  {n(r.pct_uf,1)}%",
                va="center", fontsize=8.3, color=INK_SOFT)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{nome_proprio(nm)} · {u}" for nm, u in zip(d.nome, d.SG_UF)],
                       fontsize=8.6, color=INK)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: compacto(v)))
    ax.set_xlim(0, d.votos.max() * 1.3)
    limpar(ax, "x")
    fig.subplots_adjust(left=0.245)
    fechar(fig, arquivo, 1.45)


top_candidatos("Governador", 12, "05_governadores.png",
               "Os governadores mais votados do país",
               "Votos nominais no 1º turno, todos os estados somados · % = participação nos votos válidos do próprio estado",
               "#C2543D")
top_candidatos("Senador", 12, "06_senadores.png",
               "Os senadores mais votados do país",
               "Votos nominais no 1º turno, todos os estados somados · % dentro do estado (duas vagas por UF)",
               "#2F6F6B")
top_candidatos("Deputado Federal", 20, "07_dep_federal.png",
               "Deputados federais: o topo da lista nacional",
               "Votos nominais no 1º turno, todos os estados somados · % dentro do estado",
               "#4A5C82")

# ---------------------------------------------------------------- 08 2º turno
d2 = cand.query("DS_CARGO == 'Governador' and NR_TURNO == '2'")
ufs2 = list(gov2.SG_UF)
fig = novo("Onde a eleição foi para o 2º turno",
           "Governador · 25/10/2026 · os dois candidatos mais votados em cada estado, em % dos votos válidos do 2º turno",
           12.4, 7.5)
axs = fig.subplots(2, 3)
for ax, s in zip(axs.ravel(), ufs2):
    t = d2[d2.SG_UF == s].sort_values("votos", ascending=False).head(2)
    tot = t.votos.sum()
    ax.barh([1, 0], t.votos.values, color=["#C2543D", "#4A5C82"], height=0.5, zorder=3)
    for yy, r in zip([1, 0], t.itertuples()):
        ax.text(r.votos * 1.02, yy, f"{n(r.votos/tot*100,1)}%", va="center",
                fontsize=10, color=INK, weight="demi")
        ax.text(0, yy + 0.33, nome_proprio(r.nome), va="bottom", ha="left",
                fontsize=8, color=INK_SOFT)
    ax.set_yticks([])
    ax.set_ylim(-0.55, 1.85)
    ax.set_xlim(0, t.votos.max() * 1.28)
    ax.set_title(f"{s} · {compacto(tot)} votos válidos", fontsize=9.5, color=INK_SOFT,
                 loc="left", pad=6)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: compacto(v)))
    ax.tick_params(labelsize=8)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
    limpar(ax, "x")
for ax in axs.ravel()[len(ufs2):]:
    ax.axis("off")
fig.subplots_adjust(hspace=0.95, wspace=0.22, left=0.045)
fechar(fig, "08_turno2.png", 1.45)

# ---------------------------------------------------------------- 09 concentração
d = (cand.query("DS_CARGO == 'Deputado Federal' and NR_TURNO == '1'")
     .groupby("SQ_CANDIDATO").votos.sum().sort_values(ascending=False))
cum = d.cumsum() / d.sum() * 100
x = list(range(1, len(d) + 1))
fig = novo("A concentração do voto para deputado federal",
           "Curva acumulada dos votos nominais: do candidato mais votado ao menos votado · 1º turno · Brasil",
           11.5, 6.0)
ax = fig.add_subplot(111)
ax.plot(x, cum.values, color="#4A5C82", lw=2.2, zorder=3)
ax.fill_between(x, cum.values, color="#4A5C82", alpha=0.07, zorder=2)
for pct, desloc in ((50, 0.14), (80, 0.10), (90, 0.06)):
    idx = int((cum.values >= pct).argmax())
    ax.plot([idx + 1], [cum.values[idx]], "o", color="#C2543D", ms=6, zorder=4)
    ax.annotate(f"{pct}% dos votos com {n(idx+1)} candidatos\n"
                f"({n((idx+1)/len(d)*100,1)}% dos {n(len(d))})",
                xy=(idx + 1, cum.values[idx]),
                xytext=(len(d) * desloc, cum.values[idx] - 22),
                fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color="#D8CFC0", lw=1))
ax.set_xlim(0, len(d) * 1.02)
ax.set_ylim(0, 102)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: compacto(v)))
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.0f}%"))
limpar(ax, "y")
ax.set_xlabel("candidatos, do mais votado ao menos votado", fontsize=9, labelpad=8)
fechar(fig, "09_concentracao.png", 1.25)

# ---------------------------------------------------------------- 10 legendas
d = legenda.head(15).iloc[::-1]
tot_leg = legenda.votos.sum()
fig = novo("Votos de legenda (sem nome do candidato)",
           f"1º turno · {compacto(tot_leg)} votos digitados direto no número do partido · top 15 legendas",
           11.5, 6.6)
ax = fig.add_subplot(111)
y = list(range(len(d)))
ax.barh(y, d.votos, color="#8A8F5B", height=0.6, zorder=3)
for yy, r in zip(y, d.itertuples()):
    ax.text(r.votos * 1.008, yy, f"{compacto(r.votos)} · {n(r.votos/tot_leg*100,1)}%",
            va="center", fontsize=8.4, color=INK_SOFT)
ax.set_yticks(y)
ax.set_yticklabels([sigla_partido(p) for p in d.partido], fontsize=9.5, weight="demi",
                   color=INK)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: compacto(v)))
ax.set_xlim(0, d.votos.max() * 1.26)
limpar(ax, "x")
fig.subplots_adjust(left=0.16)
fechar(fig, "10_legendas.png", 1.35)

# ---------------------------------------------------------------- 11 municípios
d = municipios.head(15).iloc[::-1]
fig = novo("Os 15 maiores colégios eleitorais",
           "Votos válidos para Governador no 1º turno, por município", 11.5, 6.6)
ax = fig.add_subplot(111)
y = list(range(len(d)))
ax.barh(y, d.validos, color=[REG[UF_REG[u]] for u in d.SG_UF], height=0.6, zorder=3)
for yy, r in zip(y, d.itertuples()):
    ax.text(r.validos * 1.008, yy, compacto(r.validos), va="center", fontsize=8.4, color=INK_SOFT)
ax.set_yticks(y)
ax.set_yticklabels([f"{nome_proprio(m)} · {u}" for m, u in zip(d.NM_MUNICIPIO, d.SG_UF)],
                   fontsize=8.8, color=INK)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: compacto(v)))
ax.set_xlim(0, d.validos.max() * 1.16)
limpar(ax, "x")
fig.subplots_adjust(left=0.235)
fechar(fig, "11_municipios.png", 1.35)

# ---------------------------------------------------------------- 12 regiões
fig = novo("O voto por região",
           "1º turno · votos válidos para Governador como medida do eleitor válido de cada região",
           12.0, 4.9)
ax = fig.add_subplot(1, 2, 1)
wedges, _ = ax.pie(reg.validos, colors=[REG[r] for r in reg.regiao], startangle=90,
                   counterclock=False,
                   wedgeprops=dict(width=0.42, edgecolor=PAPER, lw=2))
for w, r in zip(wedges, reg.itertuples()):
    ang = np.deg2rad((w.theta1 + w.theta2) / 2)
    ax.text(0.5 + 0.355 * np.cos(ang), 0.5 + 0.355 * np.sin(ang), f"{n(r.share,1)}%",
            ha="center", va="center", fontsize=8.2, color="#FFFDF8", weight="demi",
            transform=ax.transAxes)
ax.set_xlim(-1.12, 1.12)
ax.set_ylim(-1.12, 1.12)
ax.set_title(f"Distribuição dos {compacto(reg.validos.sum())} de votos válidos (Governador)",
             fontsize=10, color=INK_SOFT, loc="center", pad=6)

ax = fig.add_subplot(1, 2, 2)
x = list(range(len(reg)))
share_val = reg.pct_val
share_bn = 100 - share_val
ax.barh(x, share_val, color=[REG[r] for r in reg.regiao], height=0.5, zorder=3)
ax.barh(x, share_bn, left=share_val, color="#E4DACB", height=0.5, zorder=3)
for i, r in enumerate(reg.itertuples()):
    ax.text(share_val.iloc[i] / 2, i, f"{n(share_val.iloc[i],1)}%", va="center", ha="center",
            color="#FFFDF8", fontsize=9, weight="demi")
    ax.text(share_val.iloc[i] + share_bn.iloc[i] / 2, i, f"{n(share_bn.iloc[i],1)}%",
            va="center", ha="center", color=INK_SOFT, fontsize=8.2)
    ax.text(101.5, i, compacto(r.validos), va="center", fontsize=8.2, color=INK_SOFT)
ax.set_yticks(x)
ax.set_yticklabels([REG_NOME[r] for r in reg.regiao], fontsize=9.5, weight="demi")
ax.invert_yaxis()
ax.set_xlim(0, 118)
ax.set_ylim(len(reg) - 0.3, -1.3)
ax.set_xticks([0, 25, 50, 75, 100])
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.0f}%"))
limpar(ax, "x")
ax.set_title("Aproveitamento do voto depositado, por região", fontsize=10, color=INK_SOFT, loc="left", pad=10)
ax.legend(handles=[mpatches.Patch(color="#4A5C82", label="válidos"),
                   mpatches.Patch(color="#E4DACB", label="brancos + nulos")],
          loc="upper right", frameon=False, fontsize=8.2, handlelength=1, ncol=2,
          bbox_to_anchor=(1.0, 1.12))
fig.subplots_adjust(wspace=0.28, left=0.10)
fechar(fig, "12_regioes.png", 1.30)

# ---------------------------------------------------------------- resumo.json
resumo = {
    "total_votos": tot_total,
    "validos": tot_validos,
    "brancos": tot_branco,
    "nulos": tot_nulo,
    "pct_brancos": tot_branco / tot_total * 100,
    "pct_nulos": tot_nulo / tot_total * 100,
    "pct_bn": (tot_branco + tot_nulo) / tot_total * 100,
    "legenda": int(uf.legenda.sum()),
    "eleitores": eleitores,
    "validos_governador_t2": int(gov2.validos.sum()) if len(gov2) else 0,
    "ufs_turno2": list(gov2.SG_UF),
    "pct_bn_ufs": round(float(((uf.branco + uf.nulo) / uf.total * 100).max()), 2),
    "pct_bn_uf_max": uf.assign(p=(uf.branco + uf.nulo) / uf.total * 100)
                       .sort_values("p").iloc[-1].SG_UF,
    "pct_bn_uf_min": uf.assign(p=(uf.branco + uf.nulo) / uf.total * 100)
                       .sort_values("p").iloc[0].SG_UF,
    "tabela_uf": [
        {"uf": r.SG_UF, "regiao": REG_NOME[UF_REG[r.SG_UF]], "validos": int(r.validos),
         "brancos": int(r.branco), "nulos": int(r.nulo), "total": int(r.total),
         "pct_bn": (r.branco + r.nulo) / r.total * 100}
        for r in uf.sort_values("validos", ascending=False).itertuples()
    ],
    "top_gov": [
        {"nome": nome_proprio(r.nome), "uf": r.SG_UF, "votos": int(r.votos),
         "pct": float(r.pct_uf)}
        for r in cand.query("DS_CARGO == 'Governador' and NR_TURNO == '1'")
                     .sort_values("votos", ascending=False).head(6).itertuples()
    ],
    "top_legendas": [
        {"partido": sigla_partido(r.partido), "votos": int(r.votos),
         "pct": r.votos / float(legenda.votos.sum()) * 100}
        for r in legenda.head(5).itertuples()
    ],
    "regioes": [
        {"regiao": REG_NOME[r.regiao], "validos": int(r.validos),
         "pct_val": float(r.pct_val), "share": float(r.share)}
        for r in reg.itertuples()
    ],
}
(BASE / "dados" / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2))
print("ok:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))
print(json.dumps({k: v for k, v in resumo.items() if not isinstance(v, list)},
                 ensure_ascii=False, indent=2))
