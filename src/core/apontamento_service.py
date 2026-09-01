# -*- coding: utf-8 -*-
"""
ApontamentoService — Regras de negócio de alto nível.

Orquestra o Repository para implementar os fluxos compostos
que a UI dispara. A UI só chama o Service, nunca o Repository diretamente.

Responsabilidades:
  - Lógica de "Iniciar/Registrar" (3 cenários do guia original)
  - Troca de tarefa automática (para a atual, inicia nova)
  - Recuperação de apontamento ativo ao abrir o app
  - Score de favoritos / mais usados
  - Formatação de dados para a UI (nada de widgets aqui)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional

from src.db.models import Apontamento, ProjetoTarefa
from src.db.repository import (
    ApontamentoRepository,
    ApontamentoAtivoError,
    ApontamentoError,
    BlocoHistorico,
    HorarioInvalidoError,
    SobreposicaoError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ── DTOs de resultado ─────────────────────────────────────────────────────────

@dataclass
class ResultadoIniciar:
    """Retorno de iniciar_ou_registrar() com contexto para a UI."""
    apontamento: Apontamento
    anterior_parado: Optional[Apontamento] = None   # se houve troca de tarefa
    modo: str = "iniciado"                          # "iniciado" | "retroativo" | "troca"

    @property
    def mensagem(self) -> str:
        if self.modo == "troca":
            dur = self.anterior_parado.duracao_str if self.anterior_parado else "?"
            return (
                f"⏹  {self.anterior_parado.tarefa} parado ({dur})\n"
                f"▶️  {self.apontamento.tarefa} iniciado"
            )
        if self.modo == "retroativo":
            return f"📝 Registrado: {self.apontamento.duracao_str}"
        return f"▶️  Iniciado às {self.apontamento.inicio.strftime('%H:%M:%S')}"


@dataclass
class ItemFavorito:
    """Projeto/tarefa com score de relevância para exibição no menu de favoritos."""
    projeto: str
    tarefa:  str
    score:   float
    contagem:    int   = 0
    total_horas: float = 0.0
    ultima_vez:  Optional[datetime] = None

    @property
    def label(self) -> str:
        return f"{self.projeto}  ›  {self.tarefa}"

    @property
    def horas_str(self) -> str:
        h = int(self.total_horas)
        m = int((self.total_horas - h) * 60)
        return f"{h}h {m:02d}min"


@dataclass
class EstadoApp:
    """Snapshot do estado atual para a UI reconstruir a tela."""
    ativo: Optional[Apontamento]
    blocos_hoje: list[Apontamento]
    total_horas_hoje: float
    projetos_tarefas: list[dict]   # [{"projeto": ..., "tarefa": ...}]

    @property
    def em_execucao(self) -> bool:
        return self.ativo is not None

    @property
    def total_hoje_str(self) -> str:
        h = int(self.total_horas_hoje)
        m = int((self.total_horas_hoje - h) * 60)
        return f"{h}h {m:02d}min"


# ── Service ───────────────────────────────────────────────────────────────────

class ApontamentoService:
    """
    Ponto de entrada único para toda lógica de negócio.
    Instancie uma vez na aplicação e injete onde necessário.
    """

    def __init__(self, repo: Optional[ApontamentoRepository] = None):
        self._repo = repo or ApontamentoRepository()

    # ── Fluxo principal: Iniciar / Registrar ──────────────────────────────────

    def iniciar_ou_registrar(
        self,
        projeto: str,
        tarefa:  str,
        inicio:  Optional[datetime] = None,
        fim:     Optional[datetime] = None,
        nota:    str = "",
        agora:   Optional[datetime] = None,
    ) -> ResultadoIniciar:
        """
        Implementa os cenários de início e registro:

        Cenário 1 — Iniciar agora:
            inicio=None, fim=None, sem tarefa ativa
            → inicia a tarefa com o horário atual.

        Cenário 2 — Iniciar em horário específico:
            inicio=X, fim=None, sem tarefa ativa
            → inicia a tarefa em X.

        Cenário 3 — Retroativo completo:
            inicio=X, fim=Y, sem tarefa ativa
            → registra a tarefa no intervalo X–Y.

        Cenário 4 — Retroativo com tarefa ativa:
            inicio=X, fim=Y, com tarefa ativa
            → para a tarefa atual em X,
              registra a nova tarefa no intervalo X–Y,
              retoma a tarefa anterior em Y.

        Cenário 5 — Troca de tarefa:
            inicio=None, fim=None, com tarefa ativa
            → para a tarefa atual com o horário atual
              e inicia a nova tarefa com o mesmo horário.

        Cenário 6 — Troca de tarefa em horário específico:
            inicio=X, fim=None, com tarefa ativa
            → para a tarefa atual em X
              e inicia a nova tarefa em X.

        A validação de sobreposição dos apontamentos retroativos
        é responsabilidade do repositório.

        Returns:
            ResultadoIniciar com o apontamento criado e contexto do modo.

        Raises:
            ValueError: se projeto ou tarefa estiverem vazios.
            ApontamentoAtivoError: se houver tarefa ativa sem horário para a troca.
            SobreposicaoError: propagada para a UI tratar.
            HorarioInvalidoError: propagada para a UI tratar.
        """
        if not projeto or not projeto.strip():
            raise ValueError("Projeto não pode estar vazio.")
        if not tarefa or not tarefa.strip():
            raise ValueError("Tarefa não pode estar vazia.")

        _agora = agora or datetime.now()
        ativo  = self._repo.obter_ativo()

        # ── Cenários 3 e 4: Retroativo completo ────────────────────────────────
        if inicio is not None and fim is not None:
            if ativo is not None:
                # Cenário 4: interrompe a tarefa atual, registra o intervalo
                # e retoma a tarefa anterior ao final do intervalo.

                # 1. Para a tarefa atual no início da nova
                parado = self._repo.parar(ativo.id, fim=inicio)
                logger.info(
                    f"⏹  [Service] Intervalo: parado id={parado.id} "
                    f"em {inicio}"
                )

                # 2. Registra a nova tarefa no intervalo informado
                novo = self._repo.registrar_retroativo(
                    projeto=projeto,
                    tarefa=tarefa,
                    inicio=inicio,
                    fim=fim,
                    nota=nota,
                )
                logger.info(
                    f"📝 [Service] Intervalo: registrado id={novo.id}"
                )

                # 3. Continua a tarefa anterior a partir do fim da nova
                retomado = self._repo.iniciar(
                    projeto=ativo.projeto,
                    tarefa=ativo.tarefa,
                    inicio=fim,
                    nota=ativo.nota,
                )
                logger.info(
                    f"▶️  [Service] Intervalo: retomado id={retomado.id}"
                )

                return ResultadoIniciar(
                    apontamento=retomado,
                    anterior_parado=parado,
                    modo="retroativo_com_interrupcao",
                )

            # Cenário 3: sem tarefa ativa, registra o intervalo normalmente.
            apt = self._repo.registrar_retroativo(
                projeto=projeto,
                tarefa=tarefa,
                inicio=inicio,
                fim=fim,
                nota=nota,
            )
            logger.info(f"📝 [Service] Retroativo registrado id={apt.id}")
            return ResultadoIniciar(apontamento=apt, modo="retroativo")

        # ── Cenário 5: Troca de tarefa agora ───────────────────────────────────
        if ativo is not None and inicio is None and fim is None:
            return self._trocar_tarefa(
                ativo=ativo,
                projeto=projeto, tarefa=tarefa,
                nota=nota, agora=_agora,
            )

        # ── Cenários 1, 2 e 6: Iniciar ou trocar em horário específico ────────
        if ativo is not None:
            if inicio is not None:
                # Cenário 6: encerra a tarefa atual e inicia a nova em X.
                parado = self._repo.parar(ativo.id, fim=inicio)
                logger.info(
                    f"⏹  [Service] Troca agendada: parado id={parado.id} "
                    f"({parado.duracao_str})"
                )

                novo = self._repo.iniciar(
                    projeto=projeto,
                    tarefa=tarefa,
                    inicio=inicio,
                    nota=nota,
                )
                logger.info(f"▶️  [Service] Iniciado id={novo.id}")

                return ResultadoIniciar(
                    apontamento=novo,
                    anterior_parado=parado,
                    modo="troca",
                )

            raise ApontamentoAtivoError(
                f"Há um apontamento em execução: {ativo.projeto} / {ativo.tarefa}."
            )

        # Cenários 1 e 2: sem tarefa ativa, inicia agora ou em horário específico.
        _inicio = inicio or _agora
        apt = self._repo.iniciar(
            projeto=projeto, tarefa=tarefa, inicio=_inicio, nota=nota,
        )
        logger.info(f"▶️  [Service] Iniciado id={apt.id}")
        return ResultadoIniciar(apontamento=apt, modo="iniciado")

    def _trocar_tarefa(
        self,
        ativo: Apontamento,
        projeto: str,
        tarefa:  str,
        nota:    str,
        agora:   datetime,
    ) -> ResultadoIniciar:
        """Para o apontamento atual e inicia o novo atomicamente."""
        # Para o ativo
        parado = self._repo.parar(ativo.id, fim=agora)
        logger.info(f"⏹  [Service] Troca: parado id={parado.id} ({parado.duracao_str})")

        # Inicia o novo
        novo = self._repo.iniciar(projeto=projeto, tarefa=tarefa, inicio=agora, nota=nota)
        logger.info(f"▶️  [Service] Troca: iniciado id={novo.id}")

        return ResultadoIniciar(
            apontamento=novo,
            anterior_parado=parado,
            modo="troca",
        )

    # ── Parar ─────────────────────────────────────────────────────────────────

    def parar_ativo(
        self,
        fim:  Optional[datetime] = None,
        nota: Optional[str] = None,
        agora: Optional[datetime] = None,
    ) -> Apontamento:
        """
        Para o apontamento em execução.

        Raises:
            ApontamentoError: se não há apontamento ativo.
        """
        _agora = agora or datetime.now()
        ativo  = self._repo.obter_ativo()

        if ativo is None:
            raise ApontamentoError("Nenhum apontamento em execução para parar.")

        _fim = fim or _agora
        parado = self._repo.parar(ativo.id, fim=_fim, nota=nota)
        logger.info(f"⏹  [Service] Parado id={parado.id} ({parado.duracao_str})")
        return parado

    # ── Recuperação ao iniciar o app ──────────────────────────────────────────

    def recuperar_estado(self) -> EstadoApp:
        """
        Carrega o estado completo que a UI precisa para se montar:
        - apontamento ativo (se houver)
        - apontamentos de hoje
        - total de horas hoje
        - lista de projetos/tarefas disponíveis

        Chamado no bootstrap da MainWindow.
        """
        hoje   = date.today()
        ativo  = self._repo.obter_ativo()
        hoje_apts     = self._repo.obter_por_dia(hoje)
        total_hoje    = self._repo.total_horas_dia(hoje)
        proj_tarefas  = self._projetos_tarefas_como_dicts()

        logger.info(
            f"🔄 [Service] Estado recuperado: "
            f"ativo={'sim' if ativo else 'não'}, "
            f"{len(hoje_apts)} apt hoje, "
            f"{total_hoje:.2f}h total"
        )

        return EstadoApp(
            ativo=ativo,
            blocos_hoje=hoje_apts,
            total_horas_hoje=total_hoje,
            projetos_tarefas=proj_tarefas,
        )

    # ── Favoritos / Mais Usados ───────────────────────────────────────────────

    def calcular_favoritos(
        self,
        max_itens:       int = 5,
        dias_historico:  int = 7,
    ) -> list[ItemFavorito]:
        """
        Calcula os projetos/tarefas mais usados nos últimos N dias,
        ordenados por score de relevância.

        Score = contagem * 2.0 + (total_horas / 10) * 1.5 + bonus_recencia
        Bonus recencia: usado hoje=5.0, últimos 3d=3.0, última semana=1.5, mais=0.5

        Esta lógica migra o FavoritosHandler original para o SQLite, sem
        precisar reler o CSV a cada cálculo.
        """
        data_limite = datetime.now() - timedelta(days=dias_historico)
        apts = self._repo.buscar(data_inicio=data_limite.date())

        # Agrega por (projeto, tarefa)
        agrupado: dict[tuple[str, str], ItemFavorito] = {}
        for apt in apts:
            if apt.horas is None or apt.horas == 0:
                continue  # ignora em execução ou zero horas

            key = (apt.projeto, apt.tarefa)
            if key not in agrupado:
                agrupado[key] = ItemFavorito(
                    projeto=apt.projeto,
                    tarefa=apt.tarefa,
                    score=0.0,
                    ultima_vez=apt.inicio,
                )

            item = agrupado[key]
            item.contagem    += 1
            item.total_horas += apt.horas

            if apt.inicio > (item.ultima_vez or datetime.min):
                item.ultima_vez = apt.inicio

        # Calcula score
        agora = datetime.now()
        for item in agrupado.values():
            item.score = self._score_favorito(item, agora)

        resultado = sorted(agrupado.values(), key=lambda i: i.score, reverse=True)
        logger.info(f"🔥 [Service] {len(resultado[:max_itens])} favoritos calculados")
        return resultado[:max_itens]

    @staticmethod
    def _score_favorito(item: ItemFavorito, agora: datetime) -> float:
        score = item.contagem * 2.0 + (item.total_horas / 10) * 1.5

        dias = (agora - item.ultima_vez).days if item.ultima_vez else 999
        if dias == 0:
            score += 5.0
        elif dias <= 3:
            score += 3.0
        elif dias <= 7:
            score += 1.5
        else:
            score += 0.5

        return score

    # ── Histórico ─────────────────────────────────────────────────────────────

    def obter_historico(self, limit_dias: int = 30) -> list[BlocoHistorico]:
        return self._repo.obter_blocos_historico(limit_dias)

    def obter_intervalos_livres(self, dia: Optional[date] = None) -> list[tuple[datetime, datetime]]:
        """Intervalos sem apontamento no dia (default: hoje)."""
        return self._repo.obter_intervalos_livres(dia or date.today())

    # ── Delegações diretas ao Repository ─────────────────────────────────────
    # A UI nunca chama o repo diretamente — usa estas fachadas.

    def dividir(self, apontamento_id: int, horario_corte: datetime):
        return self._repo.dividir(apontamento_id, horario_corte)

    def atualizar_projeto_tarefa(self, apontamento_id: int, projeto: str, tarefa: str):
        return self._repo.atualizar_projeto_tarefa(apontamento_id, projeto, tarefa)

    def ajustar_inicio(self, apontamento_id: int, novo_inicio: datetime, ignorar_sobreposicao: bool = False):
        return self._repo.ajustar_inicio(apontamento_id, novo_inicio, ignorar_sobreposicao=ignorar_sobreposicao)

    def ajustar_fim(self, apontamento_id: int, novo_fim: datetime, ignorar_sobreposicao: bool = False):
        return self._repo.ajustar_fim(apontamento_id, novo_fim, ignorar_sobreposicao=ignorar_sobreposicao)

    def slide_adjacentes(self, apt: Apontamento, delta_ini=None, delta_fim=None):
        if delta_fim:
            proximo = self._repo.buscar_por_inicio(apt.fim)
            if proximo:
                novo_ini_prox = proximo.inicio + delta_fim
                novo_fim_prox = (proximo.fim + delta_fim) if proximo.fim else None
                if delta_fim < timedelta(0):
                    # Deslocando para trás: ajusta início primeiro, senão fim < início atual
                    self._repo.ajustar_inicio(proximo.id, novo_ini_prox, ignorar_sobreposicao=True)
                    if novo_fim_prox:
                        self._repo.ajustar_fim(proximo.id, novo_fim_prox, ignorar_sobreposicao=True)
                else:
                    # Deslocando para frente: mantém ordem original
                    if novo_fim_prox:
                        self._repo.ajustar_fim(proximo.id, novo_fim_prox, ignorar_sobreposicao=True)
                    self._repo.ajustar_inicio(proximo.id, novo_ini_prox, ignorar_sobreposicao=True)

        if delta_ini:
            anterior = self._repo.buscar_por_fim(apt.inicio)
            if anterior:
                novo_fim_ant = anterior.fim + delta_ini
                # Ajusta o anterior ANTES de expandir o atual
                self._repo.ajustar_fim(anterior.id, novo_fim_ant, ignorar_sobreposicao=True)

    def atualizar_nota(self, apontamento_id: int, nota: str):
        return self._repo.atualizar_nota(apontamento_id, nota)

    def deletar(self, apontamento_id: int) -> bool:
        return self._repo.deletar(apontamento_id)

    def reabrir(self, apontamento_id: int) -> Apontamento:
        return self._repo.reabrir(apontamento_id)

    def obter_ativo(self) -> Optional[Apontamento]:
        return self._repo.obter_ativo()

    def listar_projetos_tarefas(self) -> list[ProjetoTarefa]:
        return self._repo.listar_projetos_tarefas(apenas_ativos=True)

    def sincronizar_projetos_tarefas(self, dados: list[dict]) -> int:
        return self._repo.sincronizar_projetos_tarefas(dados)

    def obter_historico_audit(self, apontamento_id: int):
        return self._repo.obter_historico_audit(apontamento_id)

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _projetos_tarefas_como_dicts(self) -> list[dict]:
        """Converte ProjetoTarefa em dicts simples para os ComboBoxes da UI."""
        return [
            {"projeto": pt.projeto, "tarefa": pt.tarefa}
            for pt in self._repo.listar_projetos_tarefas(apenas_ativos=True)
        ]