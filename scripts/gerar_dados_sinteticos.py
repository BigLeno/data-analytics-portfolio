"""
gerar_dados_sinteticos.py - Gera uma base FICTÍCIA no formato dos CSVs brutos.

Cria em data/raw/ os 9 CSVs que o extract.py reconhece como "base completa",
com o mesmo layout de colunas e os mesmos tipos de sujeira que o tratamento
corrige: datas em formatos mistos, categorias com caixa/acento/abreviação
variados, CPFs com e sem máscara, decimais com vírgula, notas fora de faixa,
PKs repetidas, nomes de professor divergentes do cadastro e linhas marcadas
como "Cadastro duplicado?".

Nada aqui representa pessoas ou instituições reais: nomes, CPFs, e-mails e
telefones são inventados. A aprovação segue um modelo simples (aptidão latente
+ anos de permanência), para que as análises e o score tenham algum sinal.

Uso:
    python scripts/gerar_dados_sinteticos.py                 # ~800 alunos
    python scripts/gerar_dados_sinteticos.py --alunos 150 --seed 7 --saida /tmp/raw
"""
from __future__ import annotations

import argparse
import csv
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
MARCADOR = "DADOS_SINTETICOS.txt"

ANOS = [2021, 2022, 2023, 2024, 2025]
UNIDADES = ["Aldeota", "Centro", "Online", "Sul"]

# valor canônico -> variações sujas que o cleaning.py precisa reconhecer
MATERIAS = {
    "Matemática": ["Matemática", "MATEMÁTICA", "matematica", "Mat.", " Matemática "],
    "Física": ["Física", "fisica", "FÍSICA"],
    "Química": ["Química", "quimica", "QUIMICA"],
    "Biologia": ["Biologia", "biologia", "BIOLOGIA "],
    "História": ["História", "historia", "HISTÓRIA"],
    "Geografia": ["Geografia", "geografia", "GEOGRAFIA"],
    "Português": ["Português", "portugues", "PORTUGUÊS"],
    "Inglês": ["Inglês", "ingles", "INGLÊS"],
    "Filosofia": ["Filosofia", "filosofia"],
    "Sociologia": ["Sociologia", "sociologia"],
    "Redação": ["Redação", "redacao", "REDAÇÃO"],
}
SUJO = {
    "unidade": {u: [u, u.upper(), u.lower(), f" {u}"] for u in UNIDADES},
    "modalidade": {"Online": ["Online", "online", "ONLINE"],
                   "Presencial": ["Presencial", "presencial", "PRESENCIAL"],
                   "Híbrido": ["Híbrido", "hibrido", "HÍBRIDO", "Hibrido"]},
    "escola": {"Pública": ["Pública", "publica", "PÚBLICA"], "Privada": ["Privada", "privada"],
               "Federal": ["Federal", "federal"], "": ["", " ", "Não informado"]},
    "canal": {"Instagram": ["Instagram", "instagram", "INSTAGRAM"], "Google": ["Google", "google"],
              "Indicação": ["Indicação", "indicacao", "INDICAÇÃO"],
              "WhatsApp": ["WhatsApp", "whatsapp", "Whatsapp"],
              "Feira escolar": ["Feira escolar", "feira escolar", "Feira Escolar"], "": [""]},
    "status_mat": {"Ativa": ["Ativa", "ativa"], "Concluída": ["Concluída", "concluida", "CONCLUÍDA"],
                   "Cancelada": ["Cancelada", "cancelada"], "Trancada": ["Trancada", "TRANCADA"]},
    "presenca": {"Presente": ["Presente", "presente", "PRESENTE"], "Atrasado": ["Atrasado", "atrasado"],
                 "Ausente": ["Ausente", "ausente"], "Justificado": ["Justificado", "justificado"]},
    "realizacao": {"Finalizado": ["Finalizado", "finalizado", "FINALIZADO"],
                   "Incompleto": ["Incompleto", "incompleto"], "Ausente": ["Ausente", "ausente"]},
    "dispositivo": {"Celular": ["Celular", "celular"], "Desktop": ["Desktop", "desktop", "DESKTOP"],
                    "Papel": ["Papel", "papel"], "Tablet": ["Tablet", "tablet"]},
    "dificuldade": {"Fácil": ["Fácil", "facil"], "Média": ["Média", "media", "MÉDIA"],
                    "Difícil": ["Difícil", "dificil"]},
    "vaga": {"Ampla concorrência": ["Ampla concorrência", "ampla concorrencia", "AMPLA CONCORRÊNCIA"],
             "Cota escola pública": ["Cota escola pública", "cota escola publica"],
             "PPI": ["PPI", "ppi"], "PCD": ["PCD", "pcd"]},
    "chamada": {"1ª chamada": ["1a chamada", "1A CHAMADA", "1ª chamada"],
                "2ª chamada": ["2a chamada", "2ª chamada"], "Lista de espera": ["Lista de espera", "lista de espera"],
                "SISU": ["SISU", "Sisu", "sisu"], "Vestibular próprio": ["Vestibular próprio", "vestibular proprio"]},
    "sim_nao": {"Sim": ["Sim", "sim", "SIM"], "Não": ["Não", "nao", "NÃO"], "Parcial": ["Parcial", "parcial"]},
}
CIDADES = {
    "Fortaleza": ["Fortaleza", "fortaleza", "FORTALEZA"], "Maracanaú": ["Maracanaú", "maracanau"],
    "Eusébio": ["Eusébio", "eusebio"], "Caucaia": ["Caucaia", "caucaia"], "Sobral": ["Sobral", "SOBRAL"],
    "Juazeiro do Norte": ["Juazeiro do Norte", "juazeiro do norte"], "Crato": ["Crato"],
    "Horizonte": ["Horizonte"], "Aquiraz": ["Aquiraz", "aquiraz"], "Itapipoca": ["Itapipoca"],
    "Pacatuba": ["Pacatuba"],
}
UNIVERSIDADES = {"UFC": ["UFC", "ufc", "U.F.C."], "UECE": ["UECE", "uece", "Uece"], "IFCE": ["IFCE", "ifce"],
                 "UNIFOR": ["UNIFOR", "Unifor"], "UFCA": ["UFCA", "ufca"], "URCA": ["URCA"], "UVA": ["UVA", "uva"]}
