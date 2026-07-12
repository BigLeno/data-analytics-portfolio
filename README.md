# 📊 AprovaEdu Analytics

Pipeline analítico para análise de dados educacionais de cursinho pré-vestibular (2021-2025).

## 🎯 Sobre o Projeto

Projeto de análise de dados educacionais desenvolvido como solução para o desafio técnico da AprovaEdu Analytics. A base de dados contém 5 anos de informações sobre alunos, professores, simulados, frequência e aprovações no vestibular.

## 🛠️ Stack

- **Python 3.11+**
- **Pandas / NumPy** — Manipulação de dados
- **DuckDB** — Consultas SQL in-memory
- **Pandera** — Validação de schema
- **scikit-learn** — Modelo de propensão (score)
- **Plotly / Streamlit** — Visualização
- **Docker** — Ambiente reproduzível

## ⚠️ Escopo dos dados (leia antes de interpretar os resultados)

O arquivo fornecido `data/raw/base_pre_vestibular_dicionario_amostras.xlsx` é um **dicionário de dados + amostra** — **não** a base completa. Comparando o número de linhas de cada aba com o total declarado na própria aba `Resumo` do dicionário:

| Tabela          | Linhas no XLSX | Base completa (aba`Resumo`) | Situação           |
| --------------- | -------------: | ----------------------------: | -------------------- |
| professores     |             35 |                            35 | ✅ Completa          |
| ofertas_curso   |            220 |                           220 | ✅ Completa          |
| simulados       |            165 |                           165 | ✅ Completa          |
| aprovacoes      |            354 |                           354 | ✅ Completa          |
| estudantes      |            500 |                           812 | ✂️ Truncada em 500 |
| matriculas      |            500 |                         9.452 | ✂️ Truncada em 500 |
| aulas           |            500 |                         2.418 | ✂️ Truncada em 500 |
| resultados_sim  |            500 |                        21.510 | ✂️ Truncada em 500 |
| presencas_aulas |            500 |                        74.997 | ✂️ Truncada em 500 |

Pontos importantes:

1. **A limitação está no arquivo, não no código.** O `extract.py` lê **todas** as linhas presentes em cada aba (sem `nrows`/`skiprows`); ele extrai 500 porque 500 é o que o arquivo contém. Nenhuma mudança no código faz surgir mais dados.
2. **É truncamento por ordem, não amostragem aleatória.** Nas tabelas cortadas, os IDs são exatamente os primeiros sequenciais (`M0000001…M0000500`, `R00000001…R00000500`, …). Por isso as tabelas cobrem fatias de entidades quase disjuntas.
3. **Isso é por design.** A aba `Resumo` declara em cada linha: *"A planilha traz amostra; o CSV contém a base completa"*. A base completa é distribuída **à parte, como CSVs**.

**Consequência para as análises:** os cruzamentos entre matrícula, presença e aprovação têm sobreposição mínima (apenas **1 aluno** possui os três dados). Portanto, o notebook `02_analise.ipynb` entrega uma **demonstração de método**, e não conclusões de negócio.

**Como obter resultados válidos:** basta colocar os CSVs da base completa em `data/` e reexecutar o pipeline — todo o código (`extract` → `cleaning` → `transform`) e os notebooks já estão prontos para recebê-los.

## 📁 Estrutura do Projeto

```
data/
  raw/          # origem: XLSX (dicionário + amostra) e PDF do desafio
  processed/    # CSVs extraídos, texto fiel ao XLSX (gerado por extract.py)
    _meta/      # abas de documentação (Resumo, Problemas_Qualidade)
  final/        # base tratada em Parquet + CSV (gerado por transform.py)
                # + _relatorio_tratamento.md com as decisões e contagens
src/
  extract.py    # Etapa 1: XLSX -> CSV (dtype=str, sem alterar nada)
  cleaning.py   # normalizadores puros + dicionários canônicos
  transform.py  # Etapa 2: tratamento e estruturação da base analítica
  validation.py # schemas Pandera (contrato da base tratada)
  queries.py    # camada analítica em SQL (DuckDB) sobre os Parquet
  features.py   # engenharia de atributos por aluno (para o modelo)
notebooks/
  01_tratamento.ipynb   # extração, perfilamento e tratamento (documentado)
  02_analise.ipynb      # as 4 análises obrigatórias
  03_insights.ipynb     # insights complementares sobre as tabelas completas
  04_modelo.ipynb       # score de propensão à aprovação (scikit-learn)
dashboard/      # app Streamlit (em desenvolvimento)
reports/        # relatório final (em desenvolvimento)
```

