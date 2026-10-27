"""
Monta o relatório estático:
    index.html  — votos por região (13 gráficos)
    urnas.html  — quando cada urna fechou (gráfico 14)

Uso: ./.venv/bin/python relatorio.py
"""
import json
import pathlib
from datetime import datetime

import duckdb
import pandas as pd

BASE = pathlib.Path(__file__).parent
r = json.loads((BASE / "dados" / "resumo.json").read_text())


def n(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mi(v):
    if abs(v) >= 1e6:
        c = f"{v/1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return c.replace(",0", "") + " mi"
    return f"{v/1e3:,.0f}".replace(",", ".") + " mil"


# ---------------------------------------------------------------- apuração (gráfico 13)
apuracao = None
serie_p = BASE / "dados" / "apuracao_presidente_2026.csv"
if serie_p.exists():
    s = pd.read_csv(serie_p)
    d = s.pct_lula - s.pct_flavio
    cruzes = [i for i in range(1, len(d)) if (d[i] > 0) != (d[i - 1] > 0)]
    apuracao = {
        "lula": s.pct_lula.iloc[-1],
        "flavio": s.pct_flavio.iloc[-1],
        "validos": int(s.votos_validos.iloc[-1]),
        "cruzamentos": [(s.hora.iloc[i][11:], s.pct_urnas.iloc[i]) for i in cruzes],
    }

# ---------------------------------------------------------------- urnas por fechamento (gráfico 14)
urnas = None
parq = BASE / "dados" / "urnas_fechamento_2026.parquet"
if parq.exists():
    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW u AS SELECT * FROM read_parquet('{parq.as_posix()}')")
    q = lambda sql: con.execute(sql).df()

    faixas = q("""
        SELECT CASE
                 WHEN fech_brt <  '2026-10-25 17:00:00' THEN 0
                 WHEN fech_brt <  '2026-10-25 17:00:30' THEN 1
                 WHEN fech_brt <  '2026-10-25 17:01:00' THEN 2
                 WHEN fech_brt <  '2026-10-25 17:05:00' THEN 3
                 WHEN fech_brt <  '2026-10-25 17:15:00' THEN 4
                 WHEN fech_brt <  '2026-10-25 17:30:00' THEN 5
                 WHEN fech_brt <  '2026-10-25 18:00:00' THEN 6
                 WHEN fech_brt <  '2026-10-25 19:00:00' THEN 7
                 ELSE 8 END faixa,
               COUNT(*) urnas, SUM(validos) votos, SUM(lula) lula, SUM(flavio) flavio
        FROM u WHERE uf <> 'ZZ' GROUP BY 1 ORDER BY 1
    """)
    rotulos = ["antes das 17h", "17:00:00–17:00:29", "17:00:30–17:00:59", "17:01–17:04",
               "17:05–17:14", "17:15–17:29", "17:30–17:59", "18:00–18:59", "19:00 ou depois"]
    faixas["rotulo"] = [rotulos[i] for i in faixas.faixa]
    faixas["lula_pct"] = faixas.lula / faixas.votos * 100
    faixas["saldo"] = faixas.lula - faixas.flavio

    tot = q("""SELECT COUNT(*) urnas, SUM(validos) votos, SUM(lula) lula, SUM(flavio) flavio,
                      MIN(fech_brt) ini, MAX(fech_brt) fim
               FROM u WHERE uf <> 'ZZ'""").iloc[0]
    tarde = q("""SELECT COUNT(*) urnas, SUM(validos) votos, SUM(lula) lula, SUM(flavio) flavio
                 FROM u WHERE uf <> 'ZZ' AND fech_brt > '2026-10-25 17:05:00'""").iloc[0]
    ct = q("""SELECT CASE WHEN rec_brt < '2026-10-25 20:23' THEN 'A' ELSE 'B' END chegada,
                     CASE WHEN fech_brt > '2026-10-25 17:05:00' THEN 'tarde' ELSE 'hora' END fech,
                     COUNT(*) urnas, SUM(validos) votos, SUM(lula) lula, SUM(flavio) flavio
              FROM u WHERE uf <> 'ZZ' GROUP BY 1, 2 ORDER BY 1, 2""")
    ct["lula_pct"] = ct.lula / ct.votos * 100
    ct["saldo"] = ct.lula - ct.flavio
    urnas = {
        "total_urnas": int(tot.urnas), "total_votos": int(tot.votos),
        "ini": str(tot.ini)[11:16], "fim": str(tot.fim)[11:16],
        "tarde": tarde, "faixas": faixas, "ct": ct,
        "margem_tarde": int(tarde.lula - tarde.flavio),
        "margem_total": int(tot.lula - tot.flavio),
    }

COR_REG = {"Norte": "#2F6F6B", "Nordeste": "#C2543D", "Centro-Oeste": "#B08A3E",
           "Sudeste": "#4A5C82", "Sul": "#8A8F5B"}

blocos = [
    ("01_mapa.png", "O mapa",
     f"As duas leituras do mesmo território: à esquerda, onde estão os votos válidos para governador; "
     f"à direita, onde eles se perdem em brancos e nulos. O Nordeste concentra os maiores percentuais de "
     f"voto desperdiçado — Pernambuco lidera com {n(max(u['pct_bn'] for u in r['tabela_uf']),1)}%."),
    ("02_votos_uf.png", "O tamanho de cada estado",
     f"São Paulo sozinho tem mais votos válidos que a região Norte inteira. Entre o maior e o menor estado, "
     f"a diferença é de {n(next(u['validos'] for u in r['tabela_uf'] if u['uf']=='SP') / min(u['validos'] for u in r['tabela_uf']),1)} vezes."),
    ("04_cargos.png", "Quantos votos por cargo",
     f"Cada eleitor digita cinco números na urna — e dois deles vão para o Senado, o único cargo que "
     f"aparece com o dobro de votos. Deputado distrital existe apenas no Distrito Federal."),
    ("05_governadores.png", "Governadores",
     "Ranking nacional de votos nominais, com a participação de cada um dentro do próprio estado. "
     "Tarcísio de Freitas (SP) é o mais votado do país, com 62,6% dos votos válidos paulistas."),
    ("06_senadores.png", "Senadores",
     "Duas vagas por estado: os nomes abaixo somam votos de eleitores diferentes, então o ranking mede "
     "peso eleitoral, não vantagem competitiva."),
    ("07_dep_federal.png", "Deputados federais",
     "O topo da lista nacional mostra os puxadores de voto: candidatos que sozinhos somam mais que partidos "
     "inteiros, medidos em % dos votos válidos do seu estado."),
    ("09_concentracao.png", "A concentração do voto",
     "Metade dos votos nominais para deputado federal ficou com 297 candidatos — 4% do total. "
     "A cauda longa de candidatos leva poucos votos cada."),
    ("08_turno2.png", "Os seis segundos turnos",
     f"Governador foi decidido em dois turnos em {len(r['ufs_turno2'])} estados "
     f"({', '.join(r['ufs_turno2'])}), somando {mi(r['validos_governador_t2'])} votos válidos em 25/10."),
    ("13_apuracao_presidente.png", "A apuração, urna por urna",
     (f"Reconstrução minuto a minuto do 2º turno presidencial pela hora em que cada arquivo CHEGOU ao TSE: "
      f"Flávio liderou entre as {apuracao['cruzamentos'][0][0]} e as {apuracao['cruzamentos'][1][0]}, quando "
      f"14% a 47% das urnas já haviam sido apuradas. Dali em diante Lula abriu vantagem e fechou em "
      f"{n(apuracao['lula'],2)}% × {n(apuracao['flavio'],2)}% — margem de "
      f"{n(apuracao['lula']-apuracao['flavio'],2)} pontos, com {n(apuracao['validos'])} votos válidos.")
     if apuracao else "A apuração do 2º turno presidencial minuto a minuto."),
    ("03_brancos_nulos.png", "Brancos e nulos",
     f"{n(r['pct_brancos'],1)}% dos votos foram em branco e {n(r['pct_nulos'],1)}% nulos. "
     f"A diferença entre o estado mais e o menos desperdiçador passa de 10 pontos percentuais."),
    ("10_legendas.png", "Voto de legenda",
     f"{mi(r['legenda'])} votos foram digitados direto no número do partido (voto de legenda), "
     f"sem escolher um nome — PT e PL concentram quase metade desse total."),
    ("11_municipios.png", "Colégios eleitorais",
     "São Paulo, Rio e Brasília lideram; nenhum município fora das capitais e regiões metropolitanas "
     "aparece entre os quinze maiores."),
    ("12_regioes.png", "Regiões",
     "O Sudeste tem 40% dos votos válidos e também o pior aproveitamento: 11,5% dos votos depositados "
     "não foram válidos."),
]
blocos.sort(key=lambda b: b[0])

cards = [
    (n(r["total_votos"]), "votos depositados", "1º turno, todos os cargos"),
    (f"{n(apuracao['lula'],2)}%" if apuracao else "—", "Lula no 2º turno",
     f"Flávio {n(apuracao['flavio'],2)}% · margem {n(apuracao['lula']-apuracao['flavio'],2)} p.p."
     if apuracao else ""),
    (n(r["eleitores"]), "eleitores válidos", "votos válidos para governador"),
    (f"{n(r['pct_bn'],1)}%", "brancos + nulos", f"{mi(r['brancos'])} + {mi(r['nulos'])}"),
    (f"{len(r['ufs_turno2'])}", "estados com 2º turno", " · ".join(r["ufs_turno2"])),
]

linhas = "\n".join(
    f"""      <tr>
        <td><span class="uf">{u['uf']}</span></td>
        <td class="dim">{u['regiao']}</td>
        <td class="num">{n(u['validos'])}</td>
        <td class="num">{n(u['brancos'])}</td>
        <td class="num">{n(u['nulos'])}</td>
        <td class="num"><span class="barra" style="--w:{u['pct_bn'] / 15 * 100:.1f}%"></span>{n(u['pct_bn'],1)}%</td>
      </tr>"""
    for u in r["tabela_uf"]
)

galeria = "\n".join(
    f"""
  <section class="card" id="{arq.replace('.png', '')}">
    <figure>
      <img src="graficos/{arq}" alt="{titulo}" loading="lazy">
      <figcaption>
        <h2>{titulo}</h2>
        <p>{texto}</p>
      </figcaption>
    </figure>
  </section>"""
    for arq, titulo, texto in blocos
)

# ---------------------------------------------------------------- CSS / navegação
CSS = """
  :root {
    --paper: #FAF7F1;
    --paper-2: #F4EFE4;
    --ink: #1A2129;
    --ink-soft: #5D6673;
    --hair: #E2D9CA;
    --rust: #C2543D;
    --teal: #2F6F6B;
    --indigo: #4A5C82;
    --serif: "Iowan Old Style", "Palatino", Georgia, serif;
    --sans: "Avenir Next", "Helvetica Neue", -apple-system, system-ui, sans-serif;
    --mono: "JetBrains Mono", "SF Mono", ui-monospace, Menlo, monospace;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--paper); color: var(--ink);
    font-family: var(--sans); font-size: 17px; line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 0 28px; }

  nav.topo {
    border-bottom: 1px solid var(--hair); background: var(--paper);
    position: sticky; top: 0; z-index: 10;
  }
  nav.topo .wrap {
    display: flex; align-items: center; gap: 26px;
    padding-top: 14px; padding-bottom: 14px;
  }
  nav.topo .marca {
    font-family: var(--mono); font-size: 11px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--ink-soft); margin-right: auto;
  }
  nav.topo a {
    font-family: var(--mono); font-size: 11.5px; letter-spacing: .1em;
    text-transform: uppercase; text-decoration: none; color: var(--ink-soft);
    padding-bottom: 3px; border-bottom: 1px solid transparent;
  }
  nav.topo a:hover { color: var(--ink); }
  nav.topo a[aria-current="page"] { color: var(--ink); border-bottom-color: var(--rust); }

  header.hero { padding: 80px 0 56px; border-bottom: 1px solid var(--hair); }
  .eyebrow {
    font-family: var(--mono); font-size: 11.5px; letter-spacing: .16em;
    text-transform: uppercase; color: var(--rust); margin: 0 0 22px;
  }
  h1 {
    font-family: var(--serif); font-weight: 600; font-size: clamp(38px, 6.2vw, 68px);
    line-height: 1.02; letter-spacing: -.02em; margin: 0 0 22px; max-width: 20ch;
  }
  h1 em { font-style: italic; color: var(--rust); }
  .lead { max-width: 62ch; color: var(--ink-soft); font-size: 18.5px; margin: 0; }
  .meta {
    display: flex; flex-wrap: wrap; gap: 8px 26px; margin-top: 34px;
    font-family: var(--mono); font-size: 12px; color: var(--ink-soft);
  }
  .meta span::before { content: "◦ "; color: var(--hair); }

  .cards { display: flex; flex-wrap: wrap; border-block: 1px solid var(--hair); margin: 0; padding: 0; }
  .card-stat {
    flex: 1 1 190px; background: var(--paper); padding: 32px 24px 30px;
    border-right: 1px solid var(--hair);
  }
  .card-stat:last-child { border-right: none; }
  .card-stat b {
    display: block; font-family: var(--mono); font-size: 27px; font-weight: 500;
    letter-spacing: -.03em; color: var(--ink);
  }
  .card-stat small { display: block; color: var(--ink-soft); font-size: 13.5px; margin-top: 6px; }
  .card-stat small.dim { color: #9AA1AB; font-family: var(--mono); font-size: 11.5px; }

  main { padding: 18px 0 40px; }
  section.card { padding: 54px 0; border-bottom: 1px solid var(--hair); }
  section.card:last-child { border-bottom: none; }
  figure { margin: 0; }
  figure img {
    width: 100%; height: auto; display: block; border-radius: 3px;
    border: 1px solid var(--hair); background: #fff;
  }
  figcaption { display: grid; grid-template-columns: 240px 1fr; gap: 12px 44px; margin-top: 26px; }
  figcaption h2 {
    font-family: var(--serif); font-size: 21px; font-weight: 600; margin: 0;
    letter-spacing: -.01em;
  }
  figcaption p { margin: 0; color: var(--ink-soft); font-size: 15.5px; max-width: 62ch; }

  section.tabela { padding: 60px 0 20px; }
  .tabela h2 {
    font-family: var(--serif); font-size: 30px; font-weight: 600; margin: 0 0 8px;
    letter-spacing: -.015em;
  }
  .tabela p.sub { color: var(--ink-soft); margin: 0 0 30px; font-size: 15.5px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  thead th {
    text-align: left; font-family: var(--mono); font-size: 10.5px; font-weight: 500;
    letter-spacing: .1em; text-transform: uppercase; color: var(--ink-soft);
    padding: 0 12px 12px 0; border-bottom: 1px solid var(--ink);
    white-space: nowrap;
  }
  thead th.num, td.num { text-align: right; }
  tbody td { padding: 9px 12px 9px 0; border-bottom: 1px solid var(--hair); }
  tbody tr:hover td { background: var(--paper-2); }
  tbody tr.destaque td { background: #F7EDE7; }
  td.num { font-family: var(--mono); font-size: 12.5px; color: var(--ink); }
  td.dim { color: #9AA1AB; font-size: 13px; }
  .uf { font-family: var(--mono); font-weight: 500; font-size: 13px; }
  .barra {
    display: inline-block; height: 6px; width: var(--w); max-width: 60px;
    background: var(--rust); opacity: .55; border-radius: 1px; margin-right: 8px;
    vertical-align: middle;
  }

  .proximo {
    display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 24px;
    border: 1px solid var(--hair); border-radius: 3px; padding: 28px 30px;
    margin: 10px 0 60px; text-decoration: none; color: inherit; background: var(--paper);
  }
  .proximo:hover { background: var(--paper-2); }
  .proximo span {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--rust);
  }
  .proximo strong {
    display: block; font-family: var(--serif); font-size: 24px; font-weight: 600;
    margin-top: 6px; letter-spacing: -.01em;
  }
  .proximo em { color: var(--ink-soft); font-style: normal; font-size: 14.5px; }
  .proximo b { font-size: 26px; color: var(--rust); }

  .metodo { padding: 60px 0 90px; border-top: 1px solid var(--hair); }
  .metodo h2 { font-family: var(--serif); font-size: 22px; font-weight: 600; margin: 0 0 14px; }
  .metodo ul { margin: 0; padding-left: 18px; color: var(--ink-soft); font-size: 15px; }
  .metodo li { margin-bottom: 7px; }
  .metodo code {
    font-family: var(--mono); font-size: 12.5px; background: var(--paper-2);
    padding: 1px 6px; border-radius: 3px; color: var(--ink);
  }
  footer { padding: 26px 0 60px; color: #9AA1AB; font-family: var(--mono); font-size: 11.5px; }
  @media (max-width: 720px) {
    figcaption { grid-template-columns: 1fr; }
    header.hero { padding-top: 50px; }
    section.card { padding: 40px 0; }
    nav.topo .marca { display: none; }
  }
"""


def nav(atual):
    itens = [("index.html", "Votos por região"), ("urnas.html", "Quando a urna fechou")]
    ativo = ' aria-current="page"'
    links = "".join(
        f'<a href="{href}"{ativo if href == atual else ""}>{txt}</a>'
        for href, txt in itens
    )
    return f"""<nav class="topo"><div class="wrap">
      <span class="marca">Eleições 2026 · TSE</span>{links}
  </div></nav>"""


# ---------------------------------------------------------------- página 1
cards_html = "".join(
    f'<div class="card-stat"><b>{a}</b><small>{b}</small><small class="dim">{c}</small></div>'
    for a, b, c in cards
)

html_index = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eleições 2026 · votos por região</title>
<style>{CSS}</style>
</head>
<body>
{nav("index.html")}

<header class="hero">
  <div class="wrap">
    <p class="eyebrow">Tribunal Superior Eleitoral · Dados Abertos</p>
    <h1>Como o Brasil <em>votou</em> em 2026</h1>
    <p class="lead">
      Votos por seção eleitoral das Eleições Gerais de 2026, agregados por estado, região, cargo
      e município. Os 27 arquivos originais do TSE foram baixados, descompactados e somados:
      {n(r['total_votos'])} votos depositados, {n(r['eleitores'])} eleitores válidos para governador
      e {n(r['pct_bn'],1)}% de votos em branco ou nulo. No fim, a reconstrução da apuração
      presidencial minuto a minuto — urna por urna, com o horário de recebimento de cada boletim.
    </p>
    <div class="meta">
      <span>eleição de 04/10 e 25/10/2026</span>
      <span>27 unidades da federação</span>
      <span>{len(blocos)} gráficos</span>
      <span>fonte: votacao_secao_2026_*.zip</span>
    </div>
  </div>
</header>

<div class="wrap">
  <div class="cards">{cards_html}</div>
</div>

<main class="wrap">
{galeria}

  <a class="proximo" href="urnas.html">
    <div>
      <span>próxima página · boletim de urna</span>
      <strong>Quando cada urna fechou</strong>
      <em>Quem estava na frente e atrás conforme as urnas com fila — as que registraram voto depois das 17h — vão entrando na conta.</em>
    </div>
    <b>&rarr;</b>
  </a>

  <section class="tabela">
    <h2>Os 27 estados, lado a lado</h2>
    <p class="sub">Votos do 1º turno somando todos os cargos. Clique nos títulos para ordenar.</p>
    <table id="tab">
      <thead>
        <tr>
          <th data-col="0">UF</th>
          <th data-col="1">Região</th>
          <th data-col="2" class="num">Válidos</th>
          <th data-col="3" class="num">Brancos</th>
          <th data-col="4" class="num">Nulos</th>
          <th data-col="5" class="num">Brancos + nulos</th>
        </tr>
      </thead>
      <tbody>
{linhas}
      </tbody>
    </table>
  </section>

  <section class="metodo">
    <h2>Como os números foram feitos</h2>
    <ul>
      <li>Baixados os 27 arquivos <code>votacao_secao_2026_UF.zip</code> do portal de dados abertos do TSE
          e descompactados em <code>csv/</code> (um CSV por estado, ~18 GB no total).</li>
      <li>Os CSVs foram consolidados em uma única tabela (<code>dados/agregado.parquet</code>) com três recortes:
          UF × cargo, município × cargo e candidato.</li>
      <li><strong>Votos válidos</strong> = votos nominais + votos de legenda (exclui brancos e nulos).
          <strong>Votos depositados</strong> = tudo que entrou na urna.</li>
      <li>Para comparar estados usa-se o voto para <strong>governador</strong>: é a única escolha em que cada
          eleitor deposita exatamente um voto, então serve como medida de eleitor válido.</li>
      <li>Votos de legenda são identificados pelo código de candidato <code>-3</code>; brancos e nulos, por
          <code>-1</code>.</li>
      <li>A apuração minuto a minuto não existe pronta: o arquivo de votação tem só o resultado final.
          O horário de cada urna vem do <strong>Detalhe da apuração por seção eleitoral</strong>
          (<code>DT_RECEBIMENTO_BU_HOR_TSE</code>), cruzado com os votos por
          UF + município + zona + seção.</li>
      <li>Os percentuais da apuração são cumulativos: cada ponto soma todas as urnas recebidas até aquele
          minuto. Entre 17h07 e 19h02 nenhuma urna nova chegou ao TSE, por isso o patamar reto no começo.</li>
      <li>Sem dados de abstenção nem de comparecimento (essas bases vêm em outro conjunto do TSE).</li>
    </ul>
    <p style="color:#9AA1AB;font-family:var(--mono);font-size:11.5px;margin-top:22px">
      gerado em {datetime.now():%d/%m/%Y %H:%M} · <code>analise.py</code> → <code>graficos.py</code> → <code>relatorio.py</code>
    </p>
  </section>
</main>

<footer>
  <div class="wrap">
    TSE · Dados Abertos · Resultados 2026 · votação por seção eleitoral — tratamento local, sem vínculo com o Tribunal.
  </div>
</footer>

<script>
(function () {{
  const tab = document.getElementById('tab');
  const corpo = tab.tBodies[0];
  const linhas = [...corpo.rows];
  const num = (s) => parseFloat(s.replace(/\\./g, '').replace(',', '.')) || 0;
  let dir = {{}};
  linhas.forEach((tr) => {{
    [...tr.cells].forEach((td, i) => {{
      if (i >= 2) td.dataset.v = String(num(td.textContent));
    }});
  }});
  tab.tHead.addEventListener('click', (e) => {{
    const th = e.target.closest('th'); if (!th) return;
    const col = +th.dataset.col;
    dir[col] = !dir[col];
    [...linhas].sort((a, b) => {{
      const ca = a.cells[col].dataset.v ?? a.cells[col].textContent.trim();
      const cb = b.cells[col].dataset.v ?? b.cells[col].textContent.trim();
      const va = col >= 2 ? num(ca) : ca;
      const vb = col >= 2 ? num(cb) : cb;
      return (va < vb ? -1 : va > vb ? 1 : 0) * (dir[col] ? 1 : -1);
    }}).forEach((tr) => corpo.appendChild(tr));
  }});
}})();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------- página 2
pagina_urnas = ""
if urnas:
    t = urnas["tarde"]
    faixas_html = "\n".join(
        f"""      <tr{' class="destaque"' if f.faixa >= 4 else ''}>
        <td><span class="uf">{f.rotulo}</span></td>
        <td class="num">{n(f.urnas)}</td>
        <td class="num">{n(f.urnas / urnas['total_urnas'] * 100, 1)}%</td>
        <td class="num">{n(f.votos)}</td>
        <td class="num">{n(f.lula_pct, 1)}%</td>
        <td class="num">{'+' if f.saldo > 0 else '−'}{n(abs(f.saldo))}</td>
      </tr>"""
        for f in urnas["faixas"].itertuples()
    )
    ct = urnas["ct"]
    a_tarde = ct[(ct.chegada == "A") & (ct.fech == "tarde")].iloc[0]
    a_hora = ct[(ct.chegada == "A") & (ct.fech == "hora")].iloc[0]
    b_tarde = ct[(ct.chegada == "B") & (ct.fech == "tarde")].iloc[0]
    b_hora = ct[(ct.chegada == "B") & (ct.fech == "hora")].iloc[0]
    tot_a, tot_b = a_tarde.urnas + a_hora.urnas, b_tarde.urnas + b_hora.urnas

    cards_urnas = [
        (n(int(t.urnas)), "urnas fecharam depois das 17h05",
         f"{n(t.urnas / urnas['total_urnas'] * 100,1)}% das {n(urnas['total_urnas'])} urnas"),
        (n(int(t.votos)), "votos válidos nessas urnas",
         f"{n(t.votos / urnas['total_votos'] * 100,1)}% do total apurado"),
        (f"{n(t.lula / t.votos * 100,1)}%", "foi para Lula",
         f"Flávio {n(t.flavio / t.votos * 100,1)}%"),
        (f"+{n(urnas['margem_tarde'])}", "de saldo para Lula",
         f"{n(urnas['margem_tarde'] / urnas['margem_total'] * 100,0)}% da margem final"),
    ]
    cards_urnas_html = "".join(
        f'<div class="card-stat"><b>{a}</b><small>{b}</small><small class="dim">{c}</small></div>'
        for a, b, c in cards_urnas
    )

    pagina_urnas = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eleições 2026 · quando cada urna fechou</title>
<style>{CSS}</style>
</head>
<body>
{nav("urnas.html")}

<header class="hero">
  <div class="wrap">
    <p class="eyebrow">Boletim de Urna · DT_ENCERRAMENTO</p>
    <h1>Quando cada urna <em>fechou</em></h1>
    <p class="lead">
      O TSE não registra a hora de cada voto — voto é sigiloso. O que existe é a hora em que cada urna
      <strong>fechou</strong>, no Boletim de Urna. É o mais perto de "voto depois das 17h": só urna que
      fechou com fila recebeu voto depois do horário legal. Ordenando as {n(urnas['total_urnas'])} urnas
      por esse horário, dá para ver quem estava na frente a cada minuto — e quando a eleição virou.
    </p>
    <div class="meta">
      <span>2º turno · 25/10/2026</span>
      <span>{n(urnas['total_urnas'])} urnas</span>
      <span>{n(urnas['total_votos'])} votos válidos</span>
      <span>das {urnas['ini']} às {urnas['fim']} (Brasília)</span>
      <span>fonte: Boletim de Urna</span>
    </div>
  </div>
</header>

<div class="wrap">
  <div class="cards">{cards_urnas_html}</div>
</div>

<main class="wrap">
  <section class="card" id="grafico">
    <figure>
      <img src="graficos/14_urnas_fechamento.png" alt="Apuração por horário de fechamento da urna">
      <figcaption>
        <h2>Quem estava na frente, urna por urna</h2>
        <p>
          À esquerda, a apuração inteira: as urnas entram na conta pelo horário de fechamento, das 17h
          às {urnas['fim']}. À direita, o zoom dos primeiros seis minutos, onde 96% das urnas fecham.
          No primeiro minuto Flávio liderava com 50,99% (as urnas que fecham mais rápido são as menores,
          do Sul e do Sudeste); às 17h01 Lula passou à frente com 50,20% e a partir dali a diferença só
          cresceu, até 51,79% × 48,21%. Abaixo, o ritmo: 89% das urnas já tinham fechado às 17h04.
        </p>
      </figcaption>
    </figure>
  </section>

  <section class="tabela">
    <h2>As urnas por horário de fechamento</h2>
    <p class="sub">
      Cada linha é um grupo de urnas que fechou naquele intervalo, com os votos que estavam dentro.
      As linhas destacadas são as que registraram voto depois das 17h05 — 57 mil urnas, 12% dos votos.
    </p>
    <table>
      <thead>
        <tr>
          <th>Fechou</th>
          <th class="num">Urnas</th>
          <th class="num">% das urnas</th>
          <th class="num">Votos válidos</th>
          <th class="num">Lula</th>
          <th class="num">Saldo Lula</th>
        </tr>
      </thead>
      <tbody>
{faixas_html}
      </tbody>
    </table>
  </section>

  <section class="tabela">
    <h2>O atraso da urna e o atraso da transmissão</h2>
    <p class="sub">
      São duas coisas diferentes: a urna fechar tarde (teve fila, registrou voto depois das 17h) e o
      arquivo chegar tarde ao TSE (transmissão). Cruzando as duas, dá para responder quantas das urnas
      que chegaram atrasadas para a totalização realmente votaram depois do horário.
    </p>
    <table>
      <thead>
        <tr>
          <th>Chegou ao TSE</th>
          <th>Fechou a urna</th>
          <th class="num">Urnas</th>
          <th class="num">Votos válidos</th>
          <th class="num">Lula</th>
          <th class="num">Saldo Lula</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td rowspan="2"><span class="uf">até 20h23</span><br><span class="dim">{n(int(tot_a))} urnas</span></td>
          <td class="dim">no horário (até 17h05)</td>
          <td class="num">{n(int(a_hora.urnas))}</td>
          <td class="num">{n(int(a_hora.votos))}</td>
          <td class="num">{n(a_hora.lula_pct,1)}%</td>
          <td class="num">{'+' if a_hora.saldo > 0 else '−'}{n(abs(a_hora.saldo))}</td>
        </tr>
        <tr class="destaque">
          <td class="dim">depois das 17h</td>
          <td class="num">{n(int(a_tarde.urnas))}</td>
          <td class="num">{n(int(a_tarde.votos))}</td>
          <td class="num">{n(a_tarde.lula_pct,1)}%</td>
          <td class="num">+{n(int(a_tarde.saldo))}</td>
        </tr>
        <tr>
          <td rowspan="2"><span class="uf">depois das 20h23</span><br><span class="dim">{n(int(tot_b))} urnas</span></td>
          <td class="dim">no horário (até 17h05)</td>
          <td class="num">{n(int(b_hora.urnas))}</td>
          <td class="num">{n(int(b_hora.votos))}</td>
          <td class="num">{n(b_hora.lula_pct,1)}%</td>
          <td class="num">{'+' if b_hora.saldo > 0 else '−'}{n(abs(b_hora.saldo))}</td>
        </tr>
        <tr class="destaque">
          <td class="dim">depois das 17h</td>
          <td class="num">{n(int(b_tarde.urnas))}</td>
          <td class="num">{n(int(b_tarde.votos))}</td>
          <td class="num">{n(b_tarde.lula_pct,1)}%</td>
          <td class="num">+{n(int(b_tarde.saldo))}</td>
        </tr>
      </tbody>
    </table>
    <p class="sub" style="margin-top:26px">
      Das {n(int(tot_b))} urnas que chegaram depois das 20h23 — o bloco que decidiu a eleição —,
      <strong>{n(int(b_tarde.urnas))} ({n(b_tarde.urnas/tot_b*100,1)}%)</strong> fecharam depois das 17h05.
      No bloco que chegou mais cedo, essa proporção é de {n(a_tarde.urnas/tot_a*100,1)}%. Ou seja: urna
      que fecha com fila também tende a demorar mais para transmitir.
    </p>
  </section>

  <section class="metodo">
    <h2>Como os números foram feitos</h2>
    <ul>
      <li>Fonte: dataset <strong>"Resultados — 2026 — Boletim de Urna"</strong>, 28 arquivos
          (<code>bweb_2t_UF_*.zip</code>, um por estado mais o exterior), ~1 GB de CSV.</li>
      <li>Cada linha do BU é um candidato em uma urna. Dela saem <code>DT_ENCERRAMENTO</code>
          (fechamento), <code>DT_BU_RECEBIDO</code> (chegada ao TSE) e os votos.</li>
      <li>Os horários são locais; converti para Brasília inferindo o fuso de cada município pelo
          horário legal de fechamento (15h local = UTC-5, 16h = UTC-4, 17h = UTC-3). Amazonas tem
          os dois fusos.</li>
      <li>Os totais conferem com a votação por seção: {n(urnas['total_votos'])} votos válidos,
          os mesmos 64.256.232 de Lula e 59.826.041 de Flávio (o exterior fica de fora do corte de horário).</li>
      <li><strong>O que este dado não diz:</strong> quantos votos individuais foram digitados depois das 17h.
          A urna registra o fechamento da seção, não o horário de cada voto. Os {n(int(t.votos))} votos
          acima são um teto — vêm de urnas que estavam abertas depois das 17h05.</li>
    </ul>
    <p style="color:#9AA1AB;font-family:var(--mono);font-size:11.5px;margin-top:22px">
      <code>urnas.py</code> → <code>dados/urnas_fechamento_2026.parquet</code> → <code>graficos/14_urnas_fechamento.png</code>
    </p>
  </section>
</main>

<footer>
  <div class="wrap">
    TSE · Dados Abertos · Resultados 2026 · Boletim de Urna — tratamento local, sem vínculo com o Tribunal.
  </div>
</footer>
</body>
</html>
"""

(BASE / "index.html").write_text(html_index)
print("index.html:", (BASE / "index.html").stat().st_size / 1024, "KB")
if pagina_urnas:
    (BASE / "urnas.html").write_text(pagina_urnas)
    print("urnas.html:", (BASE / "urnas.html").stat().st_size / 1024, "KB")
else:
    print("urnas.html: sem dados (rode urnas.py antes)")
