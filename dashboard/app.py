"""
app.py - Dashboard interativo (Streamlit + Plotly) da base tratada AprovaEdu.

Gráficos são Plotly interativos (hover/zoom) — não imagens. As agregações de Q1 e
Q3 vêm da camada SQL (DuckDB, `src/queries.py`) sobre os Parquet; Q2 é calculada em
Pandas. Rodar: `streamlit run dashboard/app.py` (ou `docker compose up --build`).

O painel identifica a fonte da base tratada (`data/final/_fonte.txt`): amostra do
XLSX, base completa ou base fictícia. Sem nenhuma fonte em `data/raw/`, ele gera a
base fictícia sozinho (scripts/gerar_dados_sinteticos.py) e roda o pipeline — é
assim que a demo pública funciona.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
# APROVAEDU_DATA_DIR permite apontar o painel para outra pasta de dados (usado nos testes)
DATA_DIR = Path(os.environ.get("APROVAEDU_DATA_DIR", BASE_DIR / "data"))
FINAL_DIR = DATA_DIR / "final"
RAW_DIR = DATA_DIR / "raw"
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR / "scripts"))

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


def modo_base() -> str:
    """'sintetica', 'completa' ou 'amostra', conforme gravado pelo transform.py."""
    arquivo = FINAL_DIR / "_fonte.txt"
    if arquivo.exists():
        return arquivo.read_text(encoding="utf-8").strip()
    # bases tratadas antes do marcador: a amostra tinha no máx. 500 estudantes
    est = FINAL_DIR / "estudantes.parquet"
    return "completa" if est.exists() and len(pd.read_parquet(est)) > 500 else "amostra"


def ha_fonte_bruta() -> bool:
    """True se há XLSX de amostra ou algum CSV em data/raw/ (não sobrescrever dados reais)."""
    import extract
    return (RAW_DIR / extract.XLSX_PATH.name).exists() or \
        any((RAW_DIR / f).exists() for f in extract.CSV_COMPLETOS)


def preparar_demo() -> None:
    """Gera a base fictícia em data/raw/ e roda extract + transform."""
    import extract
    import gerar_dados_sinteticos as gds
    import transform
    extract.RAW_DIR, extract.OUTPUT_DIR = RAW_DIR, DATA_DIR / "processed"
    extract.XLSX_PATH = RAW_DIR / extract.XLSX_PATH.name
    transform.IN_DIR, transform.OUT_DIR = DATA_DIR / "processed", FINAL_DIR
    gds.gerar(RAW_DIR)
    extract.main()
    transform.main()
    st.cache_data.clear()


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


@st.cache_data(show_spinner=False)
def importancia_modelo() -> pd.DataFrame:
    import model
    return model.importancia_variaveis(FINAL_DIR)


def taxa_por_permanencia(matriculas: pd.DataFrame, aprovacoes: pd.DataFrame) -> pd.DataFrame:
    """Taxa de aprovação por nº de anos distintos com matrícula."""
    alunos = matriculas.groupby("aluno_id").agg(anos=("ano", "nunique"))
    alunos["aprovado"] = alunos.index.isin(set(aprovacoes["aluno_id"]))
    return alunos.groupby("anos")["aprovado"].agg(taxa="mean", n="count")


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
    fig = _fig(t, "Aprovações por ano", y="alunos aprovados")
    fig.update_yaxes(range=[0, df["aprovados"].max() * 1.18])  # folga p/ rótulo não cortar
    return fig


def fig_taxa(df: pd.DataFrame) -> go.Figure:
    t = go.Scatter(x=df["ano"].astype(int), y=df["taxa_pct"], mode="lines+markers+text",
                   line=dict(color=BLUE, width=2), marker=dict(size=9),
                   text=[f"{v:.1f}%" for v in df["taxa_pct"]], textposition="top center",
                   hovertemplate="%{x}: taxa %{y}%<extra></extra>")
    fig = _fig(t, "Taxa de aprovação por ano (aprovados ÷ matriculados)", y="taxa (%)")
    fig.update_yaxes(range=[0, max(50, df["taxa_pct"].max() + 8)])
    fig.update_xaxes(tickmode="linear", dtick=1)  # anos inteiros (evita 2021.5)
    return fig


def fig_nota(df: pd.DataFrame) -> go.Figure:
    t = go.Scatter(x=df["ano"].astype(int), y=df["nota_media"], mode="lines+markers+text",
                   line=dict(color=BLUE, width=2), marker=dict(size=9),
                   text=[f"{v:.0f}" for v in df["nota_media"]], textposition="top center",
                   hovertemplate="%{x}: nota média %{y}<extra></extra>")
    fig = _fig(t, "Nota final média por ano", y="pontos")
    fig.update_yaxes(range=[df["nota_media"].min() - 12, df["nota_media"].max() + 14])
    fig.update_xaxes(tickmode="linear", dtick=1)  # anos inteiros (evita 2021.5)
    return fig


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
    fig = _fig(t, "Nota média em simulados por matéria", x="nota média (0–100)")
    fig.update_xaxes(range=[0, d["nota_media"].max() * 1.35])  # espaço p/ o rótulo "(n=…)"
    return fig


# --- Insights sobre tabelas completas (conclusões válidas, sem ressalva amostral) ---

def fig_universidades(aprovacoes: pd.DataFrame) -> go.Figure:
    s = aprovacoes["universidade"].value_counts().sort_values()
    t = go.Bar(x=s.values, y=s.index, orientation="h", marker_color=BLUE,
               text=s.values, textposition="outside",
               hovertemplate="%{y}: %{x} aprovações<extra></extra>")
    fig = _fig(t, "Aprovações por universidade", x="nº de aprovações", altura=380)
    fig.update_xaxes(range=[0, s.values.max() * 1.12])
    return fig


def fig_tipo_vaga(aprovacoes: pd.DataFrame) -> go.Figure:
    s = aprovacoes["modalidade_vaga"].value_counts()
    t = go.Bar(x=s.index, y=s.values, marker_color=BLUE, text=s.values, textposition="outside",
               hovertemplate="%{x}: %{y} aprovações<extra></extra>")
    fig = _fig(t, "Aprovações por tipo de vaga", y="nº de aprovações")
    fig.update_yaxes(range=[0, s.values.max() * 1.18])
    return fig


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


def fig_persistencia(matriculas: pd.DataFrame, aprovacoes: pd.DataFrame) -> go.Figure:
    p = taxa_por_permanencia(matriculas, aprovacoes)
    t = go.Bar(x=[f"{int(a)} ano{'s' if a > 1 else ''}" for a in p.index],
               y=(p["taxa"] * 100).round(1), marker_color=BLUE,
               text=[f"{v*100:.1f}% (n={n})" for v, n in zip(p["taxa"], p["n"])],
               textposition="outside",
               hovertemplate="%{x}: %{y}% de aprovação<extra></extra>")
    fig = _fig(t, "Taxa de aprovação por anos de permanência", y="taxa de aprovação (%)")
    fig.update_yaxes(range=[0, 105])
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


def fig_importancia_perm(imp: pd.DataFrame) -> go.Figure:
    d = imp.sort_values("queda_auc")
    cores = [BLUE if v > 0.01 else MUTED for v in d["queda_auc"]]
    t = go.Bar(x=d["queda_auc"], y=d["variavel"], orientation="h", marker_color=cores,
               error_x=dict(type="data", array=d["desvio"], color=INK, thickness=1),
               hovertemplate="%{y}: queda de %{x:.3f} no AUC<extra></extra>")
    fig = _fig(t, "Importância por permutação (queda de AUC ao embaralhar a variável)",
               x="queda no AUC", altura=380)
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

def _pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",") + "%"


def main() -> None:
    st.set_page_config(page_title="AprovaEdu Analytics", page_icon="📊", layout="wide")

    base = carregar_base()
    if base is None and not ha_fonte_bruta():
        with st.spinner("Gerando a base fictícia e rodando o pipeline (primeiro acesso)…"):
            preparar_demo()
        base = carregar_base()
    if base is None:
        st.title("📊 AprovaEdu Analytics")
        st.error(
            "Base tratada não encontrada em `data/final/`. Rode o pipeline:\n\n"
            "```\npython src/extract.py\npython src/transform.py\n```\n\n"
            "Sem dados? Gere uma base fictícia com `python scripts/gerar_dados_sinteticos.py`."
        )
        st.stop()

    modo = modo_base()
    real = modo == "completa"            # números e textos da base completa original
    completa = modo != "amostra"         # tabelas inteiras (completa ou fictícia)
    ficticia = modo == "sintetica"

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
    if ficticia:
        st.info(
            "**Dados fictícios.** Esta demonstração roda sobre uma base sintética gerada por "
            "`scripts/gerar_dados_sinteticos.py`, com a mesma estrutura e os mesmos problemas de "
            "qualidade da base original. Nomes, CPFs e números são inventados e não representam "
            "nenhuma instituição real.",
            icon="🎲",
        )
    elif real:
        st.success(
            "**Base completa.** Painel alimentado pelos CSVs integrais (812 estudantes, "
            "9.452 matrículas, 74.997 presenças) — os números são **conclusões de negócio**. "
            "A fase amostral está documentada no `README.md` › *Escopo dos dados*.",
            icon="✅",
        )
    else:
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
        "★ Insights", "🧠 Score (ML)",
    ])

    with aba1:
        q1f = q1[q1["ano"].astype(int).isin(anos)] if anos else q1
        col1, col2 = st.columns(2)
        if completa:
            col1.plotly_chart(fig_taxa(q1f), width="stretch")
            col2.plotly_chart(fig_nota(q1f), width="stretch")
            st.plotly_chart(fig_aprovacoes(q1f), width="stretch")
            if real:
                st.caption("A taxa oscila entre ~30% e ~36% sem tendência clara; o volume de "
                           "aprovados cresce junto com a base de matriculados. Fonte: consulta SQL (DuckDB).")
            elif len(q1f):
                st.caption(f"Taxa de aprovação entre {_pct(q1f['taxa_pct'].min())} e "
                           f"{_pct(q1f['taxa_pct'].max())} nos anos selecionados. Fonte: consulta SQL (DuckDB).")
        else:
            col1.plotly_chart(fig_aprovacoes(q1f), width="stretch")
            col2.plotly_chart(fig_nota(q1f), width="stretch")
            st.caption("A *taxa* (aprovados ÷ matriculados) exige a base completa — o denominador "
                       "amostral é truncado. Fonte: consulta SQL (DuckDB).")
        with st.expander("Ver dados (tabela)"):
            st.dataframe(q1f, hide_index=True, width="stretch")

    with aba2:
        resumo = resumo_presenca(pres, aprov)
        st.plotly_chart(fig_presenca(resumo), width="stretch")
        if real:
            st.caption("Na base completa a presença média é **praticamente idêntica** entre "
                       "aprovados e não aprovados (~84%) — **não há associação** entre presença "
                       "e aprovação nestes dados (r≈0, p≈0,86).")
        elif ficticia:
            medias = resumo.set_index("grupo")["media_pct"]
            st.caption("Presença média: " + " · ".join(f"{g} {_pct(v)}" for g, v in medias.items())
                       + ". Na base fictícia a presença entra com peso pequeno na chance de aprovação.")
        else:
            st.caption("Direção plausível (aprovados com presença maior), mas amostra ínfima não "
                       "permite afirmar associação.")
        with st.expander("Ver dados (tabela)"):
            st.dataframe(resumo[["grupo", "media_pct", "alunos"]], hide_index=True, width="stretch")

    with aba3:
        q3 = q3_por_materia()
        st.plotly_chart(fig_materia(q3), width="stretch")
        if real:
            st.caption("Desempenho **homogêneo** entre as 10 matérias (médias entre ~60,7 e ~62,0) "
                       "— nenhuma matéria destoa. Fonte: consulta SQL (DuckDB).")
        elif ficticia:
            st.caption(f"Médias entre {q3['nota_media'].min():.1f} e {q3['nota_media'].max():.1f} "
                       f"nas {len(q3)} matérias. Fonte: consulta SQL (DuckDB).")
        else:
            st.caption("Ranking ilustrativo — a amostra cobre poucas matérias. Fonte: consulta SQL (DuckDB).")
        with st.expander("Ver dados (tabela)"):
            st.dataframe(q3, hide_index=True, width="stretch")

    with aba4:
        st.subheader("Recomendações para a coordenação")
        if real:
            st.markdown(
                "1. **Retenção é a alavanca nº 1** — a chance de aprovação eventual salta de "
                "31,6% (1 ano) para 54,6% (2 anos) e 87,5% (3 anos); priorizar rematrícula, "
                "pacotes plurianuais e contato ativo com quem encerra o ano sem aprovação.\n"
                "2. **Não usar presença como preditor de aprovação** — ela é uniformemente alta "
                "(~84%) e não se associa ao desfecho; monitorá-la vale como gestão, não como alerta.\n"
                "3. **Usar o score de propensão para priorizar orientação** — a faixa Alta concentra "
                "62% de aprovação real vs 32% na Baixa; direcionar mentoria às faixas baixas.\n"
                "4. **Manter o reforço equilibrado entre matérias** — desempenho homogêneo "
                "(60,7–62,0); e empilhar matérias no mesmo ano não faz diferença (o volume de "
                "matrículas só refletia a permanência).\n"
                "5. **Padronizar a captura de dados na origem** — a base completa trouxe ~10% de "
                "notas fora de faixa e datas em 4 formatos; qualidade na origem barateia tudo."
            )
            st.info("Recomendações sustentadas pela base completa (ver relatório final e "
                    "notebook 06 — persistência).", icon="🧭")
        else:
            st.markdown(
                "1. **Acompanhar a permanência** — medir a aprovação por anos de cursinho e agir "
                "sobre quem encerra o ano sem aprovação.\n"
                "2. **Monitorar presença** por aluno e turma, como gestão e sinal de risco.\n"
                "3. **Reforçar as matérias de menor nota média** em simulados (carga horária, revisões).\n"
                "4. **Padronizar a captura de dados na origem** — reduz o retrabalho de limpeza e "
                "melhora a qualidade decisória.\n"
                "5. **Instrumentar a taxa de aprovação por coorte** (ingresso × vestibular) para "
                "separar efeitos de turma, matéria e presença."
            )
            if ficticia:
                st.info("Com dados fictícios, as recomendações mostram o tipo de decisão que o "
                        "painel apoia; os números das outras abas não são da base real.", icon="🧭")
            else:
                st.info("Recomendações derivadas do método; a confirmar na base completa.", icon="🧭")

    with aba5:
        of = base["ofertas_curso"]
        if completa:
            st.plotly_chart(fig_persistencia(base["matriculas"], aprov), width="stretch")
            if real:
                st.caption("**Persistência é o fator nº 1**: a chance de aprovação eventual salta de "
                           "31,6% (1 ano) para 87,5% (3 anos) — parte é efeito de mais tentativas, "
                           "mas o 3º ano excede o esperado mecânico em ~20 p.p. (notebook 06).")
            else:
                pt = taxa_por_permanencia(base["matriculas"], aprov)["taxa"] * 100
                st.caption("Aprovação por anos de permanência: "
                           + " · ".join(f"{int(a)} ano{'s' if a > 1 else ''} {_pct(v)}" for a, v in pt.items()))
        else:
            st.success(
                "Estas análises usam apenas tabelas **completas** (`aprovacoes`, `ofertas_curso`) — "
                "valem como **conclusões**, sem a ressalva amostral das abas Q1–Q4.", icon="✅",
            )
        col1, col2 = st.columns(2)
        col1.plotly_chart(fig_universidades(aprov), width="stretch")
        col2.plotly_chart(fig_tipo_vaga(aprov), width="stretch")
        st.plotly_chart(fig_modalidade_ano(of), width="stretch")
        if real:
            st.caption("Público majoritariamente cotista (cotas somadas > ampla concorrência), "
                       "destino concentrado em públicas locais (UECE, UFC) e mix de modalidade "
                       "que varia por ano sem tendência linear.")

    with aba6:
        m = avaliar_modelo()
        seg = m["segmentacao"].set_index("faixa")["taxa_aprovacao_real"]
        if real:
            st.success(
                "Score treinado na **base completa** (800 alunos com features): AUC ~0,61 e "
                "segmentação com poder real — a faixa **Alta** concentra ~62% de aprovação "
                "contra ~32% na Baixa. Principal fator: **permanência** (o nº de matrículas, "
                "coeficiente dominante, é reflexo dos anos cursados — ver notebook 06).",
                icon="🧠",
            )
        elif ficticia:
            faixas = " · ".join(f"{f} {_pct(v * 100)}" for f, v in seg.items())
            st.info(f"Score treinado na base fictícia ({m['n']} alunos com features), AUC "
                    f"{m['auc_logit'][0]:.2f}. Aprovação real por faixa de score: {faixas}.", icon="🧠")
        else:
            st.warning(
                "Modelo em **demonstração**: o alvo é confiável (aprovações completas), mas as "
                "features vêm de tabelas amostrais → nesta amostra o sinal fica **próximo do acaso** "
                "(AUC ~0,5). O entregável é o *pipeline* interpretável, pronto para a base completa.",
                icon="⚠️",
            )
        k1, k2, k3 = st.columns(3)
        k1.metric("Alunos (com features)", f"{m['n']}")
        k2.metric("AUC · Regressão logística", f"{m['auc_logit'][0]:.3f}")
        k3.metric("AUC · Random forest", f"{m['auc_rf'][0]:.3f}")
        col1, col2 = st.columns(2)
        col1.plotly_chart(fig_importancia(m["coefs"]), width="stretch")
        col2.plotly_chart(fig_score_dist(m["scores"]), width="stretch")
        st.plotly_chart(fig_importancia_perm(importancia_modelo()), width="stretch")
        if real:
            st.caption("**Importância formal de cada variável**: embaralho uma variável por vez e "
                       "meço quanto o AUC cai. `n_matriculas` (proxy da permanência) carrega quase "
                       "todo o sinal; `taxa_presenca` e `nota_sim_media` têm importância ≈ zero — "
                       "confirmação formal, no modelo, dos achados de Q2 e Q3.")
        else:
            st.caption("**Importância de cada variável**: embaralho uma variável por vez e meço "
                       "quanto o AUC cai — quanto maior a queda, mais o modelo depende dela.")
        st.markdown("**Segmentação por faixa de score** — a faixa ordena a taxa real de aprovação?")
        st.dataframe(m["segmentacao"], hide_index=True, width="stretch")
        with st.expander("Ver score por aluno"):
            st.dataframe(m["scores"].sort_values("score", ascending=False),
                         hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
