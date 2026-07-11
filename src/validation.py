"""
validation.py - Schemas Pandera para validar a base tratada.

Garante os invariantes que o tratamento (transform.py) deve produzir: chaves
primárias únicas e não-nulas, faixas numéricas plausíveis e categorias dentro do
conjunto canônico. Serve como "contrato" da base analítica — se o pipeline
regredir, a validação falha e aponta onde.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandera as pa
from pandera import Check, Column, DataFrameSchema

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cleaning as cl

NI = "Não informado"
_MATERIA = sorted(set(cl.MATERIA.values()))
_MOD_VAGA = ["Ampla concorrência", "Cota escola pública", "PCD", "PPI"]
_CHAMADA = ["1ª chamada", "2ª chamada", "Lista de espera", "SISU", "Vestibular próprio"]


def _cat(valores, nao_informado=False):
    """Check.isin do conjunto canônico (+ 'Não informado' quando aplicável)."""
    vals = list(valores) + ([NI] if nao_informado else [])
    return Check.isin(vals)


def _pk(nome):
    return Column(object, unique=True, nullable=False, required=True)


ID = Column(object, nullable=False)          # chave estrangeira / id não-nulo
TXT = Column(object, nullable=True)           # texto livre
DT = Column("datetime64[ns]", nullable=True)
ANO = Column("Int64", Check.in_range(2021, 2025), nullable=True)

SCHEMAS: dict[str, DataFrameSchema] = {
    "professores": DataFrameSchema({
        "professor_id": _pk("professor_id"),
        "materia_principal": Column(object, _cat(_MATERIA), nullable=True),
        "status_professor": Column(object, _cat(["Ativo", "Inativo"]), nullable=True),
        "unidade_base": Column(object, _cat(["Aldeota", "Centro", "Online", "Sul"]), nullable=True),
        "carga_horaria_semanal": Column("Int64", Check.in_range(0, 80), nullable=True),
    }, strict=False, coerce=False),

    "estudantes": DataFrameSchema({
        "aluno_id": _pk("aluno_id"),
        "escola_origem": Column(object, _cat(["Pública", "Privada", "Federal"], nao_informado=True), nullable=True),
        "canal_captacao": Column(object, _cat(cl.CANAL.values(), nao_informado=True), nullable=True),
        "data_nascimento": DT,
    }, strict=False, coerce=False),

    "ofertas_curso": DataFrameSchema({
        "oferta_id": _pk("oferta_id"),
        "ano": ANO,
        "materia": Column(object, _cat(_MATERIA), nullable=True),
        "modalidade": Column(object, _cat(cl.MODALIDADE.values()), nullable=True),
        "unidade": Column(object, _cat(["Aldeota", "Centro", "Online", "Sul"]), nullable=True),
        "preco_lista": Column("Int64", Check.ge(0), nullable=True),
        "professor_id": ID,
    }, strict=False, coerce=False),

    "matriculas": DataFrameSchema({
        "matricula_id": _pk("matricula_id"),
        "aluno_id": ID, "oferta_id": ID, "ano": ANO,
        "materia_declarada": Column(object, _cat(_MATERIA), nullable=True),
        "status_matricula": Column(object, _cat(["Ativa", "Cancelada", "Concluída", "Trancada"], nao_informado=True), nullable=True),
        "bolsa_percentual": Column(float, Check.in_range(0, 100), nullable=True),
        "nota_diagnostico": Column(float, Check.in_range(0, 100), nullable=True),
    }, strict=False, coerce=False),

    "aprovacoes": DataFrameSchema({
        "aprovacao_id": _pk("aprovacao_id"),
        "aluno_id": ID, "ano_vestibular": ANO,
        "modalidade_vaga": Column(object, _cat(_MOD_VAGA, nao_informado=True), nullable=True),
        "chamada": Column(object, _cat(_CHAMADA), nullable=True),
        "bolsa_aprovacao": Column(object, _cat(["Sim", "Não", "Parcial"], nao_informado=True), nullable=True),
        "nota_final_vestibular": Column(float, Check.in_range(0, 1000), nullable=True),
    }, strict=False, coerce=False),

    "simulados": DataFrameSchema({
        "simulado_id": _pk("simulado_id"),
        "ano": ANO, "professor_id": ID,
        "materia": Column(object, _cat(_MATERIA), nullable=True),
        "dificuldade": Column(object, _cat(["Fácil", "Média", "Difícil"], nao_informado=True), nullable=True),
        "total_questoes": Column("Int64", Check.in_range(1, 300), nullable=True),
        "tempo_limite_min": Column("Int64", Check.in_range(1, 600), nullable=True),
    }, strict=False, coerce=False),

    "resultados_sim": DataFrameSchema({
        "resultado_id": _pk("resultado_id"),
        "simulado_id": ID, "aluno_id": ID, "ano": ANO,
        "status_realizacao": Column(object, _cat(["Finalizado", "Ausente", "Incompleto"], nao_informado=True), nullable=True),
        "nota": Column(float, Check.in_range(0, 100), nullable=True),
        "acertos": Column("Int64", Check.ge(0), nullable=True),
        "dispositivo": Column(object, _cat(["Celular", "Desktop", "Papel", "Tablet"], nao_informado=True), nullable=True),
        "unidade_aplicacao": Column(object, _cat(["Aldeota", "Centro", "Online", "Sul"], nao_informado=True), nullable=True),
    }, strict=False, coerce=False),

    "aulas": DataFrameSchema({
        "aula_id": _pk("aula_id"),
        "oferta_id": ID, "ano": ANO, "professor_id": ID,
        "materia": Column(object, _cat(_MATERIA), nullable=True),
        "modalidade_aula": Column(object, _cat(cl.MODALIDADE.values(), nao_informado=True), nullable=True),
    }, strict=False, coerce=False),

    "presencas_aulas": DataFrameSchema({
        "presenca_id": _pk("presenca_id"),
        "aula_id": ID, "aluno_id": ID,
        "status_presenca": Column(object, _cat(["Presente", "Atrasado", "Ausente", "Justificado"], nao_informado=True), nullable=True),
        "atraso_min": Column(float, Check.ge(0), nullable=True),
    }, strict=False, coerce=False),
}


def validar(tabelas: dict) -> dict[str, list[str]]:
    """Valida cada tabela contra seu schema. Retorna {tabela: [erros]} (vazio = ok)."""
    erros: dict[str, list[str]] = {}
    for nome, schema in SCHEMAS.items():
        if nome not in tabelas:
            continue
        try:
            schema.validate(tabelas[nome], lazy=True)
        except pa.errors.SchemaErrors as e:
            erros[nome] = e.failure_cases[["column", "check", "failure_case"]].astype(str) \
                .drop_duplicates().apply(lambda r: f"{r['column']} | {r['check']} | {r['failure_case']}", axis=1).tolist()
    return erros
