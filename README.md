# 📊 AprovaEdu Analytics

Pipeline analítico para análise de dados educacionais de cursinho pré-vestibular (2021-2025).

## 🎯 Sobre o Projeto

Projeto de análise de dados educacionais desenvolvido como solução para o desafio técnico da AprovaEdu Analytics. A base de dados contém 5 anos de informações sobre alunos, professores, simulados, frequência e aprovações no vestibular.

## 🛠️ Stack

- **Python 3.11+**
- **Pandas / NumPy** — Manipulação de dados
- **DuckDB** — Consultas SQL in-memory
- **Pandera** — Validação de schema
- **Plotly / Streamlit** — Visualização
- **Docker** — Ambiente reproduzível

## 🚀 Como Executar

### Opção 1: Com Docker
```bash
docker-compose up --build
# Dashboard disponível em http://localhost:8501
```