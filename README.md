# ELEIÇÕES 2026 — votos por região

Dados abertos do TSE (votação por seção eleitoral, Eleições Gerais 2026), consolidados e
transformados em gráficos.

**Ver online:** https://michelribeiro.github.io/eleicoes-2026/ ·
segunda página: [urnas.html](https://michelribeiro.github.io/eleicoes-2026/urnas.html)

## O que está publicado

```
├── index.html                  votos por região: 13 gráficos, tabela por UF e método
├── urnas.html                  quando cada urna fechou: gráfico 14 e tabelas
├── graficos/                   14 gráficos em PNG (200 dpi, 2200 px de largura)
├── apuracao.py                 apuração pela hora de CHEGADA ao TSE + gráfico 13
├── urnas.py                    apuração pela hora de FECHAMENTO da urna + gráfico 14
├── analise.py                  CSVs do TSE → parquet consolidado
├── graficos.py                 agregado → graficos/*.png + resumo.json
├── relatorio.py                resumo.json → index.html
└── exportar.py                 agregado → CSVs de apoio
```

O site é 100% estático: HTML + PNGs, sem CDN, sem JS de terceiros. Os dados brutos
(27 ZIPs do TSE, 2,6 GB; 27 CSVs, 18 GB) e as tabelas intermediárias **não são versionados** —
são regerados pelos scripts abaixo.

## Gráficos

| Arquivo | O que mostra |
|---|---|
| `01_mapa.png` | Mapas: votos válidos para governador e % de brancos + nulos por UF |
| `02_votos_uf.png` | Votos válidos por estado, coloridos por região |
| `03_brancos_nulos.png` | % de branco + nulo em cada UF vs. média nacional |
| `04_cargos.png` | Votos válidos por cargo (governador, senador, deputado...) |
| `05_governadores.png` | 12 governadores mais votados do país + % no próprio estado |
| `06_senadores.png` | 12 senadores mais votados do país |
| `07_dep_federal.png` | 20 deputados federais mais votados (puxadores de voto) |
| `08_turno2.png` | Os 6 segundos turnos para governador (ES, RN, AM, DF, TO, AC) |
| `09_concentracao.png` | Curva de concentração do voto para deputado federal |
| `10_legendas.png` | Votos de legenda (sem nome) por partido |
| `11_municipios.png` | 15 maiores colégios eleitorais |
| `12_regioes.png` | Peso e aproveitamento do voto por região |
| `13_apuracao_presidente.png` | **A virada do 2º turno presidencial, urna por urna** (chegada ao TSE, 17h → 23h21) |
| `14_urnas_fechamento.png` | **Quem estava na frente pelo horário de FECHAMENTO da urna** (17h → 23h04) |

## Números-chave

- **623.842.425** votos depositados no 1º turno (todos os cargos)
- **112.197.244** votos válidos para governador (medida de eleitor válido)
- **12,3%** dos votos em branco (6,0%) ou nulo (6,3%)
- **6** estados com 2º turno para governador, somando 9,4 mi de votos válidos em 25/10/2026
- **2º turno presidencial**: Lula 51,79% (64.256.232) × Flávio 48,21% (59.826.041) — margem de 3,57 p.p.
  - Flávio liderou das **19h44** (13,9% das urnas) às **20h23** (47,3%); Lula virou e não perdeu mais
  - 90% das urnas apuradas às 21h01; a última urna chegou às 23h21
- **Voto depois das 17h** (urnas que fecharam com fila, medidas pelo horário de fechamento):
  - até **17h59** já estavam 490.836 urnas, com Lula **+4.200.908** — 95% da margem final
  - depois das **18h**: 1.989.395 votos (1,6%), Lula 55% → acrescentaram **+200.259** (5% da margem)
  - a votação acaba às **19h59**; depois só 2 urnas (20h e 23h04, 309 votos)
  - no 1º minuto Flávio liderava (50,99% × 49,01%); Lula virou às 17h01 e não perdeu mais

## Como refazer

```bash
python -m venv .venv && ./.venv/bin/pip install pandas duckdb matplotlib pyarrow
# baixar e descompactar os 27 votacao_secao_2026_<UF>.zip do TSE em csv/
./.venv/bin/python analise.py     # ~70 s, lê os 18 GB de CSV e gera dados/agregado.parquet
./.venv/bin/python graficos.py    # gera os PNGs e dados/resumo.json
./.venv/bin/python relatorio.py   # monta o index.html
./.venv/bin/python exportar.py    # (opcional) CSVs de apoio
./.venv/bin/python apuracao.py    # apuração pela chegada ao TSE + gráfico 13
./.venv/bin/python urnas.py       # apuração pelo fechamento da urna + gráfico 14
```

`apuracao.py` usa outra fonte: além da votação por seção (arquivo `votacao_secao_2026_BR.zip`),
baixa o **Detalhe da apuração por seção eleitoral**, que traz o horário de recebimento de cada urna
(`DT_RECEBIMENTO_BU_HOR_TSE`). Os dois são cruzados por UF + município + zona + seção — sem essa
coluna não existe série temporal: a votação por seção só guarda o resultado final.
O cache (~2,9 GB) fica em `.cache/` e pode ser apontado com `TSE_CACHE=/caminho`.

`urnas.py` usa o dataset **"Resultados — 2026 — Boletim de Urna"** (28 arquivos `bweb_2t_UF_*.zip`),
que traz `DT_ENCERRAMENTO`, `DT_ABERTURA` e `DT_BU_RECEBIDO` de cada urna — é o que permite medir
"voto depois das 17h" (a urna que fechou com fila). Os horários são locais; o fuso de cada município
é inferido do horário legal de fechamento.

Origem dos dados:
`https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_<UF>.zip`
(UFs: AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO).

## Definições

- **Votos válidos** = nominais + legenda (exclui brancos e nulos). **Depositados** = tudo.
- Voto de legenda: código de candidato `-3`; branco/nulo: `-1`.
- A comparação entre estados usa o voto para **governador**, a única escolha em que cada
  eleitor deposita exatamente um voto (senador tem duas vagas por UF).
- Não há dados de abstenção/comparecimento neste conjunto do TSE.
