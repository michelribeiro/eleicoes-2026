# ELEIÇÕES 2026 — votos por região

Dados abertos do TSE (votação por seção eleitoral, Eleições Gerais 2026), baixados,
descompactados, consolidados e transformados em gráficos.

**Abra o relatório:** [`index.html`](index.html) (abra no navegador — os gráficos já estão prontos em `graficos/`).

## O que tem aqui

```
ELEICOES/
├── index.html                  relatório com todos os gráficos, tabela e método
├── zips/                       27 arquivos originais do TSE (votacao_secao_2026_UF.zip) — 2,6 GB
├── csv/                        27 CSVs descompactados (um por UF) — 18 GB
├── graficos/                   12 gráficos em PNG (200 dpi, 2200 px de largura)
├── dados/
│   ├── agregado.parquet        tabela consolidada (UF×cargo, município×cargo, candidato)
│   ├── resumo.json             números usados no relatório
│   ├── votos_por_uf_e_cargo.csv
│   ├── votos_por_municipio.csv
│   ├── votos_por_candidato.csv
│   └── br_ufs.geojson          malha das UFs (IBGE), usada nos mapas
├── analise.py                  CSVs → dados/agregado.parquet
├── graficos.py                 agregado → graficos/*.png + dados/resumo.json
├── relatorio.py                resumo.json → index.html
├── exportar.py                 agregado → CSVs de apoio
└── .venv/                      ambiente Python (pandas, duckdb, matplotlib, pyarrow)
```

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

## Números-chave

- **623.842.425** votos depositados no 1º turno (todos os cargos)
- **112.197.244** votos válidos para governador (medida de eleitor válido)
- **12,3%** dos votos em branco (6,0%) ou nulo (6,3%)
- **6** estados com 2º turno para governador, somando 9,4 mi de votos válidos em 25/10/2026

## Como refazer

```bash
cd ELEICOES
./.venv/bin/python analise.py     # ~70 s, lê os 18 GB de CSV e gera o parquet
./.venv/bin/python graficos.py    # gera os PNGs e o resumo.json
./.venv/bin/python relatorio.py   # monta o index.html
./.venv/bin/python exportar.py    # (opcional) CSVs de apoio
```

Para baixar de novo, os arquivos estão em
`https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_<UF>.zip`
(UFs: AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO).

## Definições

- **Votos válidos** = nominais + legenda (exclui brancos e nulos). **Depositados** = tudo.
- Voto de legenda: código de candidato `-3`; branco/nulo: `-1`.
- A comparação entre estados usa o voto para **governador**, a única escolha em que cada
  eleitor deposita exatamente um voto (senador tem duas vagas por UF).
- Não há dados de abstenção/comparecimento neste conjunto do TSE.
