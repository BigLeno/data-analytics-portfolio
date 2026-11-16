import pandas as pd

import extract
import gerar_dados_sinteticos as gds


def test_gera_os_nove_csvs_e_o_marcador(tmp_path):
    contagens = gds.gerar(tmp_path, alunos=40, seed=1)
    assert set(contagens) == set(extract.CSV_COMPLETOS)
    assert (tmp_path / gds.MARCADOR).exists()
    for arquivo in extract.CSV_COMPLETOS:
        assert len(pd.read_csv(tmp_path / arquivo, dtype=str)) > 0


def test_mesma_seed_gera_a_mesma_base(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gds.gerar(a, alunos=30, seed=3)
    gds.gerar(b, alunos=30, seed=3)
    for arquivo in extract.CSV_COMPLETOS:
        assert (a / arquivo).read_bytes() == (b / arquivo).read_bytes()


def test_base_bruta_vem_suja(tmp_path):
    gds.gerar(tmp_path, alunos=200, seed=5)
    est = pd.read_csv(tmp_path / "estudantes.csv", dtype=str, keep_default_na=False)
    aprov = pd.read_csv(tmp_path / "aprovacoes_vestibular.csv", dtype=str, keep_default_na=False)
    mat = pd.read_csv(tmp_path / "matriculas.csv", dtype=str, keep_default_na=False)
    assert est["cpf_ficticio"].str.contains(r"\.").any()          # CPF com máscara
    assert est["data_cadastro"].str.contains("/").any()           # datas em formatos mistos
    assert (aprov["chamada"] == "Cadastro duplicado?").any()
    assert mat["matricula_id"].duplicated().any()                 # PK repetida
