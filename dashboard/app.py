"""
app.py - Dashboard interativo (Streamlit) da base tratada AprovaEdu Analytics.

Lê a base tratada em data/final/ e apresenta as 4 análises de forma interativa.
Rodar: `streamlit run dashboard/app.py`  (ou via `docker compose up --build`).

Observação: as análises são uma demonstração de método — os dados disponíveis
são amostrais (ver README › Escopo dos dados).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = BASE_DIR / "data" / "final"

# Paleta categórica validada (colorblind-safe, ordem fixa) + tokens de tinta
BLUE, AQUA, ORANGE = "#2a78d6", "#1baf7a", "#eb6834"
INK, MUTED, GRID, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"

TABELAS = ["professores", "estudantes", "ofertas_curso", "matriculas", "aprovacoes",
           "simulados", "resultados_sim", "aulas", "presencas_aulas"]


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #

def _carregar(final_dir: Path) -> dict[str, pd.DataFrame]:
    """Lê os parquet da base tratada. Puro (sem Streamlit) — testável."""
    return {t: pd.read_parquet(final_dir / f"{t}.parquet") for t in TABELAS}


@st.cache_data(show_spinner=False)
def carregar_base() -> dict[str, pd.DataFrame] | None:
    faltando = [t for t in TABELAS if not (FINAL_DIR / f"{t}.parquet").exists()]
    if faltando:
        return None
    return _carregar(FINAL_DIR)


# --------------------------------------------------------------------------- #
# Layout base dos gráficos (eixo único, grade recessiva, tipografia sans)
# --------------------------------------------------------------------------- #

def _layout(fig: go.Figure, titulo: str, x: str = "", y: str = "") -> go.Figure:
    fig.update_layout(
        title=dict(text=titulo, x=0, font=dict(size=16, color=INK)),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK),
        plot_bgcolor=SURF, paper_bgcolor=SURF,
        margin=dict(l=10, r=10, t=48, b=10), showlegend=False,
        xaxis_title=x, yaxis_title=y,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    return fig


# --------------------------------------------------------------------------- #
# Construtores de figura (puros: recebem DataFrame, devolvem go.Figure)
# --------------------------------------------------------------------------- #

def fig_aprovacoes_ano(aprovacoes: pd.DataFrame) -> go.Figure:
    s = aprovacoes.groupby("ano_vestibular")["aluno_id"].nunique()
    fig = go.Figure(go.Bar(
        x=s.index.astype(int), y=s.values, marker_color=BLUE,
        text=s.values, textposition="outside",
        hovertemplate="%{x}: %{y} aprovados<extra></extra>",
    ))
    return _layout(fig, "Aprovações por ano", y="alunos aprovados")


def fig_nota_ano(aprovacoes: pd.DataFrame) -> go.Figure:
    s = aprovacoes.groupby("ano_vestibular")["nota_final_vestibular"].mean().round(1)
    fig = go.Figure(go.Scatter(
        x=s.index.astype(int), y=s.values, mode="lines+markers+text",
        line=dict(color=BLUE, width=2), marker=dict(size=9),
        text=[f"{v:.0f}" for v in s.values], textposition="top center",
        hovertemplate="%{x}: nota média %{y}<extra></extra>",
    ))
    return _layout(fig, "Nota final média no vestibular por ano", y="pontos")


def fig_presenca_aprovacao(presencas: pd.DataFrame, aprovacoes: pd.DataFrame) -> go.Figure:
    p = presencas.copy()
    p["compareceu"] = p["status_presenca"].isin(["Presente", "Atrasado"])
    taxa = p.groupby("aluno_id")["compareceu"].mean().reset_index(name="taxa")
    taxa["aprovado"] = taxa["aluno_id"].isin(set(aprovacoes["aluno_id"]))
    resumo = taxa.groupby("aprovado")["taxa"].agg(media="mean", n="count")
    cats = {False: "Não aprovado", True: "Aprovado"}
    x = [cats[k] for k in resumo.index]
    y = (resumo["media"] * 100).round(1)
    fig = go.Figure(go.Bar(
        x=x, y=y, marker_color=[ORANGE if not k else BLUE for k in resumo.index],
        text=[f"{v:.1f}% (n={n})" for v, n in zip(y, resumo['n'])], textposition="outside",
        hovertemplate="%{x}: %{y}% de presença média<extra></extra>",
    ))
    fig.update_yaxes(range=[0, 100])
    return _layout(fig, "Taxa média de presença por desfecho", y="presença média (%)")


def fig_desempenho_materia(resultados: pd.DataFrame, simulados: pd.DataFrame) -> go.Figure:
    m = resultados.merge(simulados[["simulado_id", "materia"]], on="simulado_id", how="left")
    d = (m.dropna(subset=["nota"]).groupby("materia")["nota"]
         .agg(media="mean", n="count").sort_values("media"))
    fig = go.Figure(go.Bar(
        x=d["media"].round(1), y=d.index, orientation="h", marker_color=BLUE,
        text=[f"{v:.1f} (n={n})" for v, n in zip(d['media'], d['n'])], textposition="outside",
        hovertemplate="%{y}: nota média %{x}<extra></extra>",
    ))
    return _layout(fig, "Nota média em simulados por matéria", x="nota média (0–100)")


# --------------------------------------------------------------------------- #
# Aplicação
# --------------------------------------------------------------------------- #

def main() -> None:
    st.set_page_config(page_title="AprovaEdu Analytics", page_icon="📊", layout="wide")
    st.title("📊 AprovaEdu Analytics")
    st.caption("Painel analítico de um cursinho pré-vestibular (2021–2025) — base tratada.")

    base = carregar_base()
    if base is None:
        st.error(
            "Base tratada não encontrada em `data/final/`.\n\n"
            "Rode o pipeline antes de abrir o painel:\n\n"
            "```\npython src/extract.py\npython src/transform.py\n```"
        )
        st.stop()

    st.warning(
        "**Demonstração de método.** Os dados disponíveis são amostrais (5 tabelas "
        "truncadas em 500 linhas), com sobreposição mínima entre matrícula, presença e "
        "aprovação. Os números ilustram o método — não são conclusões de negócio. "
        "Detalhes no `README.md` › *Escopo dos dados*.",
        icon="⚠️",
    )

    aprov, pres = base["aprovacoes"], base["presencas_aulas"]
    res, sim = base["resultados_sim"], base["simulados"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estudantes", f"{base['estudantes']['aluno_id'].nunique():,}".replace(",", "."))
    c2.metric("Aprovações", f"{len(aprov):,}".replace(",", "."))
    c3.metric("Matrículas", f"{len(base['matriculas']):,}".replace(",", "."))
    c4.metric("Anos", f"{int(aprov['ano_vestibular'].min())}–{int(aprov['ano_vestibular'].max())}")

    aba1, aba2, aba3, aba4 = st.tabs([
        "Q1 · Aprovação por ano", "Q2 · Presença × aprovação",
        "Q3 · Desempenho por matéria", "Q4 · Recomendações",
    ])

    with aba1:
        col1, col2 = st.columns(2)
        col1.plotly_chart(fig_aprovacoes_ano(aprov), use_container_width=True)
        col2.plotly_chart(fig_nota_ano(aprov), use_container_width=True)
        st.caption("Volume de aprovações e nota média por ano. A *taxa* (aprovados ÷ "
                   "matriculados) exige a base completa — o denominador amostral é truncado.")

    with aba2:
        st.plotly_chart(fig_presenca_aprovacao(pres, aprov), use_container_width=True)
        st.caption("Direção plausível (aprovados com presença maior), mas amostra ínfima "
                   "não permite afirmar associação.")

    with aba3:
        st.plotly_chart(fig_desempenho_materia(res, sim), use_container_width=True)
        st.caption("Ranking ilustrativo — a amostra cobre poucas matérias (primeiros simulados).")

    with aba4:
        st.markdown(
            "1. **Monitorar presença como sinal de risco** — acompanhar frequência por "
            "aluno/turma e acionar quedas.\n"
            "2. **Reforçar as matérias de menor nota média** em simulados (carga horária, revisões).\n"
            "3. **Padronizar a captura de dados na origem** — reduz o retrabalho de limpeza e "
            "melhora a qualidade decisória.\n"
            "4. **Instrumentar a taxa de aprovação por coorte** (ingresso × vestibular) para "
            "separar efeitos de turma, matéria e presença."
        )


if __name__ == "__main__":
    main()
