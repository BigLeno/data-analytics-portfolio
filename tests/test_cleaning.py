import pandas as pd
import pytest

import cleaning as cl


@pytest.mark.parametrize("sujo", ["MATEMÁTICA", "matematica", "Mat.", "  Matemática  "])
def test_materia_variacoes_viram_canonico(sujo):
    assert cl.normalizar(sujo, cl.MATERIA) == "Matemática"


def test_normalizar_vazio_e_desconhecido():
    assert cl.normalizar("", cl.UNIDADE) == "Não informado"
    assert cl.normalizar("  ", cl.UNIDADE, None) is None
    assert cl.normalizar("Unidade  Nova", cl.UNIDADE) == "Unidade Nova"   # nunca descarta


def test_fold_remove_acento_pontuacao_e_espacos():
    assert cl.fold("  Indicação!  ") == "indicacao"
    assert cl.fold(None) == ""


@pytest.mark.parametrize("texto, esperado", [
    ("2023-05-17", "2023-05-17"),
    ("2023/05/17", "2023-05-17"),
    ("17/05/2023", "2023-05-17"),
    ("17-05-2023", "2023-05-17"),
    ("05-17-2023", "2023-05-17"),          # mm-dd: segundo campo > 12
    ("03/04/2023", "2023-04-03"),          # ambíguo -> dd/mm
    ("2023-05-17 08:30:00", "2023-05-17"),
])
def test_parse_data_formatos_mistos(texto, esperado):
    assert cl.parse_data(texto) == pd.Timestamp(esperado)


@pytest.mark.parametrize("texto", ["", "ontem", "31/02/2023", "2023-13-40"])
def test_parse_data_invalida_vira_nat(texto):
    assert cl.parse_data(texto) is pd.NaT


def test_parse_datetime_preserva_hora():
    assert cl.parse_datetime("17/05/2023 08:30") == pd.Timestamp("2023-05-17 08:30")
    assert cl.parse_datetime("2023-05-17") == pd.Timestamp("2023-05-17")


@pytest.mark.parametrize("texto, esperado", [
    ("123.456.789-01", "12345678901"),
    ("12345678901", "12345678901"),
    ("2345678901", "02345678901"),         # perdeu o zero à esquerda
    ("", None),
    ("123456789012", None),
])
def test_normalizar_cpf(texto, esperado):
    assert cl.normalizar_cpf(texto) == esperado


def test_to_num_aceita_virgula_e_vazio():
    s = cl.to_num(pd.Series(["10,5", "7", "", "abc"]))
    assert s.iloc[0] == 10.5 and s.iloc[1] == 7
    assert s.iloc[2:].isna().all()


def test_cidade_e_universidade():
    assert cl.normalizar_cidade("maracanau") == "Maracanaú"
    assert cl.normalizar_cidade("nova cidade") == "Nova Cidade"
    assert cl.normalizar_universidade("U.F.C.") == "UFC"