CURSOS = ["Medicina", "Direito", "Engenharia Civil", "Ciência da Computação", "Enfermagem", "Psicologia",
          "Administração", "Odontologia", "Arquitetura", "Pedagogia", "Nutrição", "Engenharia Elétrica"]
TEMAS = ["Revisão geral", "Funções", "Cinemática", "Estequiometria", "Genética", "Brasil Colônia",
         "Cartografia", "Interpretação de texto", "Reading", "Ética", "Movimentos sociais", "Dissertação"]
PRENOMES = ["Ana", "Bruno", "Carla", "Davi", "Elisa", "Felipe", "Gabriela", "Heitor", "Isabela", "João",
            "Larissa", "Mateus", "Natália", "Otávio", "Paula", "Rafael", "Sofia", "Tiago", "Vitória", "Yuri"]
SOBRENOMES = ["Almeida", "Barbosa", "Cardoso", "Dias", "Esteves", "Freitas", "Gomes", "Holanda", "Lima",
              "Moreira", "Nogueira", "Oliveira", "Pereira", "Queiroz", "Rocha", "Sampaio", "Teixeira", "Vieira"]


def _somar_dias(ts: pd.Timestamp, dias: int) -> pd.Timestamp:
    """Soma dias pelo ordinal (evita aritmética de timedelta do NumPy)."""
    return pd.Timestamp.fromordinal(ts.toordinal() + dias)


def _ascii(texto: str) -> str:
    """Minúsculas sem acento (para montar e-mails fictícios)."""
    s = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


