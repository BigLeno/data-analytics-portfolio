import pandas as pd

import transform
import validation as val

TABELAS = ["professores", "estudantes", "ofertas_curso", "matriculas", "aprovacoes",
           "simulados", "resultados_sim", "aulas", "presencas_aulas"]


def ler(final_dir, nome):
    return pd.read_parquet(final_dir / f"{nome}.parquet")


def test_extract_propaga_o_marcador(data_dir):
    assert (data_dir / "processed" / transform.MARCADOR_SINTETICO).exists()
    assert (data_dir / "final" / transform.ARQUIVO_FONTE).read_text().strip() == "sintetica"


def test_base_tratada_passa_na_validacao_pandera(final_dir):
    tabelas = {t: ler(final_dir, t) for t in TABELAS}
    assert val.validar(tabelas) == {}


def test_pks_unicas_e_duplicatas_removidas(final_dir):
    pks = {"matriculas": "matricula_id", "resultados_sim": "resultado_id",
           "presencas_aulas": "presenca_id", "aprovacoes": "aprovacao_id"}
    for tabela, pk in pks.items():
        assert ler(final_dir, tabela)[pk].is_unique
    assert not ler(final_dir, "aprovacoes")["chamada"].isna().any()


def test_notas_fora_de_faixa_viram_nulas(final_dir):
    nota = ler(final_dir, "resultados_sim")["nota"].dropna()
    diag = ler(final_dir, "matriculas")["nota_diagnostico"].dropna()
    assert nota.between(0, 100).all() and diag.between(0, 100).all()


def test_integridade_referencial(final_dir):
    alunos = set(ler(final_dir, "estudantes")["aluno_id"])
    ofertas = set(ler(final_dir, "ofertas_curso")["oferta_id"])
    aulas = set(ler(final_dir, "aulas")["aula_id"])
    simulados = set(ler(final_dir, "simulados")["simulado_id"])
    assert set(ler(final_dir, "matriculas")["aluno_id"]) <= alunos
    assert set(ler(final_dir, "matriculas")["oferta_id"]) <= ofertas
    assert set(ler(final_dir, "presencas_aulas")["aula_id"]) <= aulas
    assert set(ler(final_dir, "resultados_sim")["simulado_id"]) <= simulados
    assert set(ler(final_dir, "aprovacoes")["aluno_id"]) <= alunos


def test_coluna_denormalizada_e_descartada(final_dir):
    assert "professor_nome_informado" not in ler(final_dir, "ofertas_curso").columns
    assert "professor_nome_informado" not in ler(final_dir, "simulados").columns


def test_relatorio_documenta_as_correcoes(final_dir):
    texto = (final_dir / "_relatorio_tratamento.md").read_text(encoding="utf-8")
    assert "base fictícia" in texto
    assert "PK duplicada" in texto and "Todas as tabelas passaram" in texto


def test_validacao_aponta_categoria_fora_do_canonico(final_dir):
    est = ler(final_dir, "estudantes")
    est.loc[0, "escola_origem"] = "Particular"
    erros = val.validar({"estudantes": est})
    assert "estudantes" in erros and any("Particular" in e for e in erros["estudantes"])