> `data/raw`, `data/processed` e `data/final` são ignorados pelo Git; as saídas são regeneráveis pelo pipeline.

## 🚀 Como Executar

### Setup

```bash
python -m venv env
# Windows: env\Scripts\activate | Linux/Mac: source env/bin/activate
pip install -r requirements.txt
```

### Dados (obrigatório)

O XLSX de origem **não é versionado** — dado bruto não deve ir para o repositório (boa prática), e a base é distribuída à parte. Antes de rodar o pipeline, coloque o arquivo de origem em `data/raw/`:

```
data/raw/base_pre_vestibular_dicionario_amostras.xlsx
```

As pastas `data/processed/` e `data/final/` são criadas automaticamente pelo pipeline.

### Pipeline (do bruto à base tratada)

```bash
python src/extract.py     # XLSX -> data/processed/*.csv
python src/transform.py   # -> data/final/*.parquet + *.csv + relatório
```

### Notebooks (documentação e análises)

Abra `notebooks/01_tratamento.ipynb` e `notebooks/02_analise.ipynb` de uma destas formas:

- **VS Code** — abra o arquivo `.ipynb`, selecione o kernel (o ambiente `env`) e clique em **Run All**.
- **Jupyter no navegador** — rode um dos comandos abaixo; ele abre uma aba no navegador, daí é só navegar até a pasta `notebooks/`:

```bash
jupyter lab        # interface mais completa
# ou, mais simples:
jupyter notebook
```

### Docker

O container **executa o pipeline (extract → transform) e sobe o dashboard automaticamente** — basta o XLSX estar em `data/raw/` (ver *Dados*).

```bash
docker compose up --build   # dashboard em http://localhost:8501
# Docker V1 antigo: docker-compose up --build
```

## 🔍 Decisões técnicas e analíticas

Documentadas em detalhe em `notebooks/01_tratamento.ipynb` e em `data/final/_relatorio_tratamento.md`. Resumo:

- **Camada bruta fiel** — a extração lê tudo como texto (`dtype=str`, `keep_default_na=False`); nada é "limpo" antes da etapa de tratamento.
- **Datas em formatos mistos** → `datetime`; ambiguidade `dd/mm` vs `mm/dd` resolvida pela magnitude dos campos, com padrão brasileiro (`dd/mm`) no caso ambíguo.
- **Categorias inconsistentes** → dicionário canônico por *fold* (minúsculo, sem acento, sem pontuação), unificando caixa/acento/abreviação.
- **Denormalização** → `professor_id` é a fonte de verdade; o nome informado nos fatos é conferido com a dimensão e removido.
- **Duplicidade** → em Aprovações, removem-se as linhas marcadas `chamada = "Cadastro duplicado?"` (coincidem 1:1 com duplicatas por chave de negócio).
- **Outliers** → nota de simulado fora de `[0, 100]` vira nula; inconsistências de tempo/acertos são sinalizadas, não descartadas.
- **Faltantes** → medidas (notas) não são imputadas; categóricas viram `"Não informado"` quando faz sentido de negócio.
- **Validação (Pandera)** → `src/validation.py` define o "contrato" da base tratada (PKs únicas, faixas numéricas e categorias canônicas); o `transform.py` roda a validação e registra o resultado no relatório.
- **Camada SQL (DuckDB)** → `src/queries.py` responde às perguntas via SQL sobre os Parquet, como alternativa de modelagem analítica às agregações em Pandas.
- **Score preditivo (scikit-learn)** → `src/features.py` + `notebooks/04_modelo.ipynb` treinam um score de propensão à aprovação (Pipeline com pré-processamento, validação cruzada e interpretação). O alvo é confiável (aprovações é tabela completa); na amostra o sinal fica próximo do acaso — o entregável é o pipeline, pronto para a base completa.

## ❓ Perguntas obrigatórias

Respondidas em `notebooks/02_analise.ipynb` (como demonstração de método — ver *Escopo dos dados*):

1. Evolução da taxa de aprovação ao longo dos anos.
2. Relação entre presença nas aulas e aprovação no vestibular.
3. Cursos/matérias com melhor desempenho.
4. Recomendações práticas para a coordenação.
