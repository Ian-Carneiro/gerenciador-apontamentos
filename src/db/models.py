"""
Modelos ORM — Apontador de Horas v5
SQLAlchemy 2.0 (mapped_column / DeclarativeBase)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Apontamento ──────────────────────────────────────────────────────────────


class Apontamento(Base):
    """
    Um intervalo de trabalho com início e fim na mesma row.
    Elimina o design de pares de linhas do CSV antigo.

    fim IS NULL  → apontamento em execução (no máximo 1 por vez)
    fim NOT NULL → apontamento finalizado
    """

    __tablename__ = "apontamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto: Mapped[str] = mapped_column(String(500), nullable=False)
    tarefa: Mapped[str] = mapped_column(String(500), nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nota: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relacionamento com auditoria
    audits: Mapped[list[ApontamentoAudit]] = relationship(
        "ApontamentoAudit",
        back_populates="apontamento",
        cascade="all, delete-orphan",
        order_by="ApontamentoAudit.alterado_em",
    )

    @property
    def horas(self) -> float | None:
        """Horas trabalhadas (None se ainda em execução)."""
        if self.fim is None:
            return None
        delta = self.fim - self.inicio
        return round(delta.total_seconds() / 3600, 4)

    @property
    def em_execucao(self) -> bool:
        return self.fim is None

    @property
    def duracao_str(self) -> str:
        """Ex: '2h 30min', '45min', '30s' ou 'Em execucao'."""
        if self.horas is None:
            return "Em execucao"
        total_s = int((self.fim - self.inicio).total_seconds())
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        if h > 0 and m > 0:
            return f"{h}h {m:02d}min"
        if h > 0:
            return f"{h}h"
        if m > 0:
            return f"{m}min"
        return f"{s}s"

    def __repr__(self) -> str:
        fim_str = self.fim.strftime("%H:%M") if self.fim else "…"
        return (
            f"<Apontamento id={self.id} "
            f"{self.inicio.strftime('%Y-%m-%d %H:%M')}→{fim_str} "
            f"[{self.projeto[:20]}]>"
        )


# ─── Auditoria ────────────────────────────────────────────────────────────────


class ApontamentoAudit(Base):
    """
    Registro imutável de cada alteração feita num Apontamento.
    Permite Undo/Redo e rastreabilidade.
    """

    __tablename__ = "apontamentos_audit"

    CAMPOS_VALIDOS = frozenset({"projeto", "tarefa", "inicio", "fim", "nota", "parada"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    apontamento_id: Mapped[int] = mapped_column(ForeignKey("apontamentos.id", ondelete="CASCADE"))
    campo: Mapped[str] = mapped_column(String(50), nullable=False)
    valor_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_novo: Mapped[str | None] = mapped_column(Text, nullable=True)
    alterado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    apontamento: Mapped[Apontamento] = relationship("Apontamento", back_populates="audits")

    def __repr__(self) -> str:
        return (
            f"<Audit id={self.id} apt={self.apontamento_id} "
            f"campo={self.campo} {self.valor_anterior!r}→{self.valor_novo!r}>"
        )


# ─── Projetos / Tarefas ───────────────────────────────────────────────────────


class ProjetoTarefa(Base):
    """
    Cache local dos projetos/tarefas baixados do NetProject (XMLs).
    Substitui projetos_tarefas.csv.
    """

    __tablename__ = "projetos_tarefas"
    __table_args__ = (UniqueConstraint("projeto", "tarefa", name="uq_projeto_tarefa"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto: Mapped[str] = mapped_column(String(500), nullable=False)
    tarefa: Mapped[str] = mapped_column(String(500), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    finish_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    percent_complete: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ProjetoTarefa {self.projeto[:20]} / {self.tarefa[:20]}>"


# ─── De/Para ──────────────────────────────────────────────────────────────────


class DePara(Base):
    """
    Regras de substituição de nomes de projeto/tarefa.
    Substitui a seção 'depara' do config_netproject.json.
    Mantemos o JSON também para compatibilidade com o ConfigNetProjectHandler.
    """

    __tablename__ = "depara"
    __table_args__ = (UniqueConstraint("tipo", "de", name="uq_depara_tipo_de"),)

    TIPO_PROJETO = "projeto"
    TIPO_TAREFA = "tarefa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # 'projeto' | 'tarefa'
    de: Mapped[str] = mapped_column(String(500), nullable=False)
    para: Mapped[str] = mapped_column(String(500), nullable=False)

    def __repr__(self) -> str:
        return f"<DePara tipo={self.tipo} {self.de!r}→{self.para!r}>"


# ─── SQLAlchemy event: atualiza atualizado_em automaticamente ─────────────────


@event.listens_for(Apontamento, "before_update")
def _set_atualizado_em(mapper, connection, target: Apontamento):
    target.atualizado_em = datetime.now()
