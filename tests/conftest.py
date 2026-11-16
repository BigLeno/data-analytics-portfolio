"""Fixtures: uma base fictícia pequena, gerada e tratada uma vez por sessão de testes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

import extract  # noqa: E402
import gerar_dados_sinteticos as gds  # noqa: E402
import transform  # noqa: E402


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory) -> Path:
    """Pasta data/ temporária com raw/ (fictícia), processed/ e final/ já processadas."""
    base = tmp_path_factory.mktemp("data")
    raw, processed, final = base / "raw", base / "processed", base / "final"
    gds.gerar(raw, alunos=300, seed=7)

    mp = pytest.MonkeyPatch()
    mp.setattr(extract, "RAW_DIR", raw)
    mp.setattr(extract, "OUTPUT_DIR", processed)
    mp.setattr(extract, "XLSX_PATH", raw / extract.XLSX_PATH.name)
    mp.setattr(transform, "IN_DIR", processed)
    mp.setattr(transform, "OUT_DIR", final)
    extract.main()
    transform.main()
    mp.undo()
    return base


@pytest.fixture(scope="session")
def final_dir(data_dir: Path) -> Path:
    return data_dir / "final"
