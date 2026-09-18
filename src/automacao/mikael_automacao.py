"""Automação Mikael — download e parse do XLS de apontamentos (Playwright)"""

from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

import config
from src.utils.logger import get_logger

from .page_base import BrowserManager

logger = get_logger(__name__)

_MIKAEL_URL = "https://mikael.synchro.com.br/mikael/"
_SHEET_NAME = "Meus Apontamentos de Horas"
_INTERRUPCAO = "INTERRUPÇÃO DE TRABALHO"
_PROJETO_MIKAEL = "Mikael Apontamentos"


class MikaelPage:
    """Page Object do Mikael: login, navegação até apontamentos e exportação do XLS."""

    def __init__(self, page):
        """Recebe a Page do Playwright já aberta."""
        self.page = page

    def fazer_login(self, usuario: str, senha: str):
        """Preenche usuário/senha na tela inicial e submete o login do Mikael."""
        logger.info("🔐 Fazendo login no Mikael...")
        self.page.goto(_MIKAEL_URL)
        self.page.fill("#loginForm\\:codlogin", usuario)
        self.page.fill("[name='loginForm:password']", senha)
        self.page.click(".ctrlusu-login-btn-entrar")
        logger.info("✅ Login Mikael realizado")

    def navegar_para_apontamentos(self):
        """Navega pelo menu lateral até a tela de 'Meus Apontamentos de Horas'."""
        logger.info("📋 Navegando para apontamentos...")
        self.page.click("#navigationMenuForm\\:navigationTree-d-3")
        self.page.click("#navigationMenuForm\\:navigationTree-d-3-0")
        self.page.wait_for_timeout(2000)

    def exportar_xls(self, destino: Path) -> Path:
        """Aciona o export para Excel na tela de apontamentos e salva o download em `destino`."""
        logger.info("⬇️ Exportando XLS...")
        with self.page.expect_download(timeout=60_000) as dl_info:
            self.page.click('img.iceGphImg[src="/mikael/gui/images/exportar_excel.png"]')
            self.page.wait_for_timeout(3000)
            self.page.click('img.iceGphImg[src="/mikael/gui/images/excel.gif"]')
        download = dl_info.value
        if download.failure():
            raise RuntimeError(f"Falha no download: {download.failure()}")
        download.save_as(destino)
        logger.info(f"✅ XLS salvo em {destino}")
        return destino


def parse_xls(caminho: Path) -> dict[str, list[dict]]:
    """
    Lê o XLS e retorna por data uma lista de dicts:
        {
            "hora_str":    "HH:MM:SS",
            "interrupcao": bool,
            "ocorrencia":  str | None,
            "titulo":      str | None,
            "tarefa":      str | None,
            "codigo":      str | None,
            "projeto":     str | None,
            "justificativa": str | None,
        }
    Chave do dict externo: "%d/%m/%y"
    """
    df = pd.read_excel(caminho, sheet_name=_SHEET_NAME, header=11, engine="xlrd")

    df = df[
        [
            "Data Inicial",
            "Hora Inicial",
            "Tarefa / Evento",
            "Ocorrência",
            "Título da Ocorrência",
            "Código do Projeto",
            "Projeto",
            "Justificativa",
        ]
    ].copy()
    df.columns = [
        "data",
        "hora",
        "acao",
        "ocorrencia",
        "titulo",
        "codigo",
        "projeto",
        "justificativa",
    ]
    df = df.dropna(subset=["data", "hora"])

    df["data_str"] = pd.to_datetime(df["data"], errors="coerce").dt.strftime("%d/%m/%y")
    df = df.dropna(subset=["data_str"])
    df["hora_str"] = df["hora"].astype(str).str.strip()

    # mais recente primeiro (igual ao original)
    df = df.iloc[::-1].reset_index(drop=True)

    apontamentos: dict[str, list[dict]] = {}
    eh_interrupcao = df.iloc[0]["acao"] == _INTERRUPCAO

    for _, row in df.iterrows():
        is_int = row["acao"] == _INTERRUPCAO
        if eh_interrupcao == is_int:
            apontamentos.setdefault(row["data_str"], []).append(
                {
                    "hora_str": row["hora_str"],
                    "interrupcao": is_int,
                    "ocorrencia": None
                    if pd.isna(row["ocorrencia"])
                    else str(int(row["ocorrencia"])),
                    "titulo": None if pd.isna(row["titulo"]) else str(row["titulo"]),
                    "tarefa": None if pd.isna(row["acao"]) else str(row["acao"]),
                    "codigo": None if pd.isna(row["codigo"]) else str(row["codigo"]),
                    "projeto": None if pd.isna(row["projeto"]) else str(row["projeto"]),
                    "justificativa": None
                    if pd.isna(row["justificativa"])
                    else str(row["justificativa"]),
                }
            )
            eh_interrupcao = not eh_interrupcao

    logger.info(f"📊 {len(apontamentos)} dia(s) parseados do XLS")
    return apontamentos


def baixar_apontamentos_mikael() -> dict[str, list[dict]]:
    """Faz login, baixa o XLS e retorna todos os apontamentos parseados."""
    destino = Path(config.MIKAEL_XLS_FILE)
    with sync_playwright() as p:
        browser, context, page = BrowserManager.criar_pagina(p)
        try:
            mikael = MikaelPage(page)
            mikael.fazer_login(config.SGIWEB_USER, config.SGIWEB_PASS)
            mikael.navegar_para_apontamentos()
            mikael.exportar_xls(destino)
        finally:
            context.close()
            browser.close()

    try:
        return parse_xls(destino)
    finally:
        if destino.exists():
            destino.unlink()
            logger.debug("🗑️ XLS temporário removido")


def obter_apontamentos_mikael(data_str: str) -> list[dict]:
    """Retorna lista de dicts do Mikael para `data_str` ("%d/%m/%Y")."""
    data_abreviada = datetime.strptime(data_str, "%d/%m/%Y").strftime("%d/%m/%y")
    todos = baixar_apontamentos_mikael()
    resultado = todos.get(data_abreviada, [])
    if not resultado:
        logger.warning(f"⚠️ Nenhum apontamento Mikael para {data_abreviada}")
    else:
        logger.info(f"⏰ {len(resultado)} entradas Mikael para {data_abreviada}")
    return resultado
