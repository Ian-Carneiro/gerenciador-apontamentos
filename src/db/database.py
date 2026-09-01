# -*- coding: utf-8 -*-
"""
Configuração do Engine SQLAlchemy e fábrica de sessões.

Uso:
    from src.db.database import get_session, init_db

    init_db()                     # chamado 1x no bootstrap
    with get_session() as session:
        apontamentos = session.scalars(select(Apontamento)).all()
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base

# ── Localização do banco ───────────────────────────────────────────────────────

def _db_path() -> Path:
    """Retorna o caminho do arquivo SQLite baseado em config.py (se disponível)."""
    try:
        import config
        db_path = config.DATA_DIR / "apontamentos.db"
    except ImportError:
        # Fallback para testes ou execução isolada
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).resolve().parents[3]
        db_path = base / "data" / "apontamentos.db"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


# ── Engine singleton ───────────────────────────────────────────────────────────

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def _get_engine(db_path: Path | None = None) -> Engine:
    global _engine
    if _engine is None:
        path = db_path or _db_path()
        _engine = create_engine(
            f"sqlite:///{path}",
            # Pool de conexões: para SQLite com threads (PySide6 usa QThread)
            connect_args={"check_same_thread": False},
            # Echo apenas em modo DEBUG
            echo=False,
        )
        _configure_sqlite(_engine)
    return _engine


def _configure_sqlite(engine: Engine) -> None:
    """Aplica PRAGMAs de performance e integridade no SQLite."""
    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")    # WAL: melhor concorrência
        cursor.execute("PRAGMA foreign_keys=ON")      # Integridade referencial
        cursor.execute("PRAGMA synchronous=NORMAL")   # Equilíbrio performance/segurança
        cursor.execute("PRAGMA cache_size=-32000")    # 32MB cache
        cursor.close()


def _get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=_get_engine(), expire_on_commit=False)
    return _SessionFactory


# ── API pública ───────────────────────────────────────────────────────────────

def init_db(db_path: Path | None = None) -> None:
    """
    Cria todas as tabelas se não existirem.
    Chame uma vez no bootstrap da aplicação (main.py).
    """
    engine = _get_engine(db_path)
    Base.metadata.create_all(engine)
    _apply_indexes(engine)


def _apply_indexes(engine: Engine) -> None:
    """Cria índices de performance que não estão no ORM."""
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_apt_inicio "
            "ON apontamentos(inicio DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_apt_projeto "
            "ON apontamentos(projeto)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_apt_fim_null "
            "ON apontamentos(fim) WHERE fim IS NULL"
        ))
        conn.commit()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager que abre uma sessão e faz commit/rollback automaticamente.

    Uso:
        with get_session() as s:
            s.add(obj)
            # commit automático ao sair do bloco sem exceção
    """
    factory = _get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests(db_path: Path) -> None:
    """
    Reinicia o engine apontando para um banco de testes.
    Use apenas em testes unitários.
    """
    global _engine, _SessionFactory
    _engine = None
    _SessionFactory = None
    _get_engine(db_path)