class Gerador:
    def __init__(self, alunos: int, seed: int):
        self.n_alunos = alunos
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------ helpers
    def escolha(self, seq, p=None):
        return seq[self.rng.choice(len(seq), p=p)]

    def sujo(self, canonico: str, mapa: dict[str, list[str]], taxa: float = 0.25) -> str:
        """Devolve o canônico ou, com probabilidade `taxa`, uma variação suja."""
        variacoes = mapa[canonico]
        return self.escolha(variacoes) if self.rng.random() < taxa else variacoes[0]

    def data(self, ts: pd.Timestamp, hora: bool = False) -> str:
        """Formata a data em um dos formatos que convivem na base real."""
        fmts = ["%Y-%m-%d", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"]
        if ts.day > 12:  # mm-dd só quando não há ambiguidade (o parser assume dd/mm)
            fmts.append("%m-%d-%Y")
        s = ts.strftime(self.escolha(fmts))
        if hora or self.rng.random() < 0.05:
            s += ts.strftime(" %H:%M") if hora else " 00:00:00"
        return s

    def dia(self, ano: int, mes_ini: int = 2, mes_fim: int = 11) -> pd.Timestamp:
        ini = pd.Timestamp(ano, mes_ini, 1)
        fim = pd.Timestamp(ano, mes_fim, 28)
        return _somar_dias(ini, int(self.rng.integers(0, (fim - ini).days + 1)))

    def num(self, v: float, casas: int = 1) -> str:
        """Número como texto; às vezes com vírgula decimal."""
        s = f"{v:.{casas}f}"
        return s.replace(".", ",") if self.rng.random() < 0.15 else s

    def nome(self) -> str:
        n = f"{self.escolha(PRENOMES)} {self.escolha(SOBRENOMES)} {self.escolha(SOBRENOMES)}"
        r = self.rng.random()
        return n.upper() if r < 0.1 else n.lower() if r < 0.2 else f"  {n} " if r < 0.25 else n

    def cpf(self) -> str:
        d = "".join(str(x) for x in self.rng.integers(0, 10, 11))
        r = self.rng.random()
        if r < 0.4:
            return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
        return d.lstrip("0") if r < 0.45 else d   # sem zeros à esquerda: zfill recupera

    # ------------------------------------------------------------------ tabelas
    def professores(self) -> list[dict]:
        linhas = []
        canon = list(MATERIAS)
        for i in range(1, 45):
            principal = canon[(i - 1) % len(canon)]
            extras = list(self.rng.choice(canon, size=int(self.rng.integers(0, 3)), replace=False))
            ensina = [principal] + [m for m in extras if m != principal]
            nome = f"{self.escolha(PRENOMES)} {self.escolha(SOBRENOMES)}"
            email = f"{_ascii(nome.split()[0])}.{i}@aprovaedu.example"
            linhas.append({
                "professor_id": f"P{i:03d}", "nome_professor": nome,
                "email_professor": email.upper() if self.rng.random() < 0.1 else email,
                "materia_principal": self.sujo(principal, MATERIAS),
                "materias_ensina": ";".join(self.sujo(m, MATERIAS) for m in ensina),
                "data_contratacao": self.data(self.dia(int(self.rng.integers(2015, 2024)), 1, 12)),
                "status_professor": self.escolha(["Ativo", "ativo", "ATIVO", "Inativo", "inativo"],
                                                 p=[.6, .15, .1, .1, .05]),
                "unidade_base": self.sujo(self.escolha(UNIDADES), SUJO["unidade"]),
                "carga_horaria_semanal": str(int(self.rng.choice([12, 20, 30, 40]))),
                "observacoes": self.escolha(["", "", "", "Coordena a área", "Plantão de dúvidas"]),
            })
        self.prof = pd.DataFrame(linhas)
        self.prof["materia_canon"] = [canon[(i - 1) % len(canon)] for i in range(1, 45)]
        self.prof["nome_canon"] = self.prof["nome_professor"]
        return linhas

    def nome_informado(self, professor_id: str) -> str:
        nome = self.prof.loc[self.prof["professor_id"] == professor_id, "nome_canon"].iloc[0]
        r = self.rng.random()
        if r < 0.05:
            return f"{self.escolha(PRENOMES)} {self.escolha(SOBRENOMES)}"   # divergente do cadastro
        return nome.upper() if r < 0.2 else nome

    def estudantes(self) -> list[dict]:
        linhas, alunos = [], []
        for i in range(1, self.n_alunos + 1):
            ingresso = int(self.rng.choice(ANOS, p=[.24, .22, .2, .18, .16]))
            anos_possiveis = 2025 - ingresso + 1
            permanencia = int(min(anos_possiveis, self.rng.choice([1, 2, 3], p=[.62, .28, .10])))
            escola = self.escolha(["Pública", "Privada", "Federal", ""], p=[.55, .3, .1, .05])
            canal = self.escolha(list(SUJO["canal"]), p=[.3, .2, .2, .15, .1, .05])
            alunos.append({
                "aluno_id": f"A{i:04d}", "ingresso": ingresso, "permanencia": permanencia,
                "aptidao": self.rng.normal(0, 1) + (0.3 if escola == "Privada" else 0),
                "engajamento": self.rng.beta(8, 2),
            })
            cidade = self.escolha(list(CIDADES), p=[.45, .1, .07, .08, .06, .06, .04, .04, .04, .03, .03])
            telefone = f"(85) 9{self.rng.integers(1000, 9999)}-{self.rng.integers(1000, 9999)}"
            linhas.append({
                "aluno_id": f"A{i:04d}", "nome_aluno": self.nome(), "cpf_ficticio": self.cpf(),
                "email_aluno": f"aluno{i}@email.example" if self.rng.random() > 0.03 else "",
                "telefone": telefone if self.rng.random() > 0.05 else "",
                "data_nascimento": self.data(self.dia(ingresso - int(self.rng.integers(16, 21)), 1, 12)),
                "cidade": self.sujo(cidade, CIDADES, 0.3),
                "escola_origem": self.escolha(SUJO["escola"][escola]) if escola == "" else self.sujo(escola, SUJO["escola"]),
                "data_cadastro": self.data(self.dia(ingresso - 1, 11, 12) if self.rng.random() < 0.3
                                           else self.dia(ingresso, 1, 2)),
                "canal_captacao": self.sujo(canal, SUJO["canal"]) if canal else "",
            })
        self.alunos = pd.DataFrame(alunos)
        return linhas

    def ofertas(self) -> list[dict]:
        linhas, i = [], 0
        for ano in ANOS:
            for unidade in UNIDADES:
                for materia in MATERIAS:
                    if self.rng.random() < 0.15:     # nem toda unidade oferta tudo
                        continue
                    i += 1
                    profs = self.prof.loc[self.prof["materia_canon"] == materia, "professor_id"].tolist()
                    pid = self.escolha(profs)
                    modalidade = "Online" if unidade == "Online" else \
                        self.escolha(["Presencial", "Híbrido", "Online"], p=[.6, .3, .1])
                    ini = _somar_dias(pd.Timestamp(ano, 2, 1), int(self.rng.integers(0, 20)))
                    linhas.append({
                        "oferta_id": f"OF{i:04d}", "ano": str(ano),
                        "turma": f"{materia[:3].upper()}-{ano}-{unidade[:2].upper()}",
                        "turno": self.escolha(["Manhã", "Tarde", "Noite"]),
                        "unidade": self.sujo(unidade, SUJO["unidade"]),
                        "materia": self.sujo(materia, MATERIAS), "modalidade": self.sujo(modalidade, SUJO["modalidade"]),
                        "carga_horaria_total": str(int(self.rng.choice([60, 80, 120]))),
                        "preco_lista": self.num(float(self.rng.choice([890, 1190, 1490, 1790])), 0),
                        "data_inicio": self.data(ini), "data_fim": self.data(pd.Timestamp(ano, 11, 20)),
                        "professor_id": pid, "professor_nome_informado": self.nome_informado(pid),
                        "x_ano": ano, "x_materia": materia, "x_unidade": unidade,
                    })
        self.of = pd.DataFrame(linhas)
        return [{k: v for k, v in r.items() if not k.startswith("x_")} for r in linhas]

    def matriculas(self) -> list[dict]:
        linhas, i = [], 0
        self.mat_ref = []   # (matricula_id, aluno_id, oferta_id, ano)
        for a in self.alunos.itertuples():
            unidade = self.escolha(UNIDADES, p=[.3, .3, .2, .2])
            bolsa = self.escolha(["0", "0", "25", "50", "100"])
            for ano in range(a.ingresso, a.ingresso + a.permanencia):
                ofs = self.of[(self.of["x_ano"] == ano) & (self.of["x_unidade"] == unidade)]
                k = int(min(len(ofs), self.rng.integers(3, 8)))
                for o in ofs.sample(k, random_state=int(self.rng.integers(1e9))).itertuples():
                    i += 1
                    nota = float(np.clip(55 + 12 * a.aptidao + self.rng.normal(0, 10), 0, 100))
                    if self.rng.random() < 0.02:
                        nota = float(self.rng.choice([-5, 105, 130, 999]))     # outlier
                    status = "Concluída" if ano < 2025 else "Ativa"
                    if self.rng.random() < 0.08:
                        status = self.escolha(["Cancelada", "Trancada"])
                    linhas.append({
                        "matricula_id": f"M{i:05d}", "aluno_id": a.aluno_id, "oferta_id": o.oferta_id,
                        "ano": str(ano), "materia_declarada": self.sujo(o.x_materia, MATERIAS),
                        "data_matricula": self.data(self.dia(ano, 1, 2)),
                        "bolsa_percentual": bolsa if self.rng.random() > 0.1 else self.num(float(bolsa)),
                        "status_matricula": self.sujo(status, SUJO["status_mat"]) if self.rng.random() > 0.02 else "",
                        "nota_diagnostico": self.num(nota) if self.rng.random() > 0.05 else "",
                        "origem_captacao": self.escolha(["Instagram", "google", "Indicação", "whatsapp", ""]),
                    })
                    self.mat_ref.append((a.aluno_id, o.oferta_id, ano))
        return linhas

    def aulas(self) -> list[dict]:
        linhas, i = [], 0
        for o in self.of.itertuples():
            for _ in range(int(self.rng.integers(6, 11))):
                i += 1
                linhas.append({
                    "aula_id": f"AU{i:05d}", "oferta_id": o.oferta_id, "ano": str(o.x_ano),
                    "professor_id": o.professor_id, "data_aula": self.data(self.dia(o.x_ano, 2, 11)),
                    "materia": self.sujo(o.x_materia, MATERIAS), "turma": o.turma,
                    "tema_aula": self.escolha(TEMAS), "duracao_min": str(int(self.rng.choice([50, 90, 100]))),
                    "modalidade_aula": self.sujo(self.escolha(["Presencial", "Online", "Híbrido"]), SUJO["modalidade"]),
                })
        self.au = pd.DataFrame(linhas)
        return linhas

    def presencas(self) -> list[dict]:
        linhas, i = [], 0
        aulas_por_oferta = self.au.groupby("oferta_id")["aula_id"].apply(list).to_dict()
        eng = self.alunos.set_index("aluno_id")["engajamento"].to_dict()
        for aluno_id, oferta_id, _ in self.mat_ref:
            for aula_id in aulas_por_oferta.get(oferta_id, []):
                if self.rng.random() < 0.35:     # nem toda aula tem chamada registrada
                    continue
                i += 1
                p = eng[aluno_id]
                status = self.escolha(["Presente", "Atrasado", "Ausente", "Justificado"],
                                      p=[p * .85, p * .15, (1 - p) * .7, (1 - p) * .3])
                linhas.append({
                    "presenca_id": f"PR{i:06d}", "aula_id": aula_id, "aluno_id": aluno_id,
                    "status_presenca": self.sujo(status, SUJO["presenca"]),
                    "atraso_min": str(int(self.rng.integers(5, 40))) if status == "Atrasado" else
                    ("0" if self.rng.random() < 0.5 else ""),
                    "justificativa": self.escolha(["Atestado médico", "Transporte", "Viagem"])
                    if status == "Justificado" else "",
                })
        return linhas

    def simulados(self) -> list[dict]:
        linhas, i = [], 0
        for ano in ANOS:
            for _ in range(24):
                i += 1
                materia = self.escolha(list(MATERIAS))
                profs = self.prof.loc[self.prof["materia_canon"] == materia, "professor_id"].tolist()
                pid = self.escolha(profs)
                total = int(self.rng.choice([20, 30, 45, 90]))
                linhas.append({
                    "simulado_id": f"S{i:04d}", "ano": str(ano), "data_simulado": self.data(self.dia(ano, 3, 11)),
                    "materia": self.sujo(materia, MATERIAS),
                    "dificuldade": self.sujo(self.escolha(["Fácil", "Média", "Difícil"], p=[.3, .5, .2]), SUJO["dificuldade"]),
                    "tipo_simulado": self.escolha(["Por matéria", "ENEM", "Vestibular local"]),
                    "total_questoes": str(total), "tempo_limite_min": str(total * 3),
                    "tema": self.escolha(TEMAS), "professor_id": pid,
                    "professor_nome_informado": self.nome_informado(pid),
                    "x_ano": ano, "x_total": total,
                })
        self.sim = pd.DataFrame(linhas)
        return [{k: v for k, v in r.items() if not k.startswith("x_")} for r in linhas]

    def resultados(self) -> list[dict]:
        linhas, i = [], 0
        for a in self.alunos.itertuples():
            for ano in range(a.ingresso, a.ingresso + a.permanencia):
                sims = self.sim[self.sim["x_ano"] == ano]
                for s in sims.sample(int(self.rng.integers(4, 12)), random_state=int(self.rng.integers(1e9))).itertuples():
                    i += 1
                    status = self.escolha(["Finalizado", "Incompleto", "Ausente"],
                                          p=[a.engajamento * .9, .08, 1 - a.engajamento * .9 - .08]
                                          if a.engajamento * .9 + .08 <= 1 else [.92, .08, 0])
                    linha = {
                        "resultado_id": f"R{i:06d}", "simulado_id": s.simulado_id, "aluno_id": a.aluno_id,
                        "ano": str(ano), "status_realizacao": self.sujo(status, SUJO["realizacao"]),
                        "nota": "", "acertos": "", "tempo_finalizacao_min": "", "inicio_simulado": "",
                        "dispositivo": self.sujo(self.escolha(list(SUJO["dispositivo"])), SUJO["dispositivo"]),
                        "tentativas": "1" if self.rng.random() < 0.9 else "2",
                        "unidade_aplicacao": self.sujo(self.escolha(UNIDADES), SUJO["unidade"]),
                    }
                    if status != "Ausente":
                        nota = float(np.clip(60 + 13 * a.aptidao + 4 * (ano - a.ingresso) + self.rng.normal(0, 9), 0, 100))
                        acertos = round(nota / 100 * s.x_total)
                        tempo = float(self.rng.uniform(0.4, 1.0) * s.x_total * 3)
                        if self.rng.random() < 0.01:
                            acertos = s.x_total + int(self.rng.integers(1, 5))   # inconsistente
                        if self.rng.random() < 0.02:
                            tempo = s.x_total * 3 + float(self.rng.integers(5, 30))
                        if self.rng.random() < 0.03:
                            nota = float(self.rng.choice([-10, 101, 120, 150]))  # outlier
                        d = self.dia(ano, 3, 11)
                        inicio = pd.Timestamp(d.year, d.month, d.day, int(self.rng.integers(7, 20)),
                                              int(self.rng.integers(0, 60)))
                        linha.update(nota=self.num(nota), acertos=str(acertos),
                                     tempo_finalizacao_min=self.num(tempo), inicio_simulado=self.data(inicio, hora=True))
                    linhas.append(linha)
        return linhas

    def aprovacoes(self) -> list[dict]:
        linhas, i = [], 0
        for a in self.alunos.itertuples():
            ano = a.ingresso + a.permanencia - 1
            logit = -1.2 + 0.9 * a.aptidao + 0.9 * (a.permanencia - 1) + 0.6 * (a.engajamento - 0.8)
            if self.rng.random() > 1 / (1 + np.exp(-logit)):
                continue
            for _ in range(1 if self.rng.random() < 0.85 else 2):   # alguns passam em dois cursos
                i += 1
                uni = self.escolha(list(UNIVERSIDADES), p=[.32, .3, .12, .1, .06, .05, .05])
                linha = {
                    "aprovacao_id": f"AP{i:05d}", "aluno_id": a.aluno_id, "ano_vestibular": str(ano),
                    "universidade": self.escolha(UNIVERSIDADES[uni]), "curso_aprovado": self.escolha(CURSOS),
                    "modalidade_vaga": self.sujo(self.escolha(list(SUJO["vaga"]), p=[.4, .35, .2, .05]), SUJO["vaga"]),
                    "chamada": self.sujo(self.escolha(list(SUJO["chamada"]), p=[.45, .2, .1, .15, .1]), SUJO["chamada"]),
                    "bolsa_aprovacao": self.sujo(self.escolha(["Não", "Sim", "Parcial"], p=[.6, .25, .15]), SUJO["sim_nao"])
                    if uni in ("UNIFOR",) else self.escolha(["Não", "nao", ""]),
                    "data_resultado": self.data(_somar_dias(pd.Timestamp(ano + 1, 1, 1), int(self.rng.integers(10, 60)))),
                    "nota_final_vestibular": self.num(float(np.clip(650 + 70 * a.aptidao + self.rng.normal(0, 40), 400, 1000))),
                    "campus": self.escolha(["Fortaleza", "fortaleza", "Sobral", "Juazeiro do Norte", "Crato"],
                                           p=[.6, .1, .1, .1, .1]),
                }
                linhas.append(linha)
                if self.rng.random() < 0.04:     # duplicata marcada na origem
                    i += 1
                    linhas.append({**linha, "aprovacao_id": f"AP{i:05d}", "chamada": "Cadastro duplicado?"})
        return linhas


def _duplicar_pks(rng: np.random.Generator, linhas: list[dict], taxa: float = 0.003) -> list[dict]:
    """Repete algumas linhas inteiras (PK duplicada) para o dedup_pk tratar."""
    n = max(1, int(len(linhas) * taxa))
    extras = [dict(linhas[j]) for j in rng.choice(len(linhas), size=n, replace=False)]
    return linhas + extras


def _gravar(caminho: Path, linhas: list[dict]) -> None:
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def gerar(saida: Path = RAW_DIR, alunos: int = 800, seed: int = 42) -> dict[str, int]:
    """Gera os 9 CSVs brutos em `saida`. Retorna {arquivo: linhas}."""
    g = Gerador(alunos, seed)
    tabelas = {
        "professores.csv": g.professores(),
        "estudantes.csv": g.estudantes(),
        "ofertas_curso.csv": g.ofertas(),
        "matriculas.csv": g.matriculas(),
        "aulas.csv": g.aulas(),
        "presencas_aulas.csv": g.presencas(),
        "simulados.csv": g.simulados(),
        "resultados_simulados.csv": g.resultados(),
        "aprovacoes_vestibular.csv": g.aprovacoes(),
    }
    for nome in ("matriculas.csv", "resultados_simulados.csv", "presencas_aulas.csv"):
        tabelas[nome] = _duplicar_pks(g.rng, tabelas[nome])

    saida.mkdir(parents=True, exist_ok=True)
    for nome, linhas in tabelas.items():
        _gravar(saida / nome, linhas)
    (saida / MARCADOR).write_text(
        f"Base fictícia gerada por scripts/gerar_dados_sinteticos.py (alunos={alunos}, seed={seed}).\n",
        encoding="utf-8",
    )
    return {nome: len(linhas) for nome, linhas in tabelas.items()}


def main() -> None:
    p = argparse.ArgumentParser(description="Gera uma base fictícia nos CSVs brutos da AprovaEdu.")
    p.add_argument("--alunos", type=int, default=800, help="quantidade de alunos (padrão: 800)")
    p.add_argument("--seed", type=int, default=42, help="semente aleatória (padrão: 42)")
    p.add_argument("--saida", type=Path, default=RAW_DIR, help="pasta de saída (padrão: data/raw)")
    a = p.parse_args()
    contagens = gerar(a.saida, a.alunos, a.seed)
    for nome, n in contagens.items():
        print(f"✅ {nome:28s} {n:>7} linhas")
    print(f"🎲 Base fictícia gravada em {a.saida}")


if __name__ == "__main__":
    main()
