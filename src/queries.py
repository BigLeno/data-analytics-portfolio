"""
queries.py - Camada analítica em SQL (DuckDB) sobre a base tratada.

DuckDB lê os Parquet de data/final/ diretamente (sem carregar tudo em memória),
permitindo responder às perguntas com SQL — uma alternativa de modelagem
analítica às agregações em Pandas. Os resultados batem com os do 02_analise.ipynb.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = BASE_DIR / "data" / "final"

_VIEWS = ["aprovacoes", "matriculas", "resultados_sim", "simulados", "presencas_aulas"]


def conectar(final_dir: Path = FINAL_DIR) -> duckdb.DuckDBPyConnection:
    """Abre uma conexão in-memory com uma view por Parquet da base tratada."""
    con = duckdb.connect(database=":memory:")
    for t in _VIEWS:
        caminho = (final_dir / f"{t}.parquet").as_posix()
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{caminho}')")
    return con


def aprovacoes_por_ano(final_dir: Path = FINAL_DIR) -> pd.DataFrame:
    """Q1 — matriculados, aprovados, taxa de aprovação e nota final média por ano.

    Denominador: alunos distintos matriculados no ano (base elegível).
    Na amostra o denominador é truncado e a taxa não é confiável; na base
    completa a coluna taxa_pct responde a Q1 diretamente.
    """
    con = conectar(final_dir)
    return con.execute(
        """
        WITH m AS (
            SELECT ano, COUNT(DISTINCT aluno_id) AS matriculados
            FROM matriculas GROUP BY ano
        ), a AS (
            SELECT ano_vestibular AS ano,
                   COUNT(DISTINCT aluno_id)            AS aprovados,
                   ROUND(AVG(nota_final_vestibular),1) AS nota_media
            FROM aprovacoes GROUP BY ano_vestibular
        )
        SELECT a.ano, m.matriculados, a.aprovados,
               ROUND(100.0 * a.aprovados / m.matriculados, 1) AS taxa_pct,
               a.nota_media
        FROM a LEFT JOIN m USING (ano)
        ORDER BY a.ano
        """
    ).df()


def desempenho_por_materia(final_dir: Path = FINAL_DIR) -> pd.DataFrame:
    """Q3 — nota média em simulados por matéria (join resultados × simulados)."""
    con = conectar(final_dir)
    return con.execute(
        """
        SELECT s.materia,
               ROUND(AVG(r.nota),1) AS nota_media,
               COUNT(r.nota)        AS provas
        FROM resultados_sim r
        JOIN simulados s USING (simulado_id)
        WHERE r.nota IS NOT NULL
        GROUP BY s.materia
        ORDER BY nota_media DESC
        """
    ).df()


if __name__ == "__main__":
    print("== Q1: aprovações por ano ==")
    print(aprovacoes_por_ano().to_string(index=False))
    print("\n== Q3: desempenho por matéria ==")
    print(desempenho_por_materia().to_string(index=False))
