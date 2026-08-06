"""
model.py - Pipeline e avaliação do score de propensão à aprovação.

Lógica reutilizável (notebook e dashboard) do modelo: monta o Pipeline
scikit-learn, roda validação cruzada, ajusta o modelo interpretável e gera o
score por aluno com faixas. Alvo confiável (`aprovacoes` é tabela completa);
na amostra o sinal fica próximo do acaso — o valor é o pipeline, pronto para a
base completa.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features as ft


def _preprocessador() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), ft.NUMERICAS),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="Não informado")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), ft.CATEGORICAS),
    ])


def pipelines() -> tuple[Pipeline, Pipeline]:
    """(regressão logística interpretável, random forest) com o mesmo pré-processamento."""
    logit = Pipeline([("pre", _preprocessador()),
                      ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    rf = Pipeline([("pre", _preprocessador()),
                   ("clf", RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                                  random_state=42))])
    return logit, rf


def avaliar(final_dir: Path = ft.FINAL_DIR) -> dict:
    """Treina, valida e gera o score por aluno. Retorna dict com métricas e tabelas."""
    dados = ft.construir_features(final_dir)
    X, y = dados[ft.NUMERICAS + ft.CATEGORICAS], dados[ft.ALVO]
    logit, rf = pipelines()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    auc_logit = cross_val_score(logit, X, y, cv=cv, scoring="roc_auc")
    auc_rf = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc")

    logit.fit(X, y)
    nomes = logit.named_steps["pre"].get_feature_names_out()
    coefs = (pd.Series(logit.named_steps["clf"].coef_[0],
                       index=[n.split("__", 1)[-1] for n in nomes])
             .sort_values(key=abs, ascending=False))

    score = cross_val_predict(logit, X, y, cv=cv, method="predict_proba")[:, 1]
    scores = dados[["aluno_id", ft.ALVO]].copy()
    scores["score"] = score.round(3)
    scores["faixa"] = pd.cut(score, [-0.01, 0.33, 0.66, 1.01], labels=["Baixa", "Média", "Alta"])
    seg = (scores.groupby("faixa", observed=True)
           .agg(alunos=("aluno_id", "count"), taxa_aprovacao_real=(ft.ALVO, "mean"))
           .round(2).reset_index())

    return {
        "n": len(dados), "positivos": int(y.sum()),
        "auc_logit": (auc_logit.mean(), auc_logit.std()),
        "auc_rf": (auc_rf.mean(), auc_rf.std()),
        "coefs": coefs, "scores": scores, "segmentacao": seg,
    }


def importancia_variaveis(final_dir: Path = ft.FINAL_DIR, n_repeats: int = 30) -> pd.DataFrame:
    """Importância de cada variável por permutação (queda de AUC ao embaralhá-la).

    Embaralhar uma variável destrói sua relação com o alvo; a queda no AUC mede
    quanto o modelo dependia dela. Vantagem sobre coeficientes: opera na variável
    ORIGINAL (categóricas inteiras, não colunas one-hot) e independe de escala.
    """
    from sklearn.inspection import permutation_importance

    dados = ft.construir_features(final_dir)
    X, y = dados[ft.NUMERICAS + ft.CATEGORICAS], dados[ft.ALVO]
    logit, _ = pipelines()
    logit.fit(X, y)
    r = permutation_importance(logit, X, y, scoring="roc_auc",
                               n_repeats=n_repeats, random_state=42)
    return (pd.DataFrame({
        "variavel": X.columns,
        "queda_auc": r.importances_mean.round(4),
        "desvio": r.importances_std.round(4),
    }).sort_values("queda_auc", ascending=False).reset_index(drop=True))


if __name__ == "__main__":
    r = avaliar()
    print(f"n={r['n']} | positivos={r['positivos']}")
    print(f"AUC logística = {r['auc_logit'][0]:.3f} ± {r['auc_logit'][1]:.3f}")
    print(f"AUC random forest = {r['auc_rf'][0]:.3f} ± {r['auc_rf'][1]:.3f}")
    print(r["segmentacao"].to_string(index=False))
