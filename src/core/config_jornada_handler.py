"""
ConfigJornadaHandler — Singleton de configuração da jornada de trabalho.

Segue o mesmo padrão do ConfigNetProjectHandler: config simples,
persistida em JSON (data/config_jornada.json), sem precisar de tabela no banco.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json

import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

_ARQUIVO = config.DATA_DIR / "config_jornada.json"

_PADRAO = {
    "jornada_horas_dia": 8.0,
    "banco_horas_meses": 4,
    "banco_horas_dia_corte": 26,  # período: dia_corte/mês até (corte-1)/mês+N
    "banco_horas_ancora": "2026-07-26",  # data ISO, ex: "2026-07-26"
    "dias_trabalho": [0, 1, 2, 3, 4],
}


@dataclass
class ConfigJornada:
    """Configuração da jornada de trabalho: carga horária, dias úteis e período do banco de horas."""

    jornada_horas_dia: float
    banco_horas_meses: int
    banco_horas_dia_corte: int
    banco_horas_ancora: date
    dias_trabalho: list[int]


class ConfigJornadaHandler:
    """Singleton — use os métodos de classe, não instancie."""

    _cache: ConfigJornada | None = None

    @classmethod
    def obter(cls) -> ConfigJornada:
        """Retorna a config em cache, carregando do arquivo (ou padrão) na primeira chamada."""
        if cls._cache is None:
            cls._cache = cls._carregar()
        return cls._cache

    @classmethod
    def salvar(
        cls,
        jornada_horas_dia: float,
        banco_horas_meses: int,
        banco_horas_ancora: date,
        dias_trabalho: list[int],
    ) -> ConfigJornada:
        """
        Persiste a config em disco (JSON) e atualiza o cache.
        `banco_horas_dia_corte` é derivado de `banco_horas_ancora.day`.
        """
        cfg = ConfigJornada(
            jornada_horas_dia=jornada_horas_dia,
            banco_horas_meses=banco_horas_meses,
            banco_horas_dia_corte=banco_horas_ancora.day,
            banco_horas_ancora=banco_horas_ancora,
            dias_trabalho=sorted(dias_trabalho),
        )
        dados = asdict(cfg)
        dados["banco_horas_ancora"] = cfg.banco_horas_ancora.isoformat()
        _ARQUIVO.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        cls._cache = cfg
        logger.info(f"⚙️  Config de jornada salva: {dados}")
        return cfg

    @classmethod
    def _carregar(cls) -> ConfigJornada:
        """Lê a config do JSON em disco; se o arquivo não existir, usa os valores padrão."""
        if not _ARQUIVO.exists():
            logger.warning("Config de jornada não encontrada, usando padrão.")
            dados = dict(_PADRAO)
        else:
            dados = json.loads(_ARQUIVO.read_text(encoding="utf-8"))
        return ConfigJornada(
            jornada_horas_dia=float(dados["jornada_horas_dia"]),
            banco_horas_meses=int(dados["banco_horas_meses"]),
            banco_horas_dia_corte=int(dados.get("banco_horas_dia_corte", 26)),
            banco_horas_ancora=date.fromisoformat(
                dados.get("banco_horas_ancora") or date.today().isoformat()
            ),
            dias_trabalho=list(dados["dias_trabalho"]),
        )
