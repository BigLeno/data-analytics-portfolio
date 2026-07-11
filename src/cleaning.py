"""
cleaning.py - Funções puras de normalização e os dicionários canônicos.

Isoladas do pipeline (transform.py) para serem reutilizáveis e testáveis.
Cada decisão de padronização aqui foi definida a partir do perfilamento dos
dados reais (formatos de data mistos, variações de caixa/acento/abreviação,
CPFs com e sem máscara) — ver relatório gerado pelo transform.py.
"""
from __future__ import annotations

import re
import unicodedata
import pandas as pd

# --------------------------------------------------------------------------- #
# Helpers de texto
# --------------------------------------------------------------------------- #

def strip_collapse(v: str | float) -> str:
    """Remove espaços das pontas e colapsa espaços internos. Vazio -> ''."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def fold(v: str | float) -> str:
    """Chave de comparação: minúsculas, sem acento, só alfanumérico e espaço.

    Ex.: 'MATEMÁTICA', 'Matematica' e 'Mat.' -> 'matematica' / 'mat'.
    """
    s = strip_collapse(v).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s]", "", s)          # remove pontuação (o ponto de 'Mat.')
    return re.sub(r"\s+", " ", s).strip()


def titulo(v: str | float) -> str:
    """Title case para nomes de pessoas/cidades, preservando acentos existentes."""
    s = strip_collapse(v)
    return s.title() if s else ""


# --------------------------------------------------------------------------- #
# Dicionários canônicos (chave = fold do valor sujo -> valor canônico)
# --------------------------------------------------------------------------- #

MATERIA = {
    "matematica": "Matemática", "mat": "Matemática",
    "fisica": "Física",
    "quimica": "Química",
    "biologia": "Biologia",
    "historia": "História",
    "geografia": "Geografia",
    "portugues": "Português",
    "ingles": "Inglês",
    "filosofia": "Filosofia",
    "sociologia": "Sociologia",
    "redacao": "Redação",
}

STATUS_PROFESSOR = {"ativo": "Ativo", "inativo": "Inativo"}
STATUS_MATRICULA = {"ativa": "Ativa", "cancelada": "Cancelada",
                    "concluida": "Concluída", "trancada": "Trancada"}
STATUS_REALIZACAO = {"finalizado": "Finalizado", "ausente": "Ausente",
                     "incompleto": "Incompleto"}
STATUS_PRESENCA = {"presente": "Presente", "atrasado": "Atrasado",
                   "ausente": "Ausente", "justificado": "Justificado"}
DIFICULDADE = {"facil": "Fácil", "media": "Média", "dificil": "Difícil"}
MODALIDADE = {"online": "Online", "presencial": "Presencial", "hibrido": "Híbrido"}
ESCOLA_ORIGEM = {"publica": "Pública", "privada": "Privada",
                 "federal": "Federal", "nao informado": "Não informado"}
SIM_NAO = {"sim": "Sim", "nao": "Não", "parcial": "Parcial"}
UNIDADE = {"aldeota": "Aldeota", "centro": "Centro", "online": "Online", "sul": "Sul"}
DISPOSITIVO = {"celular": "Celular", "desktop": "Desktop",
               "papel": "Papel", "tablet": "Tablet"}
CANAL = {"instagram": "Instagram", "google": "Google", "indicacao": "Indicação",
         "whatsapp": "WhatsApp", "feira escolar": "Feira escolar"}
# Universidades são siglas -> canônico em CAIXA ALTA (tratado à parte).
CIDADE = {  # apenas as que perdem acento no fold; demais caem no title case
    "fortaleza": "Fortaleza", "maracanau": "Maracanaú", "eusebio": "Eusébio",
    "juazeiro do norte": "Juazeiro do Norte", "sobral": "Sobral",
    "caucaia": "Caucaia", "crato": "Crato", "horizonte": "Horizonte",
    "aquiraz": "Aquiraz", "itapipoca": "Itapipoca", "pacatuba": "Pacatuba",
}


def normalizar(valor: str | float, mapa: dict[str, str],
               default: str | None = "Não informado") -> str | None:
    """Mapeia um valor sujo para o canônico via fold(). Vazio -> default.

    Se o valor não estiver no mapa (categoria nova/inesperada), devolve a
    versão só com espaços normalizados — nunca descarta silenciosamente.
    """
    f = fold(valor)
    if f == "":
        return default
    return mapa.get(f, strip_collapse(valor))


def normalizar_universidade(valor: str | float) -> str | None:
    f = fold(valor)
    return f.upper() if f else None


def normalizar_cidade(valor: str | float) -> str | None:
    f = fold(valor)
    if f == "":
        return None
    return CIDADE.get(f, titulo(valor))


# --------------------------------------------------------------------------- #
# Datas (formatos mistos)
# --------------------------------------------------------------------------- #
# Convivem na mesma coluna: ISO (yyyy-mm-dd), yyyy/mm/dd, dd/mm/yyyy, dd-mm-yyyy,
# mm-dd-yyyy e datetimes com hora. Ambiguidade dd/mm vs mm/dd é resolvida pela
# magnitude dos componentes; quando ambos <= 12, assume-se dd/mm (contexto BR).

_RE_YMD = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
_RE_DMY = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$")


def parse_data(v: str | float) -> pd.Timestamp:
    """Converte um valor de data em qualquer formato conhecido para Timestamp.

    Retorna pd.NaT para vazio ou irreconhecível. Ignora a parte de hora.
    """
    s = strip_collapse(v)
    if s == "":
        return pd.NaT
    s = s.split(" ")[0]                       # descarta hora, se houver

    m = _RE_YMD.match(s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = _RE_DMY.match(s)
        if not m:
            return pd.NaT
        a, b, y = map(int, m.groups())
        if a > 12:                            # só pode ser dia
            d, mo = a, b
        elif b > 12:                          # segundo campo só pode ser dia -> mm/dd
            mo, d = a, b
        else:                                 # ambíguo -> padrão brasileiro dd/mm
            d, mo = a, b
    try:
        return pd.Timestamp(year=y, month=mo, day=d)
    except (ValueError, OverflowError):
        return pd.NaT


def parse_datetime(v: str | float) -> pd.Timestamp:
    """Como parse_data, mas preserva a hora quando presente (ex.: inicio_simulado)."""
    s = strip_collapse(v)
    if s == "":
        return pd.NaT
    partes = s.split(" ")
    data = parse_data(partes[0])
    if data is pd.NaT or len(partes) == 1:
        return data
    m = re.match(r"(\d{1,2}):(\d{2})", partes[1])
    if not m:
        return data
    h, mi = int(m.group(1)), int(m.group(2))
    try:
        return data + pd.Timedelta(hours=h, minutes=mi)
    except ValueError:
        return data


# --------------------------------------------------------------------------- #
# CPF e números
# --------------------------------------------------------------------------- #

def normalizar_cpf(v: str | float) -> str | None:
    """Reduz o CPF a 11 dígitos (forma canônica). Inválidos -> None."""
    s = re.sub(r"\D", "", strip_collapse(v))
    return s.zfill(11) if 0 < len(s) <= 11 else None


def to_num(serie: pd.Series) -> pd.Series:
    """Converte texto para número (vírgula decimal tolerada); vazio/erro -> NaN."""
    return pd.to_numeric(
        serie.astype(str).str.strip().str.replace(",", ".", regex=False)
             .replace("", pd.NA),
        errors="coerce",
    )
