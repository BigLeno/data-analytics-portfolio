"""
extract.py - Etapa 1: Extração dos dados brutos

Lê o XLSX do desafio (dicionário + amostras) e grava cada aba de dados como
CSV individual em data/processed/, SEM alterar nada: os valores são lidos como
texto puro (dtype=str) e sem coerção de nulos, preservando os formatos
originais — datas mistas, CPFs com/sem máscara, inteiros com valores faltantes.
Assim a camada de origem é um espelho fiel do arquivo, e TODO o tratamento fica
concentrado no transform.py.

As abas de metadados (Resumo, Problemas_Qualidade) são documentação — dicionário
e catálogo de problemas —, não dados analíticos, e vão para data/processed/_meta/.
"""

import sys

import pandas as pd
from pathlib import Path

# O console do Windows costuma ser cp1252 e quebra ao imprimir os emojis dos
# logs; garante saída UTF-8 em qualquer terminal.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Caminhos
BASE_DIR = Path(__file__).resolve().parent.parent
XLSX_PATH = BASE_DIR / "data" / "raw" / "base_pre_vestibular_dicionario_amostras.xlsx"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

# Abas que são documentação (dicionário/catálogo), não tabelas analíticas
META_SHEETS = {"Resumo", "Problemas_Qualidade"}


def extract_sheets(xlsx_path: Path, output_dir: Path) -> dict[str, Path]:
    """Lê todas as abas do XLSX e grava cada uma como CSV individual.

    Lê os valores como texto (dtype=str) e sem converter vazios em NaN, para
    que a saída seja fiel ao arquivo de origem. As abas de dados vão para
    ``output_dir`` e as de metadados para ``output_dir/_meta``.

    Retorna um dict {nome_da_aba: caminho_do_csv} com os arquivos gravados.
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {xlsx_path}\n"
            "Baixe o XLSX do desafio e coloque em data/raw/"
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


if __name__ == "__main__":
    extract_sheets(XLSX_PATH, OUTPUT_DIR)
