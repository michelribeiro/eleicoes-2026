"""
Monta o relatório HTML (index.html) com os gráficos e a tabela por UF.

Uso: ./.venv/bin/python relatorio.py
"""
import json
import pathlib
from datetime import datetime

BASE = pathlib.Path(__file__).parent
r = json.loads((BASE / "dados" / "resumo.json").read_text())


def n(v, dec=0):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mi(v):
    if abs(v) >= 1e6:
        c = f"{v/1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return c.replace(",0", "") + " mi"
    return f"{v/1e3:,.0f}".replace(",", ".") + " mil"


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
     f"Metade dos votos nominais para deputado federal ficou com 297 candidatos — 4% do total. "
     f"A cauda longa de candidatos leva poucos votos cada."),
    ("08_turno2.png", "Os seis segundos turnos",
     f"Governador foi decidido em dois turnos em {len(r['ufs_turno2'])} estados "
     f"({', '.join(r['ufs_turno2'])}), somando {mi(r['validos_governador_t2'])} votos válidos em 25/10."),
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

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eleições 2026 · votos por região</title>
<style>
  :root {{
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
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--paper); color: var(--ink);
    font-family: var(--sans); font-size: 17px; line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 0 28px; }}

  header.hero {{ padding: 88px 0 56px; border-bottom: 1px solid var(--hair); }}
  .eyebrow {{
    font-family: var(--mono); font-size: 11.5px; letter-spacing: .16em;
    text-transform: uppercase; color: var(--rust); margin: 0 0 22px;
  }}
  h1 {{
    font-family: var(--serif); font-weight: 600; font-size: clamp(38px, 6.2vw, 68px);
    line-height: 1.02; letter-spacing: -.02em; margin: 0 0 22px; max-width: 20ch;
  }}
  h1 em {{ font-style: italic; color: var(--rust); }}
  .lead {{ max-width: 62ch; color: var(--ink-soft); font-size: 18.5px; margin: 0; }}
  .meta {{
    display: flex; flex-wrap: wrap; gap: 8px 26px; margin-top: 34px;
    font-family: var(--mono); font-size: 12px; color: var(--ink-soft);
  }}
  .meta span::before {{ content: "◦ "; color: var(--hair); }}

  .cards {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr));
    gap: 1px; background: var(--hair); border-block: 1px solid var(--hair);
    margin: 0; padding: 0;
  }}
  .card-stat {{ background: var(--paper); padding: 32px 26px 30px; }}
  .card-stat b {{
    display: block; font-family: var(--mono); font-size: 27px; font-weight: 500;
    letter-spacing: -.03em; color: var(--ink);
  }}
  .card-stat small {{ display: block; color: var(--ink-soft); font-size: 13.5px; margin-top: 6px; }}
  .card-stat small.dim {{ color: #9AA1AB; font-family: var(--mono); font-size: 11.5px; }}

  main {{ padding: 18px 0 40px; }}
  section.card {{ padding: 54px 0; border-bottom: 1px solid var(--hair); }}
  section.card:last-child {{ border-bottom: none; }}
  figure {{ margin: 0; }}
  figure img {{
    width: 100%; height: auto; display: block; border-radius: 3px;
    border: 1px solid var(--hair); background: #fff;
  }}
  figcaption {{ display: grid; grid-template-columns: 240px 1fr; gap: 12px 44px; margin-top: 26px; }}
  figcaption h2 {{
    font-family: var(--serif); font-size: 21px; font-weight: 600; margin: 0;
    letter-spacing: -.01em;
  }}
  figcaption p {{ margin: 0; color: var(--ink-soft); font-size: 15.5px; max-width: 62ch; }}

  section.tabela {{ padding: 60px 0 20px; }}
  .tabela h2 {{
    font-family: var(--serif); font-size: 30px; font-weight: 600; margin: 0 0 8px;
    letter-spacing: -.015em;
  }}
  .tabela p.sub {{ color: var(--ink-soft); margin: 0 0 30px; font-size: 15.5px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  thead th {{
    text-align: left; font-family: var(--mono); font-size: 10.5px; font-weight: 500;
    letter-spacing: .1em; text-transform: uppercase; color: var(--ink-soft);
    padding: 0 12px 12px 0; border-bottom: 1px solid var(--ink); cursor: pointer;
    white-space: nowrap;
  }}
  thead th.num, td.num {{ text-align: right; }}
  tbody td {{ padding: 9px 12px 9px 0; border-bottom: 1px solid var(--hair); }}
  tbody tr:hover td {{ background: var(--paper-2); }}
  td.num {{ font-family: var(--mono); font-size: 12.5px; color: var(--ink); }}
  td.dim {{ color: #9AA1AB; font-size: 13px; }}
  .uf {{ font-family: var(--mono); font-weight: 500; font-size: 13px; }}
  .barra {{
    display: inline-block; height: 6px; width: var(--w); max-width: 60px;
    background: var(--rust); opacity: .55; border-radius: 1px; margin-right: 8px;
    vertical-align: middle;
  }}

  .metodo {{ padding: 60px 0 90px; border-top: 1px solid var(--hair); }}
  .metodo h2 {{ font-family: var(--serif); font-size: 22px; font-weight: 600; margin: 0 0 14px; }}
  .metodo ul {{ margin: 0; padding-left: 18px; color: var(--ink-soft); font-size: 15px; }}
  .metodo li {{ margin-bottom: 7px; }}
  .metodo code {{
    font-family: var(--mono); font-size: 12.5px; background: var(--paper-2);
    padding: 1px 6px; border-radius: 3px; color: var(--ink);
  }}
  footer {{
    padding: 26px 0 60px; color: #9AA1AB; font-family: var(--mono); font-size: 11.5px;
  }}
  @media (max-width: 720px) {{
    figcaption {{ grid-template-columns: 1fr; }}
    header.hero {{ padding-top: 56px; }}
    section.card {{ padding: 40px 0; }}
  }}
</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <p class="eyebrow">Tribunal Superior Eleitoral · Dados Abertos</p>
    <h1>Como o Brasil <em>votou</em> em 2026</h1>
    <p class="lead">
      Votos por seção eleitoral das Eleições Gerais de 2026, agregados por estado, região, cargo
      e município. Os 27 arquivos originais do TSE foram baixados, descompactados e somados:
      {n(r['total_votos'])} votos depositados, {n(r['eleitores'])} eleitores válidos para governador
      e {n(r['pct_bn'],1)}% de votos em branco ou nulo.
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
  <div class="cards">
    {"".join(f'<div class="card-stat"><b>{a}</b><small>{b}</small><small class="dim">{c}</small></div>' for a, b, c in cards)}
  </div>
</div>

<main class="wrap">
{galeria}

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
  tab.tHead.addEventListener('click', (e) => {{
    const th = e.target.closest('th'); if (!th) return;
    const col = +th.dataset.col;
    dir[col] = !dir[col];
    const ordem = [...linhas].sort((a, b) => {{
      const ca = a.cells[col].dataset.v ?? a.cells[col].textContent.trim();
      const cb = b.cells[col].dataset.v ?? b.cells[col].textContent.trim();
      const va = col >= 2 ? num(ca) : ca;
      const vb = col >= 2 ? num(cb) : cb;
      return (va < vb ? -1 : va > vb ? 1 : 0) * (dir[col] ? 1 : -1);
    }});
    ordem.forEach((tr) => corpo.appendChild(tr));
  }});
  linhas.forEach((tr) => {{
    [...tr.cells].forEach((td, i) => {{
      if (i >= 2) td.dataset.v = String(num(td.textContent));
    }});
  }});
}})();
</script>
</body>
</html>
"""

(BASE / "index.html").write_text(html)
print("relatório:", (BASE / "index.html").stat().st_size / 1024, "KB")
