# ELEIÇÕES 2026 — votos por região

Dados abertos do TSE (votação por seção eleitoral, Eleições Gerais 2026), baixados,
descompactados, consolidados e transformados em gráficos.

**Ver online:** https://michelribeiro.github.io/eleicoes-2026/ · segunda página: [urnas.html](https://michelribeiro.github.io/eleicoes-2026/urnas.html)
**Local:** abra [`index.html`](index.html) no navegador (os gráficos já estão prontos em `graficos/`).

## O que tem aqui

```
ELEICOES/
├── index.html                  votos por região: 13 gráficos, tabela por UF e método
├── urnas.html                  quando cada urna fechou: gráfico 14 e tabelas
├── zips/                       27 arquivos originais do TSE (votacao_secao_2026_UF.zip) — 2,6 GB
├── csv/                        27 CSVs descompactados (um por UF) — 18 GB
├── graficos/                   12 gráficos em PNG (200 dpi, 2200 px de largura)
├── dados/
│   ├── agregado.parquet        tabela consolidada (UF×cargo, município×cargo, candidato)
│   ├── apuracao_presidente_2026.csv   apuração do 2º turno presidencial, minuto a minuto
│   ├── urnas_fechamento_2026.parquet  1 linha por urna: fechamento, chegada ao TSE e votos
│   ├── urnas_series_fechamento.csv    série cumulativa por horário de fechamento
│   ├── resumo.json             números usados no relatório
│   ├── votos_por_uf_e_cargo.csv
│   ├── votos_por_municipio.csv
│   ├── votos_por_candidato.csv
│   └── br_ufs.geojson          malha das UFs (IBGE), usada nos mapas
├── apuracao.py                 apuração pela hora de CHEGADA ao TSE + gráfico 13
├── urnas.py                    apuração pela hora de FECHAMENTO da urna + gráfico 14
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
- **Urnas que fecharam depois das 17h05** (registraram voto depois do horário legal): 57.409 urnas,
  14.983.173 votos, **56,2% para Lula** — saldo de +1.860.855, ou 42% da margem final
  - No 1º minuto de apuração Flávio liderava (50,99% × 49,01%); Lula virou às 17h01 e não perdeu mais

## Como refazer

```bash
cd ELEICOES
./.venv/bin/python analise.py     # ~70 s, lê os 18 GB de CSV e gera o parquet
./.venv/bin/python graficos.py    # gera os PNGs e o resumo.json
./.venv/bin/python relatorio.py   # monta o index.html
./.venv/bin/python exportar.py    # (opcional) CSVs de apoio
./.venv/bin/python apuracao.py    # apuração pela chegada ao TSE + gráfico 13
./.venv/bin/python urnas.py       # apuração pelo fechamento da urna + gráfico 14
```

`apuracao.py` usa outra fonte: além da votação por seção (arquivo `votacao_secao_2026_BR.zip`),
baixa o **Detalhe da apuração por seção eleitoral**, que traz o horário de recebimento de cada urna
(`DT_RECEBIMENTO_BU_HOR_TSE`). Os dois são cruzados por UF + município + zona + seção — sem essa
coluna não existe série temporal: a votação por seção só guarda o resultado final.
Os ~2,9 GB ficam em `.cache/` (fora do git) e podem ser apagados depois. Para não baixar de novo:

```bash
TSE_CACHE=/caminho/do/cache ./.venv/bin/python apuracao.py --forcar
TSE_CACHE=/caminho/do/cache ./.venv/bin/python urnas.py --forcar
```

`urnas.py` usa o dataset **"Resultados — 2026 — Boletim de Urna"** (28 arquivos `bweb_2t_UF_*.zip`),
que traz `DT_ENCERRAMENTO`, `DT_ABERTURA` e `DT_BU_RECEBIDO` de cada urna — é o que permite medir
"voto depois das 17h" (a urna que fechou com fila). Os horários são locais; o fuso de cada município
é inferido do horário legal de fechamento. O CSV extraído (~1 GB) é apagado no fim; ficam só os zips e
o parquet de 1 linha por urna.

Para baixar de novo, os arquivos estão em
`https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_<UF>.zip`
(UFs: AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO).

## Definições

- **Votos válidos** = nominais + legenda (exclui brancos e nulos). **Depositados** = tudo.
- Voto de legenda: código de candidato `-3`; branco/nulo: `-1`.
- A comparação entre estados usa o voto para **governador**, a única escolha em que cada
  eleitor deposita exatamente um voto (senador tem duas vagas por UF).
- Não há dados de abstenção/comparecimento neste conjunto do TSE.
