"""
MainWindow — Janela principal do Apontador de Horas v5.

Layout:
  ┌--------------------------------------------─┐
  │  MenuBar (... Configurar ★ Favoritos Ajuda) │
  ├--------------------------------------------─┤
  │  ⏱  Apontador de Horas          v5.0  [≡]  │
  ├--------------------------------------------─┤
  │  PROJETO   [▼ FilterableComboBox       ]    │
  │  TAREFA    [▼ FilterableComboBox       ]    │
  │  NOTA      [TextEdit expansível        ]    │
  │                                             │
  │  INÍCIO  [HH:MM:SS]   FIM  [HH:MM:SS]       │
  │                                             │
  │  [  ▶ Iniciar / Registrar  ] [  ■ Parar  ] │
  ├--------------------------------------------─┤
  │  ● Em execução . Projeto > Tarefa . 12:34  │
  └--------------------------------------------─┘
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.apontamento_service import ApontamentoService, EstadoApp
from src.db.models import Apontamento
from src.db.repository import ApontamentoAtivoError, HorarioInvalidoError, SobreposicaoError
from src.ui import messagebox_utils as mbox
from src.ui.widgets.favoritos_popup import FavoritosPopup
from src.ui.widgets.filterable_combo import FilterableComboBox
from src.ui.widgets.hora_field import HoraField
from src.ui.widgets.status_bar import StatusBar
from src.ui.workers import AtualizarProjetosWorker
from src.utils.logger import get_logger

logger = get_logger(__name__)

_QSS_PATH = Path(__file__).parent / "style" / "theme.qss"


def _carregar_qss() -> str:
    if _QSS_PATH.exists():
        return _QSS_PATH.read_text(encoding="utf-8")
    logger.warning(f"QSS nao encontrado: {_QSS_PATH}")
    return ""


# -- MainWindow ----------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self, service: ApontamentoService):
        super().__init__()
        self._svc = service
        self._dados_pt: list[dict] = []  # cache [{projeto, tarefa}]

        self.setWindowTitle("Apontador de Horas")
        self.setMinimumSize(520, 520)
        self.resize(560, 580)

        # Aplica QSS global
        QApplication.instance().setStyleSheet(_carregar_qss())

        self._build_ui()
        self._build_menu()
        self._restaurar_estado()

    # -- Construção da UI ------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Cabeçalho
        root.addWidget(self._build_header())

        # Painel principal
        root.addWidget(self._build_main_panel(), stretch=1)

        # Status bar
        self._status_bar = StatusBar(self)
        root.addWidget(self._status_bar)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("appHeader")
        frame.setFixedHeight(52)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 0, 12, 0)

        lbl_icon = QLabel("[H]")
        lbl_icon.setObjectName("appHeaderIcon")
        layout.addWidget(lbl_icon)

        lbl_title = QLabel("Apontador de Horas")
        lbl_title.setObjectName("labelAppTitle")
        layout.addWidget(lbl_title)

        layout.addStretch()

        lbl_ver = QLabel("v5.0")
        lbl_ver.setObjectName("labelVersion")
        layout.addWidget(lbl_ver)

        return frame

    def _build_main_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panelMain")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # -- Projeto ----------------------------------------------------------
        layout.addWidget(self._field_label("PROJETO"))
        self._combo_projeto = FilterableComboBox(placeholder="Selecionar projeto...")
        layout.addWidget(self._combo_projeto)

        # -- Tarefa ----------------------------------------------------------─
        layout.addWidget(self._field_label("TAREFA"))
        self._combo_tarefa = FilterableComboBox(placeholder="Selecionar tarefa...")
        layout.addWidget(self._combo_tarefa)

        # -- Nota ------------------------------------------------------------─
        layout.addWidget(self._field_label("NOTA  (opcional)"))
        self._nota = QTextEdit()
        self._nota.setObjectName("textEditNota")
        self._nota.setPlaceholderText("Observacoes sobre este apontamento...")
        self._nota.setFixedHeight(52)  # ~2 linhas
        self._nota.textChanged.connect(self._ajustar_nota)
        layout.addWidget(self._nota)

        # -- Horários --------------------------------------------------------─
        linha_horas = QHBoxLayout()
        linha_horas.setSpacing(20)
        self._hora_inicio = HoraField("INÍCIO")
        self._hora_fim = HoraField("FIM")
        linha_horas.addWidget(self._hora_inicio)
        linha_horas.addWidget(self._hora_fim)
        linha_horas.addStretch()
        layout.addLayout(linha_horas)

        # -- Botões ------------------------------------------------------------
        layout.addSpacing(4)
        linha_btns = QHBoxLayout()
        linha_btns.setSpacing(10)

        self._btn_iniciar = QPushButton("Iniciar / Registrar")
        self._btn_iniciar.setObjectName("btnIniciar")
        self._btn_iniciar.setMinimumHeight(40)
        self._btn_iniciar.clicked.connect(self._on_iniciar)
        linha_btns.addWidget(self._btn_iniciar, stretch=2)

        self._btn_parar = QPushButton("Parar Apontamento")
        self._btn_parar.setObjectName("btnParar")
        self._btn_parar.setMinimumHeight(40)
        self._btn_parar.setEnabled(False)
        self._btn_parar.clicked.connect(self._on_parar)
        linha_btns.addWidget(self._btn_parar, stretch=1)

        layout.addLayout(linha_btns)
        return frame

    @staticmethod
    def _field_label(texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setObjectName("labelFieldCaption")
        return lbl

    # -- Menu ------------------------------------------------------------------

    def _build_menu(self):
        bar = self.menuBar()

        # Visualizar
        menu_ver = bar.addMenu("Visualizar")
        act_hist = QAction("📋  Historico de Apontamentos", self)
        act_hist.setShortcut("Ctrl+H")
        act_hist.triggered.connect(self._abrir_historico)
        menu_ver.addAction(act_hist)

        act_intervalos = QAction("🕳  Intervalos Livres Hoje", self)
        act_intervalos.triggered.connect(self._mostrar_intervalos_livres)
        menu_ver.addAction(act_intervalos)

        # Automação
        menu_auto = bar.addMenu("Automacao")
        act_np = QAction("🤖  Apontar no NetProject", self)
        act_np.setShortcut("Ctrl+N")
        act_np.triggered.connect(self._on_automacao_netproject)
        menu_auto.addAction(act_np)

        act_sgi = QAction("🤖  Apontar no SGIWeb", self)
        act_sgi.setShortcut("Ctrl+G")
        act_sgi.triggered.connect(self._on_automacao_sgiweb)
        menu_auto.addAction(act_sgi)

        # Configurar
        menu_conf = bar.addMenu("Configurar")
        act_proj = QAction("🔄  Atualizar Projetos / Tarefas", self)
        act_proj.setShortcut("Ctrl+R")
        act_proj.triggered.connect(self._on_atualizar_projetos)
        menu_conf.addAction(act_proj)

        menu_conf.addSeparator()

        act_np_cfg = QAction("✏️  Editar Projetos / Tarefas", self)
        act_np_cfg.triggered.connect(self._on_configuracoes_netproject)
        menu_conf.addAction(act_np_cfg)

        # Favoritos (ação direta na barra, sem submenu — abre o popup de favoritos)
        self._act_favoritos = QAction("★ Favoritos", self)
        self._act_favoritos.triggered.connect(self._abrir_favoritos)
        bar.addAction(self._act_favoritos)

        # Ajuda
        menu_ajuda = bar.addMenu("Ajuda")
        act_sobre = QAction("ℹ️  Sobre", self)
        act_sobre.triggered.connect(self._on_sobre)
        menu_ajuda.addAction(act_sobre)

    # -- Restauração de estado ------------------------------------------------─

    def _restaurar_estado(self):
        """Carrega o estado do banco e popula a UI."""
        estado: EstadoApp = self._svc.recuperar_estado()

        # Projetos/tarefas
        self._dados_pt = estado.projetos_tarefas
        self._popular_combos()

        # Favoritos
        self._popular_favoritos()

        # Status bar — total de hoje
        self._status_bar.set_total_hoje(estado.total_horas_hoje)

        # Apontamento ativo?
        if estado.ativo:
            self._aplicar_estado_ativo(estado.ativo)
            logger.info(f"Apontamento ativo recuperado: {estado.ativo}")
        else:
            self._aplicar_estado_inativo()

    def _popular_combos(self):
        projetos = sorted({d["projeto"] for d in self._dados_pt})
        self._combo_projeto.set_dados(projetos)
        self._combo_tarefa.set_dados_por_pai(
            dados=self._dados_pt,
            campo_proprio="tarefa",
            campo_pai="projeto",
            combo_pai=self._combo_projeto,
        )

    def _popular_favoritos(self):
        self._favoritos_cache = self._svc.calcular_favoritos(max_itens=8)

    # -- Handlers de botão ----------------------------------------------------─

    def _on_iniciar(self):
        projeto = self._combo_projeto.valor_atual()
        tarefa = self._combo_tarefa.valor_atual()

        if not projeto:
            self._mostrar_erro("Selecione um projeto antes de iniciar.")
            self._combo_projeto.setFocus()
            return
        if not tarefa:
            self._mostrar_erro("Selecione uma tarefa antes de iniciar.")
            self._combo_tarefa.setFocus()
            return

        inicio = self._hora_inicio.valor()
        fim = self._hora_fim.valor()
        nota = self._nota.toPlainText().strip()

        # Valida: se fim preenchido, inicio obrigatório
        if fim is not None and inicio is None:
            self._mostrar_erro("Preencha também o Início quando informar o Fim.")
            return

        try:
            resultado = self._svc.iniciar_ou_registrar(
                projeto=projeto,
                tarefa=tarefa,
                inicio=inicio,
                fim=fim,
                nota=nota,
            )
        except SobreposicaoError as e:
            conflito = e.conflito
            self._mostrar_erro(
                f"Intervalo conflita com apontamento existente:\n\n"
                f"  {conflito.projeto} > {conflito.tarefa}\n"
                f"  {conflito.inicio.strftime('%H:%M')} - "
                f"{conflito.fim.strftime('%H:%M') if conflito.fim else '...'}\n\n"
                f"Ajuste os horários ou use 'Intervalos Livres Hoje' para ver "
                f"os buracos disponíveis."
            )
            return
        except (HorarioInvalidoError, ApontamentoAtivoError, ValueError) as e:
            self._mostrar_erro(str(e))
            return

        # Sucesso
        self._hora_inicio.limpar()
        self._hora_fim.limpar()
        self._nota.clear()

        if resultado.modo == "retroativo":
            self._aplicar_estado_inativo()
            self._mostrar_toast(resultado.mensagem)
        else:
            self._aplicar_estado_ativo(resultado.apontamento)
            self._mostrar_toast(resultado.mensagem)

        self._combo_projeto.adicionar_valor(projeto)
        self._combo_tarefa.adicionar_par(projeto, tarefa)

        self._atualizar_total_hoje()
        self._popular_favoritos()

    def _on_parar(self):
        fim = self._hora_fim.valor()
        nota = self._nota.toPlainText().strip()

        try:
            parado = self._svc.parar_ativo(fim=fim, nota=nota or None)
        except (HorarioInvalidoError, Exception) as e:
            self._mostrar_erro(str(e))
            return

        self._hora_inicio.limpar()
        self._hora_fim.limpar()
        self._nota.clear()

        self._aplicar_estado_inativo()
        self._mostrar_toast(f"Parado: {parado.projeto} > {parado.tarefa} ({parado.duracao_str})")
        self._atualizar_total_hoje()
        self._popular_favoritos()

    def _abrir_favoritos(self):
        popup = FavoritosPopup(self, self._favoritos_cache)
        popup.favorito_escolhido.connect(self._aplicar_favorito)
        bar = self.menuBar()
        rect = bar.actionGeometry(self._act_favoritos)
        popup.abrir_em(bar.mapToGlobal(rect.bottomLeft()), rect.width())

    # -- Estado visual --------------------------------------------------------─

    def _aplicar_estado_ativo(self, apontamento: Apontamento):
        self._status_bar.set_ativo(apontamento)
        self._btn_parar.setEnabled(True)
        self._btn_iniciar.setText("Trocar Tarefa")

    def _aplicar_estado_inativo(self):
        self._status_bar.set_inativo()
        self._btn_parar.setEnabled(False)
        self._btn_iniciar.setText("Iniciar / Registrar")

    def _aplicar_favorito(self, projeto: str, tarefa: str):
        self._combo_projeto.set_valor(projeto)
        # Dispara o sinal para o combo de tarefa filtrar
        self._combo_projeto.valor_selecionado.emit(projeto)
        self._combo_tarefa.set_valor(tarefa)

    def _ajustar_nota(self):
        """Expande o TextEdit de nota até 4 linhas conforme o conteúdo."""
        linhas = self._nota.document().blockCount()
        nova_h = max(52, min(linhas * 22 + 10, 98))
        self._nota.setFixedHeight(nova_h)

    def _atualizar_total_hoje(self):
        from datetime import date

        total = self._svc._repo.total_horas_dia(date.today())
        self._status_bar.set_total_hoje(total)

    # -- Menus: ações --------------------------------------------------------─

    def _abrir_historico(self):
        """Abre o diálogo de histórico (implementado na Fase 4)."""
        from src.ui.dialogs.historico_dialog import HistoricoDialog

        dlg = HistoricoDialog(self._svc, parent=self)
        dlg.exec()
        # Recarrega estado após fechar (pode ter editado algo)
        self._restaurar_estado()

    def _mostrar_intervalos_livres(self):
        from datetime import date

        intervalos = self._svc.obter_intervalos_livres(date.today())

        if not intervalos:
            self._mostrar_info("Nenhum intervalo livre hoje.")
            return

        linhas = []
        for ini, fim in intervalos:
            duracao_s = int((fim - ini).total_seconds())
            h = duracao_s // 3600
            m = (duracao_s % 3600) // 60
            if h > 0:
                dur = f"{h}h {m:02d}min"
            elif m > 0:
                dur = f"{m}min"
            else:
                continue  # ignora buracos < 1min
            linhas.append(f"  {ini.strftime('%H:%M')} - {fim.strftime('%H:%M')}  ({dur})")

        if not linhas:
            self._mostrar_info("Nenhum intervalo livre significativo hoje.")
            return

        self._mostrar_info("Intervalos sem apontamento hoje:\n\n" + "\n".join(linhas))

    def _on_automacao_netproject(self):
        from src.automacao.exceptions import (
            AutomacaoError,
            CredenciaisInvalidasError,
            EnvioCanceladoError,
            NenhumApontamentoError,
        )
        from src.automacao.netproject_automacao import AutomacaoNetProject
        from src.ui.dialogs.confirmacao_dialogs import confirmar_apontamentos_netproject
        from src.ui.dialogs.utils_dialogs import pedir_data

        data_str = pedir_data("Automação NetProject", parent=self)
        if not data_str:
            return

        automacao = AutomacaoNetProject(self._svc._repo)

        try:
            apontamentos = automacao.obter_apontamentos_dia(data_str)
        except NenhumApontamentoError as e:
            self._mostrar_info(str(e))
            return

        if not confirmar_apontamentos_netproject(apontamentos, data_str, parent=self):
            self._mostrar_toast("Envio cancelado")
            return

        def confirmar_envio():
            return confirmar_apontamentos_netproject(apontamentos, data_str, parent=self)

        try:
            automacao.enviar(apontamentos, data_str, confirmar_envio=confirmar_envio)
        except EnvioCanceladoError:
            self._mostrar_toast("Envio cancelado")
            return
        except CredenciaisInvalidasError as e:
            self._mostrar_erro(f"{e}\n\nConfigure as credenciais no arquivo .env")
            return
        except AutomacaoError as e:
            self._mostrar_aviso(str(e))
            return
        except Exception as e:
            self._mostrar_erro(f"Erro na automação:\n{e}")
            return

        self._mostrar_info("✅ Apontamentos enviados com sucesso!")

    def _on_automacao_sgiweb(self):
        from src.automacao.exceptions import (
            AutomacaoError,
            CredenciaisInvalidasError,
            NenhumApontamentoError,
            SobrescritaCanceladaError,
        )
        from src.automacao.sgiweb_automacao import AutomacaoSGIWeb
        from src.ui.dialogs.confirmacao_dialogs import confirmar_horarios_sgiweb
        from src.ui.dialogs.utils_dialogs import pedir_data

        data_str = pedir_data("Automação SGIWeb", parent=self)
        if not data_str:
            return

        automacao = AutomacaoSGIWeb(self._svc._repo)

        try:
            horarios = automacao.obter_horarios_dia(data_str)
        except NenhumApontamentoError as e:
            self._mostrar_info(str(e))
            return

        if not confirmar_horarios_sgiweb(horarios, data_str, parent=self):
            self._mostrar_toast("Envio cancelado")
            return

        def confirmar_sobrescrita():
            return mbox.askyesno(
                "Aviso", "Esta data já possui apontamentos.\nDeseja sobrescrever?", parent=self
            )

        try:
            automacao.enviar(horarios, data_str, confirmar_sobrescrita=confirmar_sobrescrita)
        except SobrescritaCanceladaError:
            self._mostrar_toast("Sobrescrita cancelada")
            return
        except CredenciaisInvalidasError as e:
            self._mostrar_erro(f"{e}\n\nConfigure as credenciais no arquivo .env")
            return
        except AutomacaoError as e:
            self._mostrar_aviso(str(e))
            return
        except Exception as e:
            self._mostrar_erro(f"Erro na automação:\n{e}")
            return

        self._mostrar_info("✅ Apontamentos enviados com sucesso!")

    def _on_atualizar_projetos(self):
        from src.core.projetos_tarefas import ProjetosTarefasHandler
        from src.ui.dialogs.utils_dialogs import selecionar_recurso_netproject

        handler = ProjetosTarefasHandler()

        recursos = handler.obter_recursos_disponiveis()
        if not recursos:
            self._mostrar_erro("Não foi possível carregar a lista de recursos do NetProject.")
            return

        recurso = selecionar_recurso_netproject(recursos, parent=self)
        if not recurso:
            return

        progresso = QProgressDialog(
            "Baixando e processando projetos/tarefas do NetProject...", None, 0, 0, self
        )
        progresso.setWindowTitle("Atualizando Projetos/Tarefas")
        progresso.setWindowModality(Qt.WindowModality.WindowModal)
        progresso.setCancelButton(None)
        progresso.setMinimumDuration(0)
        progresso.show()

        self._worker_projetos = AtualizarProjetosWorker(handler, recurso, parent=self)

        def on_concluido(dados):
            progresso.close()
            if not dados:
                self._mostrar_info("Nenhum projeto/tarefa encontrado para o recurso configurado.")
                return
            count = self._svc._repo.sincronizar_projetos_tarefas(dados)
            self._restaurar_estado()
            self._mostrar_toast(f"🔄 {count} projetos/tarefas atualizados")

        def on_erro(msg):
            progresso.close()
            self._mostrar_erro(f"Erro ao atualizar projetos/tarefas:\n{msg}")

        self._worker_projetos.concluido.connect(on_concluido)
        self._worker_projetos.erro.connect(on_erro)
        self._worker_projetos.start()

    def _on_configuracoes_netproject(self):
        from src.ui.dialogs.projetos_tarefas_dialog import ProjetosTarefasDialog

        dlg = ProjetosTarefasDialog(self._svc._repo, parent=self)
        dlg.exec()
        self._restaurar_estado()

    def _on_sobre(self):
        QMessageBox.about(
            self,
            "Sobre",
            "<b>Apontador de Horas v5.0</b><br><br>"
            "Stack: PySide6 . SQLite/SQLAlchemy . Playwright<br>"
            "Migrado de Tkinter + Selenium + CSV",
        )

    # -- Utilitários de diálogo ------------------------------------------------

    def _mostrar_erro(self, msg: str):
        mbox.showerror("Erro", msg, parent=self)

    def _mostrar_info(self, msg: str):
        mbox.showinfo("Info", msg, parent=self)

    def _mostrar_aviso(self, msg: str):
        mbox.showwarning("Aviso", msg, parent=self)

    def _mostrar_toast(self, msg: str):
        """Exibe mensagem temporária na status bar do Qt (2 segundos)."""
        self.statusBar().showMessage(msg, 2000)
        logger.info(f"Toast: {msg}")
