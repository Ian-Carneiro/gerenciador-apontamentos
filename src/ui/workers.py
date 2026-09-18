"""
workers.py — QThread workers da camada de UI.

Classes:
    AtualizarProjetosWorker  — baixa e processa projetos/tarefas do NetProject
                               em background, emitindo concluido ou erro.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal


class AtualizarProjetosWorker(QThread):
    """
    Executa `handler.atualizar_projetos_tarefas()` em background.

    Signals:
        concluido(list): emitido com os dados retornados pelo handler.
        erro(str):       emitido com a mensagem de exceção em caso de falha.

    Uso:
        worker = AtualizarProjetosWorker(handler, recurso, parent=self)
        worker.concluido.connect(on_concluido)
        worker.erro.connect(on_erro)
        worker.start()
    """

    concluido = Signal(list)
    erro = Signal(str)

    def __init__(self, handler, recurso: str, parent=None):
        """Guarda `handler` e `recurso` para usar em run()."""
        super().__init__(parent)
        self._handler = handler
        self._recurso = recurso

    def run(self):
        """Baixa e processa os projetos/tarefas do recurso; emite concluido(dados) ou erro(str)."""
        try:
            dados = self._handler.atualizar_projetos_tarefas(self._recurso, forcar_download=True)
            self.concluido.emit(dados)
        except Exception as e:
            self.erro.emit(str(e))


class ImportarFolhaPontoWorker(QThread):
    """Lê e parseia os PDFs do Espelho de Ponto em background."""

    concluido = Signal(dict)
    erro = Signal(str)

    def __init__(self, caminhos: list[str], parent=None):
        """Guarda a lista de caminhos de PDF para usar em run()."""
        super().__init__(parent)
        self._caminhos = caminhos

    def run(self):
        """Parseia cada PDF e mescla os dicts de resultado; emite concluido(dados) ou erro(str)."""
        from src.automacao.folha_ponto_import import parse_espelho_ponto

        try:
            dados = {}
            for caminho in self._caminhos:
                dados.update(parse_espelho_ponto(Path(caminho)))
            self.concluido.emit(dados)
        except Exception as e:
            self.erro.emit(str(e))
