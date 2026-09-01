# -*- coding: utf-8 -*-
"""Automação SGIWeb - Playwright, desacoplada de UI"""
from datetime import datetime
from typing import Callable, List, Optional

from playwright.sync_api import sync_playwright

import config
from src.core.credentials_validator import CredentialsValidator
from src.utils.logger import get_logger
from .exceptions import AutomacaoError, CredenciaisInvalidasError, NenhumApontamentoError, SobrescritaCanceladaError
from .page_base import BrowserManager
from .sgiweb_pages import SGIWebLoginPage, SGIWebMarcacaoPage

logger = get_logger(__name__)


class AutomacaoSGIWeb:
    """Automação completa do SGIWeb (sem dependência de UI)"""

    def __init__(self, repo):
        self.repo = repo

    def obter_horarios_dia(self, data_str: str) -> List[str]:
        """
        Retorna horários (entrada/saída) do dia via SQLite.

        Raises:
            NenhumApontamentoError: se não houver apontamentos para a data.
        """
        data = datetime.strptime(data_str, "%d/%m/%Y").date()
        apts = self.repo.obter_por_dia(data)

        if not apts:
            raise NenhumApontamentoError(f"Nenhum apontamento encontrado para {data_str}.")

        horarios = [apts[0].inicio]

        for anterior, atual in zip(apts, apts[1:]):
            if anterior.fim and atual.inicio != anterior.fim:
                horarios.append(anterior.fim)
                horarios.append(atual.inicio)

        ultimo = apts[-1]
        if ultimo.fim:
            horarios.append(ultimo.fim)

        horarios_str = [h.strftime("%H:%M:%S") for h in horarios]
        logger.info(f"⏰ Horários extraídos: {horarios_str}")
        return horarios_str

    def enviar(
        self,
        horarios: List[str],
        data_str: str,
        confirmar_sobrescrita: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Executa a automação no SGIWeb (login, preenchimento, envio).

        Se a data já tiver horários preenchidos, chama `confirmar_sobrescrita()`
        (se fornecido) para decidir se continua. Sem callback, ou se ele
        retornar False, cancela sem sobrescrever.

        Raises:
            CredenciaisInvalidasError: credenciais não configuradas.
            SobrescritaCanceladaError: dados já existiam e não foi confirmado.
            AutomacaoError: data não encontrada ou falha no envio.
        """
        logger.info("=== AUTOMAÇÃO SGIWEB ===")
        logger.info(f"📅 Data: {data_str}")

        valido, erro = CredentialsValidator.validar_sgiweb()
        if not valido:
            raise CredenciaisInvalidasError(erro)

        with sync_playwright() as p:
            browser, context, page = BrowserManager.criar_pagina(p)
            try:
                login_page = SGIWebLoginPage(page)
                login_page.fazer_login(config.SGIWEB_USER, config.SGIWEB_PASS)

                marcacao_page = SGIWebMarcacaoPage(page)
                marcacao_page.ir_para_marcacao()

                if marcacao_page.verificar_data_preenchida(data_str):
                    if not confirmar_sobrescrita or not confirmar_sobrescrita():
                        raise SobrescritaCanceladaError(data_str)

                linha = marcacao_page.obter_linha_apontamento(data_str)
                if not linha:
                    raise AutomacaoError(f"Data {data_str} não encontrada no sistema.")

                marcacao_page.preencher_horarios(linha, horarios)

                if not marcacao_page.enviar_apontamentos():
                    raise AutomacaoError("Erro ao enviar. Verifique os dados.")

                logger.info("🎉 Automação concluída com sucesso")
            finally:
                context.close()
                browser.close()
                logger.info("🔒 Browser fechado")

        logger.info("🏁 Automação finalizada")