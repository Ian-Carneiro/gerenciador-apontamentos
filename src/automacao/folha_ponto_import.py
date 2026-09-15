"""Importação de apontamentos históricos a partir do Espelho de Ponto (SGIWeb PDF)"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

import pdfplumber

_DIA_RE = re.compile(r"^(\d{2}/\d{2}) \((\w+)\)\s+(.+?)\s+(-?\d+\.\d{2}|-)$")
_HORA_RE = re.compile(r"^\d{2}h\d{2}$")
_PERIODO_RE = re.compile(r"Período: (\d{2}/\d{2}/\d{2}) a (\d{2}/\d{2}/\d{2})")

PROJETO_HISTORICO = "Histórico (folha de ponto)"


def _resolver_ano(dia_mes: str, ano_ini: str, mes_ini: str, ano_fim: str) -> str:
    """Período sempre cobre 2 meses seguidos; usa o mês pra decidir o ano certo."""
    _, mes = dia_mes.split("/")
    return ano_ini if mes == mes_ini else ano_fim


def parse_espelho_ponto(caminho: Path) -> dict[str, list[tuple[str, str]]]:
    """
    Lê o PDF do Espelho de Ponto e retorna, por data ("%d/%m/%Y"),
    a lista de pares (entrada, saída) em "HH:MM:SS".
    Ignora linhas de "Erro no dia ..." e dias sem marcação.
    """
    with pdfplumber.open(caminho) as pdf:
        texto_p1 = pdf.pages[0].extract_text() or ""
        if not texto_p1.strip():
            raise ValueError(
                "PDF sem camada de texto (fontes provavelmente vetorizadas/outline "
                "na exportação). Gere o Espelho de Ponto novamente a partir do "
                "navegador (Ctrl+P > Salvar como PDF) sem usar impressora virtual "
                "ou redução de tamanho de arquivo."
            )
        periodo = _PERIODO_RE.search(texto_p1)
        if not periodo:
            raise ValueError("Não foi possível identificar o período no PDF.")
        ini, fim = periodo.groups()  # "26/08/26"
        ano_ini, mes_ini = "20" + ini.split("/")[2], ini.split("/")[1]
        ano_fim = "20" + fim.split("/")[2]

        resultado: dict[str, list[tuple[str, str]]] = {}
        for page in pdf.pages:
            for linha in page.extract_text().split("\n"):
                m = _DIA_RE.match(linha.strip())
                if not m:
                    continue
                dia_mes, _dow, marcacoes, _saldo = m.groups()
                tokens = marcacoes.split()
                if len(tokens) != 6:
                    continue

                pares = []
                for i in range(0, 6, 2):
                    entrada, saida = tokens[i], tokens[i + 1]
                    if _HORA_RE.match(entrada) and _HORA_RE.match(saida):
                        pares.append(
                            (
                                entrada.replace("h", ":") + ":00",
                                saida.replace("h", ":") + ":00",
                            )
                        )

                if not pares:
                    continue

                ano = _resolver_ano(dia_mes, ano_ini, mes_ini, ano_fim)
                data_str = f"{dia_mes}/{ano}"  # "26/08/2026"
                resultado[data_str] = pares

        return resultado


@dataclass
class RegistroHistorico:
    data: date
    inicio: str  # "HH:MM:SS"
    fim: str
    ja_existe: bool = False  # já há apontamento local nesse dia (candidato a duplicata)

    @property
    def horas(self) -> float:
        ini = datetime.strptime(self.inicio, "%H:%M:%S")
        fim = datetime.strptime(self.fim, "%H:%M:%S")
        return (fim - ini).total_seconds() / 3600


def construir_registros(
    dados: dict[str, list[tuple[str, str]]],
    repo,
) -> list[RegistroHistorico]:
    """Converte o resultado de parse_espelho_ponto() em linhas de preview,
    marcando dias que já têm apontamento local no banco."""
    registros = []
    for data_str, pares in sorted(
        dados.items(), key=lambda kv: datetime.strptime(kv[0], "%d/%m/%Y")
    ):
        dia = datetime.strptime(data_str, "%d/%m/%Y").date()
        ja_existe = bool(repo.obter_por_dia(dia))
        for inicio, fim in pares:
            registros.append(
                RegistroHistorico(data=dia, inicio=inicio, fim=fim, ja_existe=ja_existe)
            )
    return registros


if __name__ == "__main__":
    print(parse_espelho_ponto(Path("<Path>")))
