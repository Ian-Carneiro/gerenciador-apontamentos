"""Mesclagem e ajuste de apontamentos locais + Mikael"""

from dataclasses import dataclass
from datetime import datetime

from config import MIKAEL_GAP_THRESHOLD_MIN


@dataclass
class Intervalo:
    """Um intervalo de trabalho normalizado, de origem local (banco) ou Mikael."""

    inicio: datetime
    fim: datetime
    origem: str  # "local" | "mikael"
    projeto: str = ""
    tarefa: str = ""
    nota: str = ""
    id_local: int | None = None  # id do registro no banco (se origem=="local")


@dataclass
class AjusteGap:
    """Representa um gap entre dois intervalos adjacentes e o ajuste proposto."""

    idx_anterior: int  # índice em lista de Intervalo
    idx_proximo: int
    gap_segundos: int
    descricao: str  # texto legível para a UI
    aplicar: bool  # default baseado no threshold


def _parse_hora(h: str) -> datetime:
    """Converte "HH:MM:SS" para datetime (data base 1900-01-01)."""
    return datetime.strptime(h, "%H:%M:%S")


def _fmt_hora(dt: datetime) -> str:
    """Formata um datetime (data base 1900-01-01) de volta para "HH:MM:SS"."""
    return dt.strftime("%H:%M:%S")


def _nota_mikael(apt: dict) -> str:
    """Monta a nota do apontamento a partir dos campos chamado/título/justificativa do Mikael, um por linha."""
    linhas = []
    if apt.get("ocorrencia"):
        linhas.append(f"Chamado: {apt['ocorrencia']}")
    if apt.get("titulo"):
        linhas.append(f"Título: {apt['titulo']}")
    if apt.get("justificativa"):
        linhas.append(f"Justificativa: {apt['justificativa']}")
    return "\n".join(linhas)


def construir_intervalos_locais(apontamentos_db: list) -> list[Intervalo]:
    """
    Converte registros ORM (Apontamento) em Intervalo.
    Ignora apontamentos sem fim e os do projeto Mikael.
    """
    resultado = []
    for apt in apontamentos_db:
        if not apt.fim:
            continue
        if apt.projeto == "Mikael Apontamentos":
            continue
        resultado.append(
            Intervalo(
                inicio=datetime.combine(apt.inicio.date(), apt.inicio.time()).replace(
                    year=1900, month=1, day=1
                ),
                fim=datetime.combine(apt.fim.date(), apt.fim.time()).replace(
                    year=1900, month=1, day=1
                ),
                origem="local",
                projeto=apt.projeto or "",
                tarefa=apt.tarefa or "",
                nota=apt.nota or "",
                id_local=apt.id,
            )
        )
    return sorted(resultado, key=lambda x: x.inicio)


def construir_intervalos_mikael(apontamentos_mikael: list[dict]) -> list[Intervalo]:
    """
    Converte dicts do Mikael em pares de Intervalo (entrada/saída alternados).
    """
    horas = [a["hora_str"] for a in apontamentos_mikael]
    meta = apontamentos_mikael  # mesmo índice

    resultado = []
    for i in range(0, len(horas) - 1, 2):
        ini = _parse_hora(horas[i])
        fim = _parse_hora(horas[i + 1])
        apt = meta[i]
        resultado.append(
            Intervalo(
                inicio=ini,
                fim=fim,
                origem="mikael",
                projeto="Mikael Apontamentos",
                tarefa=f"{apt.get('codigo', '') or ''} - {apt.get('projeto', '') or ''}".strip(
                    " -"
                ),
                nota=_nota_mikael(apt),
            )
        )
    return sorted(resultado, key=lambda x: x.inicio)


def mesclar(locais: list[Intervalo], mikael: list[Intervalo]) -> list[Intervalo]:
    """
    Junta locais + mikael, ordena por início.
    Remove apenas locais totalmente englobados por um único intervalo Mikael.
    Sobreposições parciais NÃO são resolvidas aqui — ficam com os horários
    originais e só são fechadas em aplicar_ajustes(), respeitando o checkbox.
    """

    def engolido(loc: Intervalo) -> bool:
        return any(mk.inicio <= loc.inicio and loc.fim <= mk.fim for mk in mikael)

    restantes = [loc for loc in locais if not engolido(loc)]

    merged = [iv for iv in restantes + mikael if iv.fim > iv.inicio]
    merged.sort(key=lambda x: x.inicio)
    return merged


def calcular_ajustes(
    intervalos: list[Intervalo],
    apontamentos_db: list,
) -> list[AjusteGap]:
    """
    Calcula o gap entre cada par de intervalos adjacentes (pulando pares
    local-local, que não precisam de ajuste), e monta um AjusteGap por par
    com descrição legível para a UI. `aplicar` já vem marcado como True
    quando a magnitude do gap é menor que MIKAEL_GAP_THRESHOLD_MIN minutos.
    """
    ajustes = []
    for i in range(len(intervalos) - 1):
        atual = intervalos[i]
        proximo = intervalos[i + 1]

        if atual.origem == "local" and proximo.origem == "local":
            continue

        # Usa fim original do banco para calcular gap real
        if atual.origem == "local" and atual.id_local:
            apt_orig = next((a for a in apontamentos_db if a.id == atual.id_local), None)
            fim_atual = (
                _parse_hora(apt_orig.fim.strftime("%H:%M:%S"))
                if apt_orig and apt_orig.fim
                else atual.fim
            )
        else:
            fim_atual = atual.fim

        gap_s = int((proximo.inicio - fim_atual).total_seconds())

        abs_s = abs(gap_s)
        sinal = "-" if gap_s < 0 else ""
        if abs_s >= 60:
            gap_label = (
                f"{sinal}{abs_s // 60}min {abs_s % 60}s"
                if abs_s % 60
                else f"{sinal}{abs_s // 60}min"
            )
        else:
            gap_label = f"{gap_s}s"

        # Quem realmente se move ao fechar o gap: local sempre; Mikael nunca.
        if proximo.origem == "mikael":
            origem_horario, destino_horario = fim_atual, proximo.inicio
        else:
            origem_horario, destino_horario = proximo.inicio, fim_atual

        descricao = (
            f"{_fmt_hora(origem_horario)} → {_fmt_hora(destino_horario)}  "
            f"({gap_label})  "
            f"[{atual.projeto or atual.origem}] ↔ [{proximo.projeto or proximo.origem}]"
        )

        # Critério único: magnitude do gap, independente de sinal ou direção.
        aplicar = abs(gap_s) // 60 < MIKAEL_GAP_THRESHOLD_MIN

        ajustes.append(
            AjusteGap(
                idx_anterior=i,
                idx_proximo=i + 1,
                gap_segundos=gap_s,
                descricao=descricao,
                aplicar=aplicar,
            )
        )
    return ajustes


def aplicar_ajustes(
    intervalos: list[Intervalo],
    ajustes: list[AjusteGap],
) -> list[Intervalo]:
    """
    Para cada ajuste marcado, fecha o gap:
    - Se o próximo é "mikael" (fonte da verdade): estende o fim do anterior até ele.
    - Senão: recua o início do próximo até o fim do anterior.
    """
    for aj in ajustes:
        if not aj.aplicar:
            continue
        anterior = intervalos[aj.idx_anterior]
        proximo = intervalos[aj.idx_proximo]

        if proximo.origem == "mikael":
            # Mikael é a fonte da verdade: o local se estende até ele
            anterior.fim = proximo.inicio
        else:
            # Mikael antes de um local: o local recua o início até o Mikael
            proximo.inicio = anterior.fim

    return intervalos
