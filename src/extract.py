"""
extract.py - Etapa 1: Extração dos dados brutos

Duas fontes possíveis, na ordem de preferência:

1. **Base completa (CSVs)** — se os 9 CSVs da base completa estiverem em
   data/raw/, são copiados byte a byte para data/processed/ com os nomes
   canônicos das tabelas (cópia fiel: nenhuma releitura/reserialização).
2. **Amostra (XLSX)** — na ausência dos CSVs, lê o XLSX do dicionário e grava
   cada aba como CSV (prefixo ``amostra_``), com os valores em texto puro
   (dtype=str) e sem coerção de nulos, preservando os formatos originais.

Em ambos os casos a camada de origem é um espelho fiel do arquivo, e TODO o
tratamento fica concentrado no transform.py.

As abas de metadados do XLSX (Resumo, Problemas_Qualidade) são documentação —
dicionário e catálogo de problemas —, não dados analíticos, e vão para
data/processed/_meta/.
"""

import shutil
import sys

import pandas as pd
from pathlib import Path

# O console do Windows costuma ser cp1252 e quebra ao imprimir os emojis dos
# logs; garante saída UTF-8 em qualquer terminal.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
XLSX_PATH = RAW_DIR / "base_pre_vestibular_dicionario_amostras.xlsx"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

# Abas que são documentação (dicionário/catálogo), não tabelas analíticas
META_SHEETS = {"Resumo", "Problemas_Qualidade"}

# Base completa: arquivo em data/raw/ -> nome canônico da tabela
CSV_COMPLETOS = {
    "professores.csv": "professores",
    "estudantes.csv": "estudantes",
    "ofertas_curso.csv": "ofertas_curso",
    "matriculas.csv": "matriculas",
    "aprovacoes_vestibular.csv": "aprovacoes",
    "simulados.csv": "simulados",
    "resultados_simulados.csv": "resultados_sim",
    "aulas.csv": "aulas",
    "presencas_aulas.csv": "presencas_aulas",
}


def extract_csvs_completos(raw_dir: Path, output_dir: Path) -> dict[str, Path]:
    """Copia os CSVs da base completa para data/processed/ com nomes canônicos.

    Cópia byte a byte (máxima fidelidade — nada é relido/reserializado).
    Retorna um dict {tabela: caminho_do_csv} com os arquivos gravados.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print("📂 Base COMPLETA detectada em data/raw/ (CSVs)")
    print("-" * 70)

    written: dict[str, Path] = {}
    for arquivo, tabela in CSV_COMPLETOS.items():
        origem = raw_dir / arquivo
        destino = output_dir / f"{tabela}.csv"
        shutil.copyfile(origem, destino)
        with origem.open("rb") as f:
            linhas = sum(1 for _ in f) - 1  # desconta o cabeçalho
        written[tabela] = destino
        rel = destino.relative_to(BASE_DIR)
        print(f"✅ dado  {arquivo:28s} → {str(rel):38s} ({linhas} linhas)")

    print("-" * 70)
    print(f"🎉 Extração concluída! {len(written)} CSVs em {output_dir.relative_to(BASE_DIR)}")
    return written


def extract_sheets(xlsx_path: Path, output_dir: Path) -> dict[str, Path]:
    """Lê todas as abas do XLSX e grava cada uma como CSV individual.

    Lê os valores como texto (dtype=str) e sem converter vazios em NaN, para
    que a saída seja fiel ao arquivo de origem. As abas de dados vão para
    ``output_dir`` e as de metadados para ``output_dir/_meta``.

    Retorna um dict {nome_da_aba: caminho_do_csv} com os arquivos gravados.
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"Arquivo de origem não encontrado:\n  {xlsx_path}\n\n"
            f"Coloque '{xlsx_path.name}' em data/raw/ e rode novamente."
        )

    meta_dir = output_dir / "_meta"
    output_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Lendo arquivo: {xlsx_path.name}")

    # Texto puro: mantém "10" como "10" (e não "10.0") e "" como "" (e não NaN).
    all_sheets = pd.read_excel(
        xlsx_path,
        sheet_name=None,
        dtype=str,
        keep_default_na=False,
    )

    print(f"📊 Abas encontradas: {len(all_sheets)}")
    print("-" * 70)

    written: dict[str, Path] = {}
    for sheet_name, df in all_sheets.items():
        is_meta = sheet_name in META_SHEETS
        dest_dir = meta_dir if is_meta else output_dir
        csv_name = sheet_name.strip().lower().replace(" ", "_") + ".csv"
        csv_path = dest_dir / csv_name

        # utf-8 sem BOM: estes CSVs são insumos do pipeline (pandas/DuckDB),
        # não entregáveis para abrir no Excel — o BOM atrapalharia a leitura.
        df.to_csv(csv_path, index=False, encoding="utf-8")
        written[sheet_name] = csv_path

        tag = "🗂  meta" if is_meta else "✅ dado"
        rel = csv_path.relative_to(BASE_DIR)
        print(f"{tag}  {sheet_name:24s} → {str(rel):42s} ({len(df)} linhas, {len(df.columns)} colunas)")

    print("-" * 70)
    print(f"🎉 Extração concluída! {len(written)} CSVs em {output_dir.relative_to(BASE_DIR)}")
    return written


def main() -> dict[str, Path]:
    """Extrai da melhor fonte disponível: base completa (CSVs) ou amostra (XLSX)."""
    completos = [f for f in CSV_COMPLETOS if (RAW_DIR / f).exists()]
    if len(completos) == len(CSV_COMPLETOS):
        return extract_csvs_completos(RAW_DIR, OUTPUT_DIR)
    if completos:  # presença parcial indica cópia incompleta — melhor avisar do que misturar
        faltam = sorted(set(CSV_COMPLETOS) - set(completos))
        raise FileNotFoundError(
            "Base completa INCOMPLETA em data/raw/ — faltam: " + ", ".join(faltam)
            + "\nCopie todos os CSVs (ou remova-os para usar o XLSX de amostra)."
        )
    return extract_sheets(XLSX_PATH, OUTPUT_DIR)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as erro:
        print(f"\n❌ {erro}\n")
        sys.exit(1)
