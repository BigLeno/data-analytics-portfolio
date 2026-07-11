"""
transform.py - Etapa 2: Tratamento e estruturação da base analítica.

Lê os CSVs brutos de data/processed/ (texto fiel ao XLSX), aplica as regras de
limpeza definidas em cleaning.py — todas embasadas no perfilamento dos dados —
e grava a base tratada em data/final/ (Parquet + CSV). Ao final, escreve um
relatório em data/final/_relatorio_tratamento.md documentando cada decisão e as
contagens de correções (requisito do desafio: decisões documentadas).

Decisões-chave (resumo; detalhe no relatório e no notebook):
- Valores lidos como texto e tipados aqui; nada é "limpo" antes desta etapa.
- Datas em formatos mistos -> ISO; ambiguidade dd/mm vs mm/dd resolvida pela
  magnitude dos campos, com padrão brasileiro (dd/mm) no caso ambíguo.
- Categorias normalizadas por dicionário canônico (caixa/acento/abreviação).
- Denormalização: professor_id é a FK; o nome informado nos fatos é conferido
  contra a dimensão Professores e então descartado.
- Duplicidade: em Aprovações, remove-se as linhas marcadas com
  chamada = "Cadastro duplicado?" (coincidem 1:1 com duplicatas por chave de
  negócio). Alunos aprovados em cursos/universidades distintas são mantidos.
- Outliers: nota de simulado fora de [0, 100] vira nula; inconsistências de
  tempo/acertos são apenas reportadas (não descartadas).
- Faltantes: medidas (notas) não são imputadas; categóricas viram
  "Não informado" quando faz sentido de negócio.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cleaning as cl
import validation as val

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
IN_DIR = BASE_DIR / "data" / "processed"
OUT_DIR = BASE_DIR / "data" / "final"

# Mapas específicos de aprovações (definidos aqui por serem locais desta tabela)
MODALIDADE_VAGA = {
    "ampla concorrencia": "Ampla concorrência",
    "cota escola publica": "Cota escola pública",
    "pcd": "PCD", "ppi": "PPI",
}
CHAMADA = {
    "1a chamada": "1ª chamada", "2a chamada": "2ª chamada",
    "lista de espera": "Lista de espera", "sisu": "SISU",
    "vestibular proprio": "Vestibular próprio",
}
DUP_FLAG = "cadastro duplicado"  # fold de "Cadastro duplicado?"

# relatório acumulado
_rel: list[str] = []
def rel(msg: str) -> None:
    _rel.append(msg)
    print(msg)


def _ler(nome: str) -> pd.DataFrame:
    return pd.read_csv(IN_DIR / f"amostra_{nome}.csv", dtype=str, keep_default_na=False)

def _int(s: pd.Series) -> pd.Series:
    return cl.to_num(s).round().astype("Int64")

def _txt(s: pd.Series) -> pd.Series:
    """strip/collapse e transforma vazio em <NA>."""
    return s.map(cl.strip_collapse).replace("", pd.NA)


# --------------------------------------------------------------------------- #
# Limpeza por tabela
# --------------------------------------------------------------------------- #

def clean_professores() -> pd.DataFrame:
    df = _ler("professores")
    df["nome_professor"] = df["nome_professor"].map(cl.titulo)
    df["email_professor"] = _txt(df["email_professor"]).str.lower()
    df["materia_principal"] = df["materia_principal"].map(lambda v: cl.normalizar(v, cl.MATERIA, None))
    df["materias_ensina"] = df["materias_ensina"].map(
        lambda v: "; ".join(cl.normalizar(p, cl.MATERIA, p) for p in str(v).split(";") if p.strip()) or pd.NA
    )
    df["data_contratacao"] = df["data_contratacao"].map(cl.parse_data)
    df["status_professor"] = df["status_professor"].map(lambda v: cl.normalizar(v, cl.STATUS_PROFESSOR, None))
    df["unidade_base"] = df["unidade_base"].map(lambda v: cl.normalizar(v, cl.UNIDADE, None))
    df["carga_horaria_semanal"] = _int(df["carga_horaria_semanal"])
    df["observacoes"] = _txt(df["observacoes"])
    return df

def clean_estudantes() -> pd.DataFrame:
    df = _ler("estudantes")
    df["nome_aluno"] = df["nome_aluno"].map(cl.titulo)
    df["cpf_ficticio"] = df["cpf_ficticio"].map(cl.normalizar_cpf)
    df["email_aluno"] = _txt(df["email_aluno"]).str.lower()
    df["telefone"] = _txt(df["telefone"])
    df["data_nascimento"] = df["data_nascimento"].map(cl.parse_data)
    df["cidade"] = df["cidade"].map(cl.normalizar_cidade)
    df["escola_origem"] = df["escola_origem"].map(lambda v: cl.normalizar(v, cl.ESCOLA_ORIGEM))
    df["data_cadastro"] = df["data_cadastro"].map(cl.parse_data)
    df["canal_captacao"] = df["canal_captacao"].map(lambda v: cl.normalizar(v, cl.CANAL))
    return df

def clean_ofertas() -> pd.DataFrame:
    df = _ler("ofertas_curso")
    df["ano"] = _int(df["ano"])
    for c in ("turma", "turno"):
        df[c] = _txt(df[c])
    df["unidade"] = df["unidade"].map(lambda v: cl.normalizar(v, cl.UNIDADE, None))
    df["materia"] = df["materia"].map(lambda v: cl.normalizar(v, cl.MATERIA, None))
    df["modalidade"] = df["modalidade"].map(lambda v: cl.normalizar(v, cl.MODALIDADE, None))
    df["carga_horaria_total"] = _int(df["carga_horaria_total"])
    df["preco_lista"] = _int(df["preco_lista"])
    df["data_inicio"] = df["data_inicio"].map(cl.parse_data)
    df["data_fim"] = df["data_fim"].map(cl.parse_data)
    return df

def clean_matriculas() -> pd.DataFrame:
    df = _ler("matriculas")
    df["ano"] = _int(df["ano"])
    df["materia_declarada"] = df["materia_declarada"].map(lambda v: cl.normalizar(v, cl.MATERIA, None))
    df["data_matricula"] = df["data_matricula"].map(cl.parse_data)
    df["bolsa_percentual"] = cl.to_num(df["bolsa_percentual"])
    df["status_matricula"] = df["status_matricula"].map(lambda v: cl.normalizar(v, cl.STATUS_MATRICULA))
    df["nota_diagnostico"] = cl.to_num(df["nota_diagnostico"])
    df["origem_captacao"] = df["origem_captacao"].map(lambda v: cl.normalizar(v, cl.CANAL))
    return df

def clean_aprovacoes() -> pd.DataFrame:
    df = _ler("aprovacoes")
    antes = len(df)
    dup = df["chamada"].map(cl.fold) == DUP_FLAG
    df = df[~dup].copy()
    rel(f"- **Aprovações – duplicidade:** removidas {int(dup.sum())} linhas marcadas "
        f'"Cadastro duplicado?" ({antes} → {len(df)}).')
    df["ano_vestibular"] = _int(df["ano_vestibular"])
    df["universidade"] = df["universidade"].map(cl.normalizar_universidade)
    df["curso_aprovado"] = _txt(df["curso_aprovado"])
    df["modalidade_vaga"] = df["modalidade_vaga"].map(lambda v: cl.normalizar(v, MODALIDADE_VAGA))
    df["chamada"] = df["chamada"].map(lambda v: cl.normalizar(v, CHAMADA, None))
    df["bolsa_aprovacao"] = df["bolsa_aprovacao"].map(lambda v: cl.normalizar(v, cl.SIM_NAO))
    df["data_resultado"] = df["data_resultado"].map(cl.parse_data)
    df["nota_final_vestibular"] = cl.to_num(df["nota_final_vestibular"])
    df["campus"] = df["campus"].map(cl.normalizar_cidade)
    return df

def clean_simulados() -> pd.DataFrame:
    df = _ler("simulados")
    df["ano"] = _int(df["ano"])
    df["data_simulado"] = df["data_simulado"].map(cl.parse_data)
    df["materia"] = df["materia"].map(lambda v: cl.normalizar(v, cl.MATERIA, None))
    df["dificuldade"] = df["dificuldade"].map(lambda v: cl.normalizar(v, cl.DIFICULDADE))
    df["tipo_simulado"] = _txt(df["tipo_simulado"])
    df["total_questoes"] = _int(df["total_questoes"])
    df["tempo_limite_min"] = _int(df["tempo_limite_min"])
    df["tema"] = _txt(df["tema"])
    return df

def clean_resultados(simulados: pd.DataFrame) -> pd.DataFrame:
    df = _ler("resultados_sim")
    df["ano"] = _int(df["ano"])
    df["status_realizacao"] = df["status_realizacao"].map(lambda v: cl.normalizar(v, cl.STATUS_REALIZACAO))
    nota = cl.to_num(df["nota"])
    fora = nota.notna() & ((nota < 0) | (nota > 100))
    df["nota"] = nota.where(~fora)
    rel(f"- **Resultados – outliers de nota:** {int(fora.sum())} notas fora de [0,100] "
        "convertidas para nula.")
    df["acertos"] = _int(df["acertos"])
    df["tempo_finalizacao_min"] = cl.to_num(df["tempo_finalizacao_min"])
    df["inicio_simulado"] = df["inicio_simulado"].map(cl.parse_datetime)
    df["dispositivo"] = df["dispositivo"].map(lambda v: cl.normalizar(v, cl.DISPOSITIVO))
    df["tentativas"] = _int(df["tentativas"])
    df["unidade_aplicacao"] = df["unidade_aplicacao"].map(lambda v: cl.normalizar(v, cl.UNIDADE))
    # checagens de consistência (apenas reportadas)
    m = df.merge(simulados[["simulado_id", "total_questoes", "tempo_limite_min"]], on="simulado_id", how="left")
    ac = (m["acertos"] > m["total_questoes"]).sum()
    tp = (m["tempo_finalizacao_min"] > m["tempo_limite_min"]).sum()
    rel(f"- **Resultados – consistência:** {int(ac)} com acertos > total de questões; "
        f"{int(tp)} com tempo acima do limite (mantidos e sinalizados).")
    return df

def clean_aulas() -> pd.DataFrame:
    df = _ler("aulas")
    df["ano"] = _int(df["ano"])
    df["data_aula"] = df["data_aula"].map(cl.parse_data)
    df["materia"] = df["materia"].map(lambda v: cl.normalizar(v, cl.MATERIA, None))
    df["turma"] = _txt(df["turma"])
    df["tema_aula"] = _txt(df["tema_aula"])
    df["duracao_min"] = cl.to_num(df["duracao_min"])
    df["modalidade_aula"] = df["modalidade_aula"].map(lambda v: cl.normalizar(v, cl.MODALIDADE))
    return df

def clean_presencas() -> pd.DataFrame:
    df = _ler("presencas_aulas")
    df["status_presenca"] = df["status_presenca"].map(lambda v: cl.normalizar(v, cl.STATUS_PRESENCA))
    df["atraso_min"] = cl.to_num(df["atraso_min"])
    df["justificativa"] = _txt(df["justificativa"])
    return df


# --------------------------------------------------------------------------- #
# Denormalização e deduplicação genérica
# --------------------------------------------------------------------------- #

def conferir_denormalizacao(fato: pd.DataFrame, professores: pd.DataFrame, nome_tabela: str) -> pd.DataFrame:
    """Confere professor_nome_informado contra a dimensão e descarta a coluna."""
    if "professor_nome_informado" not in fato.columns:
        return fato
    ref = professores.set_index("professor_id")["nome_professor"]
    esperado = fato["professor_id"].map(ref)
    informado = fato["professor_nome_informado"].map(cl.titulo)
    divergem = (esperado.notna()) & (informado != esperado)
    rel(f"- **{nome_tabela} – denormalização:** {int(divergem.sum())} nomes de professor "
        "divergentes do cadastro; usada a dimensão como fonte de verdade e removida a coluna informada.")
    return fato.drop(columns=["professor_nome_informado"])

def dedup_pk(df: pd.DataFrame, pk: str, nome: str) -> pd.DataFrame:
    dups = df[pk].duplicated().sum()
    if dups:
        rel(f"- **{nome} – PK duplicada:** {int(dups)} linhas removidas por {pk} repetido.")
    return df.drop_duplicates(subset=[pk], keep="first")


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #

def _salvar(df: pd.DataFrame, nome: str) -> None:
    df.to_parquet(OUT_DIR / f"{nome}.parquet", index=False)
    df.to_csv(OUT_DIR / f"{nome}.csv", index=False, encoding="utf-8")

def main() -> dict[str, pd.DataFrame]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rel("# Relatório de tratamento — AprovaEdu Analytics\n")
    rel("Gerado por `src/transform.py`. Correções aplicadas sobre `data/processed/` "
        "e base tratada salva em `data/final/`.\n")

    professores = dedup_pk(clean_professores(), "professor_id", "Professores")
    estudantes = dedup_pk(clean_estudantes(), "aluno_id", "Estudantes")
    ofertas = conferir_denormalizacao(dedup_pk(clean_ofertas(), "oferta_id", "Ofertas"), professores, "Ofertas")
    matriculas = dedup_pk(clean_matriculas(), "matricula_id", "Matrículas")
    aprovacoes = dedup_pk(clean_aprovacoes(), "aprovacao_id", "Aprovações")
    simulados = conferir_denormalizacao(dedup_pk(clean_simulados(), "simulado_id", "Simulados"), professores, "Simulados")
    resultados = dedup_pk(clean_resultados(simulados), "resultado_id", "Resultados")
    aulas = dedup_pk(clean_aulas(), "aula_id", "Aulas")
    presencas = dedup_pk(clean_presencas(), "presenca_id", "Presenças")

    tabelas = {
        "professores": professores, "estudantes": estudantes, "ofertas_curso": ofertas,
        "matriculas": matriculas, "aprovacoes": aprovacoes, "simulados": simulados,
        "resultados_sim": resultados, "aulas": aulas, "presencas_aulas": presencas,
    }
    rel("\n## Validação da base tratada (Pandera)\n")
    erros = val.validar(tabelas)
    if not erros:
        rel("- ✅ Todas as tabelas passaram: PKs únicas e não-nulas, faixas numéricas "
            "plausíveis e categorias dentro do conjunto canônico.")
    else:
        for t, es in erros.items():
            rel(f"- ❌ **{t}**: " + "; ".join(es[:5]))

    rel("\n## Tabelas geradas\n")
    for nome, df in tabelas.items():
        _salvar(df, nome)
        rel(f"- `{nome}`: {len(df)} linhas × {len(df.columns)} colunas")

    (OUT_DIR / "_relatorio_tratamento.md").write_text("\n".join(_rel), encoding="utf-8")
    print("\n🎉 Tratamento concluído! Base tratada em", OUT_DIR.relative_to(BASE_DIR))
    return tabelas


if __name__ == "__main__":
    main()
