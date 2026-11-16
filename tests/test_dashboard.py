import shutil

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = "dashboard/app.py"


@pytest.fixture(autouse=True)
def limpar_cache():
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def test_painel_com_base_ficticia(data_dir, monkeypatch):
    monkeypatch.setenv("APROVAEDU_DATA_DIR", str(data_dir))
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    assert any("Dados fictícios" in i.value for i in at.info)
    assert len(at.tabs) == 6
    assert at.metric[0].label == "Estudantes" and at.metric[0].value == "300"


def test_painel_gera_a_demo_sozinho_quando_nao_ha_dados(tmp_path, monkeypatch):
    monkeypatch.setenv("APROVAEDU_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=300).run()
    assert not at.exception
    assert (tmp_path / "final" / "_fonte.txt").read_text().strip() == "sintetica"
    assert any("Dados fictícios" in i.value for i in at.info)


def test_painel_nao_sobrescreve_fonte_existente(data_dir, tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    shutil.copytree(data_dir / "raw", raw)
    monkeypatch.setenv("APROVAEDU_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Base tratada não encontrada" in e.value for e in at.error)
    assert not (tmp_path / "final").exists()
