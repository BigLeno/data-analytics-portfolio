"""
app.py - Dashboard interativo (Streamlit + Plotly) da base tratada AprovaEdu.

Gráficos são Plotly interativos (hover/zoom) — não imagens. As agregações de Q1 e
Q3 vêm da camada SQL (DuckDB, `src/queries.py`) sobre os Parquet; Q2 é calculada em
Pandas. Rodar: `streamlit run dashboard/app.py` (ou `docker compose up --build`).

Observação: os dados disponíveis são amostrais — as análises são demonstração de
método (ver README › Escopo dos dados).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = BASE_DIR / "data" / "final"
sys.path.insert(0, str(BASE_DIR / "src"))

# Paleta categórica validada (colorblind-safe) + tokens de tinta
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"

TABELAS = ["professores", "estudantes", "ofertas_curso", "matriculas", "aprovacoes",
           "simulados", "resultados_sim", "aulas", "presencas_aulas"]


# --------------------------------------------------------------------------- #
# Dados (cacheados)
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner=False)
def carregar_base() -> dict[str, pd.DataFrame] | None:
    if any(not (FINAL_DIR / f"{t}.parquet").exists() for t in TABELAS):
        return None
    return {t: pd.read_parquet(FINAL_DIR / f"{t}.parquet") for t in TABELAS}


@st.cache_data(show_spinner=False)
def q1_por_ano() -> pd.DataFrame:
    import queries
    return queries.aprovacoes_por_ano(FINAL_DIR)


@st.cache_data(show_spinner=False)
def q3_por_materia() -> pd.DataFrame:
    import queries
    return queries.desempenho_por_materia(FINAL_DIR)


@st.cache_data(show_spinner=False)
def avaliar_modelo() -> dict:
    import model
    return model.avaliar(FINAL_DIR)


def resumo_presenca(presencas: pd.DataFrame, aprovacoes: pd.DataFrame) -> pd.DataFrame:
    p = presencas.copy()
    p["compareceu"] = p["status_presenca"].isin(["Presente", "Atrasado"])
    taxa = p.groupby("aluno_id")["compareceu"].mean().reset_index(name="taxa")
    taxa["grupo"] = taxa["aluno_id"].isin(set(aprovacoes["aluno_id"])).map(
        {True: "Aprovado", False: "Não aprovado"})
    r = taxa.groupby("grupo")["taxa"].agg(media="mean", alunos="count").reset_index()
    r["media_pct"] = (r["media"] * 100).round(1)
    return r


# --------------------------------------------------------------------------- #
# Layout base dos gráficos (eixo único, grade recessiva, tipografia sans)
# --------------------------------------------------------------------------- #

def _fig(traces, titulo: str, x: str = "", y: str = "", altura: int = 340) -> go.Figure:
    fig = go.Figure(traces)
    fig.update_layout(
        title=dict(text=titulo, x=0, font=dict(size=15, color=INK)),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK),
        plot_bgcolor=SURF, paper_bgcolor=SURF, height=altura,
        margin=dict(l=10, r=10, t=44, b=10), showlegend=False,
        xaxis_title=x, yaxis_title=y, hoverlabel=dict(font_size=12),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    return fig


def fig_aprovacoes(df: pd.DataFrame) -> go.Figure:
    t = go.Bar(x=df["ano"].astype(int), y=df["aprovados"], marker_color=BLUE,
               text=df["aprovados"], textposition="outside",
               hovertemplate="%{x}: %{y} aprovados<extra></extra>")
    return _fig(t, "Aprovações por ano", y="alunos aprovados")


def fig_nota(df: pd.DataFrame) -> go.Figure:
    t = go.Scatter(x=df["ano"].astype(int), y=df["nota_media"], mode="lines+markers+text",
                   line=dict(color=BLUE, width=2), marker=dict(size=9),
                   text=[f"{v:.0f}" for v in df["nota_media"]], textposition="top center",
                   hovertemplate="%{x}: nota média %{y}<extra></extra>")
    return _fig(t, "Nota final média por ano", y="pontos")


def fig_presenca(resumo: pd.DataFrame) -> go.Figure:
    cores = [BLUE if g == "Aprovado" else ORANGE for g in resumo["grupo"]]
    t = go.Bar(x=resumo["grupo"], y=resumo["media_pct"], marker_color=cores,
               text=[f"{v:.1f}% (n={n})" for v, n in zip(resumo["media_pct"], resumo["alunos"])],
               textposition="outside", hovertemplate="%{x}: %{y}% presença média<extra></extra>")
    fig = _fig(t, "Taxa média de presença por desfecho", y="presença média (%)")
    fig.update_yaxes(range=[0, 100])
    return fig


def fig_materia(df: pd.DataFrame) -> go.Figure:
    d = df.sort_values("nota_media")
    t = go.Bar(x=d["nota_media"], y=d["materia"], orientation="h", marker_color=BLUE,
               text=[f"{v:.1f} (n={n})" for v, n in zip(d["nota_media"], d["provas"])],
               textposition="outside", hovertemplate="%{y}: nota média %{x}<extra></extra>")
    return _fig(t, "Nota média em simulados por matéria", x="nota média (0–100)")


# --- Insights sobre tabelas completas (conclusões válidas, sem ressalva amostral) ---

def fig_universidades(aprovacoes: pd.DataFrame) -> go.Figure:
    s = aprovacoes["universidade"].value_counts().sort_values()
    t = go.Bar(x=s.values, y=s.index, orientation="h", marker_color=BLUE,
               text=s.values, textposition="outside",
               hovertemplate="%{y}: %{x} aprovações<extra></extra>")
    return _fig(t, "Aprovações por universidade", x="nº de aprovações", altura=380)


def fig_tipo_vaga(aprovacoes: pd.DataFrame) -> go.Figure:
    s = aprovacoes["modalidade_vaga"].value_counts()
    t = go.Bar(x=s.index, y=s.values, marker_color=BLUE, text=s.values, textposition="outside",
               hovertemplate="%{x}: %{y} aprovações<extra></extra>")
    return _fig(t, "Aprovações por tipo de vaga", y="nº de aprovações")


def fig_modalidade_ano(ofertas: pd.DataFrame) -> go.Figure:
    mix = pd.crosstab(ofertas["ano"], ofertas["modalidade"])
    cores = {"Presencial": BLUE, "Híbrido": "#eda100", "Online": "#1baf7a"}
    traces = [go.Bar(name=c, x=mix.index.astype(int), y=mix[c], marker_color=cores.get(c, MUTED),
                     hovertemplate=f"{c} %{{x}}: %{{y}} ofertas<extra></extra>")
              for c in ["Presencial", "Híbrido", "Online"] if c in mix.columns]
    fig = _fig(traces, "Ofertas por modalidade e ano", y="nº de ofertas")
    fig.update_layout(barmode="stack", showlegend=True,
                      legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
    return fig


# --- Score de propensão (modelo scikit-learn) ---

def fig_importancia(coefs: pd.Series) -> go.Figure:
    top = coefs.head(10).sort_values()
    cores = [BLUE if v >= 0 else ORANGE for v in top.values]
    t = go.Bar(x=top.values, y=top.index, orientation="h", marker_color=cores,
               hovertemplate="%{y}: %{x:.2f}<extra></extra>")
    fig = _fig(t, "Coeficientes da regressão logística (↑ aprovação em azul)",
               x="coeficiente (log-odds)", altura=380)
    fig.add_vline(x=0, line_color=MUTED, line_width=1)
    return fig


def fig_score_dist(scores: pd.DataFrame) -> go.Figure:
    ap1 = scores.loc[scores["aprovado"] == 1, "score"]
    ap0 = scores.loc[scores["aprovado"] == 0, "score"]
    traces = [go.Histogram(x=ap1, name="Aprovado", marker_color=BLUE, opacity=0.65, nbinsx=12),
              go.Histogram(x=ap0, name="Não aprovado", marker_color=ORANGE, opacity=0.65, nbinsx=12)]
    fig = _fig(traces, "Distribuição do score por desfecho real",
               x="score de propensão (0–1)", y="alunos")
    fig.update_layout(barmode="overlay", showlegend=True,
                      legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
    return fig


# --------------------------------------------------------------------------- #
# Aplicação
# --------------------------------------------------------------------------- #

def main() -> None:
    st.set_page_config(page_title="AprovaEdu Analytics", page_icon="📊", layout="wide")

    base = carregar_base()
    if base is None:
        st.title("📊 AprovaEdu Analytics")
        st.error(
            "Base tratada não encontrada em `data/final/`.\n\n"
            "Rode o pipeline antes de abrir o painel:\n\n"
            "```\npython src/extract.py\npython src/transform.py\n```"
        )
        st.stop()

    aprov, pres = base["aprovacoes"], base["presencas_aulas"]

    # ---- Sidebar ----
    with st.sidebar:
        st.header("📊 AprovaEdu")
        st.caption("Painel analítico de cursinho pré-vestibular (2021–2025).")
        st.divider()
        q1 = q1_por_ano()
        anos = st.multiselect("Anos (Q1)", q1["ano"].astype(int).tolist(),
                              default=q1["ano"].astype(int).tolist())
        st.divider()
        st.subheader("Qualidade dos dados")
        st.success("Base validada com Pandera (schemas em `src/validation.py`).", icon="✔️")
        st.caption("Q1 e Q3 são consultadas via SQL (DuckDB) sobre os Parquet.")

    # ---- Cabeçalho + escopo ----
    st.title("📊 AprovaEdu Analytics")
    st.warning(
        "**Demonstração de método.** Dados amostrais (5 tabelas truncadas em 500 linhas), "
        "com sobreposição mínima entre matrícula, presença e aprovação. Os números ilustram "
        "o método — não são conclusões de negócio. Detalhes no `README.md` › *Escopo dos dados*.",
        icon="⚠️",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estudantes", f"{base['estudantes']['aluno_id'].nunique():,}".replace(",", "."))
    c2.metric("Aprovações", f"{len(aprov):,}".replace(",", "."))
    c3.metric("Matrículas", f"{len(base['matriculas']):,}".replace(",", "."))
    c4.metric("Período", f"{int(aprov['ano_vestibular'].min())}–{int(aprov['ano_vestibular'].max())}")

    aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
        "Q1 · Aprovação por ano", "Q2 · Presença × aprovação",
        "Q3 · Desempenho por matéria", "Q4 · Recomendações",
        "★ Insights (dados completos)", "🧠 Score (ML)",
    ])

    with aba1:
        q1f = q1[q1["ano"].astype(int).isin(anos)] if anos else q1
        col1, col2 = st.columns(2)
        col1.plotly_chart(fig_aprovacoes(q1f), use_container_width=True)
        col2.plotly_chart(fig_nota(q1f), use_container_width=True)
        st.caption("A *taxa* (aprovados ÷ matriculados) exige a base completa — o denominador "
                   "amostral é truncado. Fonte: consulta SQL (DuckDB).")
        with st.expander("Ver dados (tabela)"):
            st.dataframe(q1f, hide_index=True, use_container_width=True)

    with aba2:
        resumo = resumo_presenca(pres, aprov)
        st.plotly_chart(fig_presenca(resumo), use_container_width=True)
        st.caption("Direção plausível (aprovados com presença maior), mas amostra ínfima não "
                   "permite afirmar associação.")
        with st.expander("Ver dados (tabela)"):
            st.dataframe(resumo[["grupo", "media_pct", "alunos"]], hide_index=True,
                         use_container_width=True)

    with aba3:
        q3 = q3_por_materia()
        st.plotly_chart(fig_materia(q3), use_container_width=True)
        st.caption("Ranking ilustrativo — a amostra cobre poucas matérias. Fonte: consulta SQL (DuckDB).")
        with st.expander("Ver dados (tabela)"):
            st.dataframe(q3, hide_index=True, use_container_width=True)

    with aba4:
        st.subheader("Recomendações para a coordenação")
        st.markdown(
            "1. **Monitorar presença como sinal de risco** — acompanhar frequência por "
            "aluno/turma e acionar quedas.\n"
            "2. **Reforçar as matérias de menor nota média** em simulados (carga horária, revisões).\n"
            "3. **Padronizar a captura de dados na origem** — reduz o retrabalho de limpeza e "
            "melhora a qualidade decisória.\n"
            "4. **Instrumentar a taxa de aprovação por coorte** (ingresso × vestibular) para "
            "separar efeitos de turma, matéria e presença."
        )
        st.info("Recomendações derivadas do método; a confirmar na base completa.", icon="🧭")

    with aba5:
        st.success(
            "Estas análises usam apenas tabelas **completas** (`aprovacoes`, `ofertas_curso`) — "
            "valem como **conclusões**, sem a ressalva amostral das abas Q1–Q4.", icon="✅",
        )
        of = base["ofertas_curso"]
        col1, col2 = st.columns(2)
        col1.plotly_chart(fig_universidades(aprov), use_container_width=True)
        col2.plotly_chart(fig_tipo_vaga(aprov), use_container_width=True)
        st.plotly_chart(fig_modalidade_ano(of), use_container_width=True)
        st.caption("Público majoritariamente cotista (cotas somadas > ampla concorrência), "
                   "destino concentrado em públicas locais (UECE, UFC) e mix de modalidade "
                   "que varia por ano sem tendência linear.")

    with aba6:
        st.warning(
            "Modelo em **demonstração**: o alvo é confiável (aprovações completas), mas as "
            "features vêm de tabelas amostrais → nesta amostra o sinal fica **próximo do acaso** "
            "(AUC ~0,5). O entregável é o *pipeline* interpretável, pronto para a base completa.",
            icon="⚠️",
        )
        m = avaliar_modelo()
        k1, k2, k3 = st.columns(3)
        k1.metric("Alunos (com features)", f"{m['n']}")
        k2.metric("AUC · Regressão logística", f"{m['auc_logit'][0]:.3f}")
        k3.metric("AUC · Random forest", f"{m['auc_rf'][0]:.3f}")
        col1, col2 = st.columns(2)
        col1.plotly_chart(fig_importancia(m["coefs"]), use_container_width=True)
        col2.plotly_chart(fig_score_dist(m["scores"]), use_container_width=True)
        st.markdown("**Segmentação por faixa de score** — a faixa ordena a taxa real de aprovação?")
        st.dataframe(m["segmentacao"], hide_index=True, use_container_width=True)
        with st.expander("Ver score por aluno"):
            st.dataframe(m["scores"].sort_values("score", ascending=False),
                         hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
