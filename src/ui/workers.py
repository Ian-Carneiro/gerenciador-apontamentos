# -*- coding: utf-8 -*-
"""
workers.py — QThread workers da camada de UI.

Classes:
    AtualizarProjetosWorker  — baixa e processa projetos/tarefas do NetProject
                               em background, emitindo concluido ou erro.
"""
from __future__ import annotations

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
    erro      = Signal(str)

    def __init__(self, handler, recurso: str, parent=None):
        super().__init__(parent)
        self._handler = handler
        self._recurso = recurso

    def run(self):
        try:
            dados = self._handler.atualizar_projetos_tarefas(
                self._recurso, forcar_download=True
            )
            self.concluido.emit(dados)
        except Exception as e:
            self.erro.emit(str(e))