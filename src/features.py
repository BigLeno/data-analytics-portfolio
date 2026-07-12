"""
features.py - Engenharia de atributos por aluno para o modelo de propensão.

Monta uma tabela aluno × features a partir da base tratada, com o alvo binário
`aprovado` (aluno presente em `aprovacoes` — tabela completa, então o rótulo é
confiável). As features vêm de tabelas amostrais (simulados, presença, matrícula),
logo são esparsas — a imputação e os indicadores de ausência são parte do modelo.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = BASE_DIR / "data" / "final"

NUMERICAS = ["nota_sim_media", "n_simulados", "taxa_finalizacao", "taxa_presenca",
             "n_presencas", "n_matriculas", "nota_diag_media", "bolsa_media"]
CATEGORICAS = ["escola_origem", "canal_captacao"]
ALVO = "aprovado"


def construir_features(final_dir: Path = FINAL_DIR) -> pd.DataFrame:
    """Retorna DataFrame aluno_id + features (numéricas/categóricas) + alvo `aprovado`."""
    ler = lambda n: pd.read_parquet(final_dir / f"{n}.parquet")
    mat, pres, res = ler("matriculas"), ler("presencas_aulas"), ler("resultados_sim")
    ap, est = ler("aprovacoes"), ler("estudantes")

    # população: alunos com QUALQUER registro de atividade
    featured = sorted(set(mat["aluno_id"]) | set(pres["aluno_id"]) | set(res["aluno_id"]))
    df = pd.DataFrame({"aluno_id": featured})

    # simulados
    r = res.copy()
    r["finalizado"] = r["status_realizacao"].eq("Finalizado")
    g_sim = r.groupby("aluno_id").agg(
        nota_sim_media=("nota", "mean"),
        n_simulados=("resultado_id", "count"),
        taxa_finalizacao=("finalizado", "mean"),
    )
    # presença
    p = pres.copy()
    p["compareceu"] = p["status_presenca"].isin(["Presente", "Atrasado"])
    g_pres = p.groupby("aluno_id").agg(
        taxa_presenca=("compareceu", "mean"),
        n_presencas=("presenca_id", "count"),
    )
    # matrícula
    g_mat = mat.groupby("aluno_id").agg(
        n_matriculas=("matricula_id", "count"),
        nota_diag_media=("nota_diagnostico", "mean"),
        bolsa_media=("bolsa_percentual", "mean"),
    )
    # cadastro (categóricas)
    cad = est[["aluno_id", "escola_origem", "canal_captacao"]].drop_duplicates("aluno_id")

    df = (df.merge(g_sim, on="aluno_id", how="left")
            .merge(g_pres, on="aluno_id", how="left")
            .merge(g_mat, on="aluno_id", how="left")
            .merge(cad, on="aluno_id", how="left"))

    df[ALVO] = df["aluno_id"].isin(set(ap["aluno_id"])).astype(int)
    return df


if __name__ == "__main__":
    d = construir_features()
    print("tabela de modelagem:", d.shape)
    print("positivos (aprovados):", int(d[ALVO].sum()), "| negativos:", int((1 - d[ALVO]).sum()))
    print("\ncobertura (não-nulos) por feature:")
    print(d[NUMERICAS + CATEGORICAS].notna().sum().to_string())
