"""Exceções de domínio da automação"""


class AutomacaoError(Exception):
    """Erro genérico durante a execução da automação"""


class CredenciaisInvalidasError(AutomacaoError):
    """Credenciais não configuradas ou inválidas"""


class NenhumApontamentoError(AutomacaoError):
    """Não há apontamentos/horários para o dia solicitado"""


class SobrescritaCanceladaError(AutomacaoError):
    """Usuário optou por não sobrescrever dados já existentes"""

    def __init__(self, data_str: str):
        self.data_str = data_str
        super().__init__(f"Sobrescrita cancelada para {data_str}")


class EnvioCanceladoError(AutomacaoError):
    """Usuário cancelou a confirmação final antes do envio"""

    def __init__(self, data_str: str):
        self.data_str = data_str
        super().__init__(f"Envio cancelado pelo usuário para {data_str}")
