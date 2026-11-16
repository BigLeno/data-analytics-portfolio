import features as ft
import model
import queries


def test_q1_tem_os_cinco_anos(final_dir):
    q1 = queries.aprovacoes_por_ano(final_dir)
    assert q1["ano"].astype(int).tolist() == [2021, 2022, 2023, 2024, 2025]
    assert q1["taxa_pct"].between(0, 100).all()


def test_q3_cobre_as_materias(final_dir):
    q3 = queries.desempenho_por_materia(final_dir)
    assert len(q3) == 11 and q3["nota_media"].between(0, 100).all()


def test_features_um_aluno_por_linha(final_dir):
    d = ft.construir_features(final_dir)
    assert d["aluno_id"].is_unique
    assert set(ft.NUMERICAS + ft.CATEGORICAS + [ft.ALVO]) <= set(d.columns)
    assert 0 < d[ft.ALVO].mean() < 1


def test_modelo_encontra_o_sinal_da_base_ficticia(final_dir):
    r = model.avaliar(final_dir)
    assert r["auc_logit"][0] > 0.6          # a aprovação depende de aptidão e permanência
    assert {"Baixa", "Alta"} <= set(r["segmentacao"]["faixa"].astype(str))


def test_importancia_por_permutacao(final_dir):
    imp = model.importancia_variaveis(final_dir, n_repeats=3)
    assert set(imp["variavel"]) == set(ft.NUMERICAS + ft.CATEGORICAS)
