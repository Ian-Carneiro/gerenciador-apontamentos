# -*- coding: utf-8 -*-
"""Automação NetProject - Playwright, desacoplada de UI"""
from datetime import datetime
from typing import Callable, Dict, List, Optional

from playwright.sync_api import sync_playwright

from src.core.credentials_validator import CredentialsValidator
from src.utils.logger import get_logger
from .exceptions import (
    AutomacaoError, CredenciaisInvalidasError, EnvioCanceladoError, NenhumApontamentoError,
)
from .netproject_pages import LoginPage, ApontamentoPage
from .page_base import BrowserManager

logger = get_logger(__name__)


class AutomacaoNetProject:
    """Automação completa do NetProject (sem dependência de UI)"""

    def __init__(self, repo):
        self.repo = repo

    def obter_apontamentos_dia(self, data_str: str) -> List[Dict]:
        """
        Retorna apontamentos do dia (via SQLite).

        Raises:
            NenhumApontamentoError: se não houver apontamentos para a data.
        """
        data = datetime.strptime(data_str, "%d/%m/%Y").date()

        apontamentos = []
        for apt in self.repo.obter_por_dia(data):
            apontamentos.append({
                "projeto": apt.projeto,
                "tarefa": apt.tarefa,
                "hora_inicio": apt.inicio.strftime("%H:%M:%S"),
                "hora_fim": apt.fim.strftime("%H:%M:%S") if apt.fim else None,
                "horas_trabalhadas": apt.horas if apt.fim else None,
            })

        if not apontamentos:
            raise NenhumApontamentoError(f"Nenhum apontamento encontrado para {data_str}.")

        return apontamentos

    def enviar(
            self,
            apontamentos: List[Dict],
            data_str: str,
            confirmar_envio: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Executa a automação no NetProject (login, preenchimento, envio).
        Não interage com o usuário — quem chama decide o que mostrar.

        Raises:
            CredenciaisInvalidasError: credenciais não configuradas.
            AutomacaoError: falha durante login, preenchimento ou envio.
            EnvioCanceladoError: se confirmar_envio() retornar False.
        """
        logger.info("=== AUTOMAÇÃO NETPROJECT ===")
        logger.info(f"📅 Data: {data_str}")

        valido, erro = CredentialsValidator.validar_netproject()
        if not valido:
            raise CredenciaisInvalidasError(erro)

        with sync_playwright() as p:
            browser, context, page = BrowserManager.criar_pagina(p)
            try:
                login_page = LoginPage(page)
                login_page.fazer_login()

                apt_page = ApontamentoPage(page)
                apt_page.abrir()
                apt_page.preencher_data(data_str)

                count = 0
                for apt in apontamentos:
                    if apt["projeto"] and apt["tarefa"] and apt["hora_fim"]:
                        apt_page.adicionar_linha()
                        apt_page.preencher_apontamento(count, apt)
                        count += 1
                        logger.info(f"✅ {count}/{len(apontamentos)}: {apt['projeto']} > {apt['tarefa']}")

                logger.info("📤 Enviando apontamentos...")
                if confirmar_envio and not confirmar_envio():
                    raise EnvioCanceladoError(data_str)

                if not apt_page.enviar():
                    raise AutomacaoError(
                        "Possível erro no envio. Verifique manualmente no NetProject."
                    )

                logger.info("🎉 Apontamentos enviados com sucesso")
            finally:
                context.close()
                browser.close()

        logger.info("🏁 Automação finalizada")