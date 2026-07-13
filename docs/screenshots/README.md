# Screenshots do dashboard

Coloque aqui os prints do dashboard rodando, com **exatamente estes nomes** (o
`README.md` principal já aponta para eles):

| Arquivo | Aba a capturar |
|---|---|
| `01-visao-geral.png` | Topo + aba **Q1 · Aprovação por ano** (título, KPIs, aviso, os 2 gráficos) |
| `02-q2-presenca.png` | Aba **Q2 · Presença × aprovação** |
| `03-q3-materia.png` | Aba **Q3 · Desempenho por matéria** |
| `04-insights.png` | Aba **★ Insights (dados completos)** |
| `05-score-ml.png` | Aba **🧠 Score (ML)** |

## Como gerar

1. Suba o dashboard: `docker compose up --build` (ou `streamlit run dashboard/app.py`).
2. Abra http://localhost:8501 no navegador.
3. Em cada aba, tire o print (Windows: `Win + Shift + S`) e salve com o nome da tabela acima, em PNG, nesta pasta.
4. Commite junto com o README.

> Se pular algum print, remova a linha correspondente na seção *Demonstração* do
> `README.md` principal para não ficar imagem quebrada.
