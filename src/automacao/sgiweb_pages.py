# -*- coding: utf-8 -*-
"""Page Objects para SGIWeb - PLAYWRIGHT"""
from datetime import datetime
import re

import config
from src.utils.logger import get_logger
from .page_base import BasePage

logger = get_logger(__name__)


class SGIWebLoginPage(BasePage):
    """Página de login do SGIWeb"""

    URL = "https://sgiweb.synchro.com.br/login.html"

    USERNAME_INPUT = "input[name='prfNome']"
    PASSWORD_INPUT = "input[name='prfSenha']"
    SUBMIT_BTN = "input[name='submit1']"

    def fazer_login(self, usuario: str, senha: str):
        logger.info("🔐 Fazendo login no SGIWeb...")
        self.page.goto(self.URL)
        self.page.fill(self.USERNAME_INPUT, usuario)
        self.page.fill(self.PASSWORD_INPUT, senha)
        self.page.click(self.SUBMIT_BTN)
        logger.info("✅ Login realizado")


class SGIWebMarcacaoPage(BasePage):
    """Página de marcação de jornada"""

    RADIO_HORA_ENTRADA = "input[value='HoraEntrada']"
    BTN_GO = "[name='go']"
    TABLE_MARCACOES = "table"
    BTN_SUBMIT = "[name='submit1']"
    TITULO_VALIDACAO = "h3"
    INPUT_HORA = "input[name='hora']"

    def ir_para_marcacao(self):
        logger.info("📋 Navegando para marcação de jornada...")
        self.page.click(self.RADIO_HORA_ENTRADA)
        self.page.click(self.BTN_GO)
        self.sleep(config.TIMEOUT_MEDIO)
        logger.info("✅ Página de marcação carregada")

    def obter_linha_apontamento(self, data_str: str):
        data_abreviada = datetime.strptime(data_str, "%d/%m/%Y").strftime("%d/%m/%y")
        logger.debug(f"🔍 Buscando linha para data: {data_abreviada}")
        self.sleep(config.TIMEOUT_MEDIO)

        tabelas = self.page.locator(self.TABLE_MARCACOES)
        if tabelas.count() < 2:
            logger.error("❌ Tabela de marcações não encontrada")
            return None

        xpath = f".//tr[td[1][starts-with(normalize-space(), '{data_abreviada}')]]"
        linha = tabelas.nth(1).locator(f"xpath={xpath}")

        if linha.count() == 0:
            logger.warning(f"⚠️ Linha não encontrada para {data_abreviada}")
            return None

        logger.info(f"✅ Linha encontrada para {data_abreviada}")
        return linha.first

    def preencher_horarios(self, linha_apontamento, horarios: list):
        logger.info(f"⏰ Preenchendo {len(horarios)} horários...")

        linha_apontamento.locator("xpath=.//td[a]/a").click()
        self.sleep(config.TIMEOUT_MEDIO)

        inputs_hora = self.page.locator(self.INPUT_HORA)
        total = inputs_hora.count()

        for i, horario in enumerate(horarios):
            if i < total:
                inputs_hora.nth(i).fill(horario)
                logger.debug(f"  ✓ Horário {i + 1}: {horario}")

        logger.info("✅ Horários preenchidos")

    def enviar_apontamentos(self):
        logger.info("📤 Enviando apontamentos...")
        self.page.click(self.BTN_SUBMIT)
        self.sleep(config.TIMEOUT_MEDIO)

        try:
            titulo = self.page.locator(self.TITULO_VALIDACAO).first
            if titulo.text_content().strip() == "Validando os dados":
                self.page.go_back()
                self.page.go_back()
        except Exception:
            return False

        self.page.reload()
        logger.info("✅ Apontamentos enviados com sucesso")
        return True

    def verificar_data_preenchida(self, data_str: str) -> bool:
        linha = self.obter_linha_apontamento(data_str)
        if not linha:
            return False

        texto = linha.text_content().strip()
        padrao_vazio = r"\d{2}/\d{2}/\d{2} \w{3}$"
        esta_vazio = bool(re.match(padrao_vazio, texto))

        if not esta_vazio:
            logger.info(f"ℹ️ Data {data_str} já possui apontamentos")

        return not esta_vazio