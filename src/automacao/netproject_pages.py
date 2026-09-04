"""Page Objects para NetProject - PLAYWRIGHT"""

from pathlib import Path
import re

import config
from src.utils.logger import get_logger

from .exceptions import CredenciaisInvalidasError
from .page_base import BasePage

logger = get_logger(__name__)


class LoginPage(BasePage):
    """Página de login do NetProject"""

    URL = "https://synchro.netproject.com.br/index.php"

    USERNAME_INPUT = "#username"
    PASSWORD_INPUT = "#password"
    SUBMIT_BTN = "input[type=submit][name=login]"
    LOGO = "#netproject_logo"

    def fazer_login(self) -> bool:
        self.page.goto(self.URL)

        # Cookies (se existirem) já foram injetados via storage_state no BrowserManager
        if self._logo_visivel(timeout=2000):
            logger.info("✅ Login com cookies")
            return True

        return self._login_credenciais()

    def _logo_visivel(self, timeout: float = 5000) -> bool:
        try:
            self.page.wait_for_selector(self.LOGO, timeout=timeout)
            return True
        except Exception:
            return False

    def _login_credenciais(self) -> bool:
        if not config.NETPROJECT_USER or not config.NETPROJECT_PASS:
            raise CredenciaisInvalidasError("❌ Credenciais NetProject não configuradas no .env")

        self.page.fill(self.USERNAME_INPUT, config.NETPROJECT_USER)
        self.page.fill(self.PASSWORD_INPUT, config.NETPROJECT_PASS)
        self.page.click(self.SUBMIT_BTN)

        self.page.wait_for_selector(self.LOGO)

        Path(config.STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        self.page.context.storage_state(path=str(config.STATE_FILE))

        logger.info("✅ Login com credenciais (cookies salvos)")
        return True


class ApontamentoPage(BasePage):
    """Página de apontamentos do NetProject"""

    URL = (
        "https://synchro.netproject.com.br/index.php?page=meta/view"
        "&id_view=usuario_recurso_cadastro&_menu_acessado=444"
    )

    DATA_INPUT = "[id='dth_ponto_eletronico**93,0;180___dat//0/0']"
    BTN_ADICIONAR = "[id='btn_cadastro_detalhe_1_n_+']"
    TBODY_LINHAS = "#body_mestre_detalhe_tabela_214_122_0"
    BTN_SUBMIT = "button#btn_cadastro_submit"
    SELECT2_INPUT = (
        "#body_main > span > span > span.select2-search.select2-search--dropdown > input"
    )
    SELECT2_RESULTS = "#body_main > span > span > span.select2-results"
    OBSERVACAO_TEXTAREA = "textarea[name^='dsc_manual']"

    def abrir(self):
        self.page.goto(self.URL)
        self.sleep(config.TIMEOUT_MEDIO)

    def preencher_data(self, data_str: str):
        self.page.fill(self.DATA_INPUT, data_str)
        self.sleep(1)

    def adicionar_linha(self):
        self.page.click(self.BTN_ADICIONAR)
        self.sleep(0.1)

    def preencher_apontamento(self, numero: int, apontamento: dict):
        linha_atual = self.page.locator(f"{self.TBODY_LINHAS} > tr").nth(numero)
        linha_atual.scroll_into_view_if_needed()

        linhas_internas = linha_atual.locator("tbody tr")

        # Projeto e tarefa
        selects_row = linhas_internas.nth(0)
        tds = selects_row.locator("td")

        self._selecionar_select2(tds.nth(1).locator("span.selection"), apontamento["projeto"])

        self.sleep(0.5)

        self._selecionar_select2(tds.nth(3).locator("span.selection"), apontamento["tarefa"])

        # Horas
        horas_row = linhas_internas.nth(2)
        tds_horas = horas_row.locator("td")

        self._preencher_hora(tds_horas.nth(1), apontamento["hora_inicio"])

        if apontamento.get("hora_fim"):
            self._preencher_hora(tds_horas.nth(3), apontamento["hora_fim"])

        if apontamento.get("observacao"):
            self._preencher_observacao(linha_atual, apontamento["observacao"])

    def _buscar_opcao(self, campo, resultados, valor: str):
        """
        Digita `valor` incrementalmente (palavra por palavra) até o filtro
        retornar 3 opções ou menos, e retorna a que bate com o valor exato.
        """
        palavras = valor.split()
        busca = ""

        for palavra in palavras:
            candidato = f"{busca} {palavra}".strip()

            campo.press("Control+A")
            campo.press("Delete")
            campo.press_sequentially(candidato, delay=6)
            self.sleep(0.5)

            opcoes = resultados.locator("li.select2-results__option").filter(
                has_not_text="carregando"
            )
            count = opcoes.count()

            if count == 0:
                continue  # palavra quebrou a busca, ignora e segue com a próxima

            busca = candidato

            if count <= 3:
                valor_norm = self._normalizar_espacos(valor).lower()
                for i in range(count):
                    opcao = opcoes.nth(i)
                    texto_norm = self._normalizar_espacos(opcao.text_content()).lower()
                    if valor_norm in texto_norm:
                        return opcao
                return None

        return None

    @staticmethod
    def _normalizar_espacos(texto: str) -> str:
        return re.sub(r"\s+", " ", texto).strip()

    def _selecionar_select2(self, elemento_trigger, valor: str, tentativas: int = 3) -> None:
        """
        Abre o select2 pelo `elemento_trigger`, digita `valor`, clica na
        primeira opção e CONFIRMA lendo o texto que ficou selecionado.
        Se não confirmar, fecha o dropdown e reabre do zero.
        """
        for tentativa in range(1, tentativas + 1):
            self.page.keyboard.press(
                "Escape"
            )  # garante que nada ficou aberto de tentativa anterior
            self.sleep(0.2)

            elemento_trigger.click()
            self.sleep(0.3)

            campo = self.page.locator(self.SELECT2_INPUT).last
            resultados = self.page.locator(self.SELECT2_RESULTS).last

            campo.click()

            opcao = self._buscar_opcao(campo, resultados, valor)

            if opcao is not None:
                opcao.click()
                self.sleep(0.3)

                texto_selecionado = self._normalizar_espacos(elemento_trigger.text_content())
                if self._normalizar_espacos(valor).lower() in texto_selecionado.lower():
                    return  # confirmado ✅

                logger.warning(
                    f"⚠️ Clicou mas não confirmou '{valor}' (mostrou '{texto_selecionado}') "
                    f"— tentativa {tentativa}/{tentativas}"
                )
            else:
                logger.warning(
                    f"⚠️ Select2 sem resultados para '{valor}' (tentativa {tentativa}/{tentativas})"
                )

            self.sleep(0.5)

    def _preencher_hora(self, td_locator, hora: str):
        """Preenche campo de hora (HH:MM)"""
        h, m = hora.split(":")[:2]
        inputs = td_locator.locator("input")

        self.sleep(0.5)
        inputs.nth(0).click()
        inputs.nth(0).press("Control+A")
        inputs.nth(0).press("Delete")
        inputs.nth(0).press_sequentially(h)  # use .type(h) se sua versão do Playwright for antiga

        self.sleep(0.5)
        inputs.nth(1).click()
        inputs.nth(1).press("Control+A")
        inputs.nth(1).press("Delete")
        inputs.nth(1).press_sequentially(m)

    def _preencher_observacao(self, linha_atual, texto: str):
        """Preenche o campo de Observações da linha, se houver texto."""
        textarea = linha_atual.locator(self.OBSERVACAO_TEXTAREA)
        if textarea.count() == 0:
            return
        textarea.first.click()
        textarea.first.fill(texto.strip())

    def enviar(self) -> bool:
        try:
            with self.page.expect_navigation():
                self.page.click(self.BTN_SUBMIT, no_wait_after=True)

            modal = self.page.locator("#info-msg-modal")

            if modal.is_visible():
                modal.locator("xpath=..").locator(".ui-dialog-titlebar-close").click()
                logger.info("ℹ️ Modal de informação fechada")

            self.sleep(1)

            logger.info("✅ Apontamentos enviados e confirmados")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao enviar/confirmar: {e}")
            return False
