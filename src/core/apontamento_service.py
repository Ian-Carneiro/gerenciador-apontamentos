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

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.core.config_jornada_handler import ConfigJornadaHandler
from src.db.models import Apontamento, DiaExcecao, ProjetoTarefa
from src.db.repository import (
    ApontamentoAtivoError,
    ApontamentoError,
    ApontamentoRepository,
    BlocoHistorico,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ── DTOs de resultado ─────────────────────────────────────────────────────────


@dataclass
class ResultadoIniciar:
    """Retorno de iniciar_ou_registrar() com contexto para a UI."""

    apontamento: Apontamento
    anterior_parado: Apontamento | None = None  # se houve troca de tarefa
    modo: str = "iniciado"  # "iniciado" | "retroativo" | "troca"

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
    tarefa: str
    score: float
    contagem: int = 0
    total_horas: float = 0.0
    ultima_vez: datetime | None = None

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

    ativo: Apontamento | None
    blocos_hoje: list[Apontamento]
    total_horas_hoje: float
    projetos_tarefas: list[dict]  # [{"projeto": ..., "tarefa": ...}]

    @property
    def em_execucao(self) -> bool:
        return self.ativo is not None

    @property
    def total_hoje_str(self) -> str:
        h = int(self.total_horas_hoje)
        m = int((self.total_horas_hoje - h) * 60)
        return f"{h}h {m:02d}min"


@dataclass
class DiaRelatorio:
    data: date
    esperado: float
    trabalhado: float
    excecao: DiaExcecao | None = None

    @property
    def saldo(self) -> float:
        return self.trabalhado - self.esperado


@dataclass
class RelatorioJornada:
    data_referencia: date
    trabalhado_hoje: float
    esperado_hoje: float
    saldo_mes: float
    periodo_mes_inicio: date
    periodo_mes_fim: date
    saldo_banco: float
    periodo_banco_inicio: date
    periodo_banco_fim: date
    dias_uteis_restantes_banco: int
    dias_mes: list[DiaRelatorio]

    @property
    def falta_hoje(self) -> float:
        return max(0.0, self.esperado_hoje - self.trabalhado_hoje)


# ── Service ───────────────────────────────────────────────────────────────────


class ApontamentoService:
    """
    Ponto de entrada único para toda lógica de negócio.
    Instancie uma vez na aplicação e injete onde necessário.
    """

    def __init__(self, repo: ApontamentoRepository | None = None):
        self._repo = repo or ApontamentoRepository()

    @property
    def repo(self):
        return self._repo

    # ── Fluxo principal: Iniciar / Registrar ──────────────────────────────────

    def iniciar_ou_registrar(
        self,
        projeto: str,
        tarefa: str,
        inicio: datetime | None = None,
        fim: datetime | None = None,
        nota: str = "",
        agora: datetime | None = None,
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
        ativo = self._repo.obter_ativo()

        # ── Cenários 3 e 4: Retroativo completo ────────────────────────────────
        if inicio is not None and fim is not None:
            if ativo is not None:
                # Cenário 4: interrompe a tarefa atual, registra o intervalo
                # e retoma a tarefa anterior ao final do intervalo.

                # 1. Para a tarefa atual no início da nova
                parado = self._repo.parar(ativo.id, fim=inicio)
                logger.info(f"⏹  [Service] Intervalo: parado id={parado.id} em {inicio}")

                # 2. Registra a nova tarefa no intervalo informado
                novo = self._repo.registrar_retroativo(
                    projeto=projeto,
                    tarefa=tarefa,
                    inicio=inicio,
                    fim=fim,
                    nota=nota,
                )
                logger.info(f"📝 [Service] Intervalo: registrado id={novo.id}")

                # 3. Continua a tarefa anterior a partir do fim da nova
                retomado = self._repo.iniciar(
                    projeto=ativo.projeto,
                    tarefa=ativo.tarefa,
                    inicio=fim,
                    nota=ativo.nota,
                )
                logger.info(f"▶️  [Service] Intervalo: retomado id={retomado.id}")

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
                projeto=projeto,
                tarefa=tarefa,
                nota=nota,
                agora=_agora,
            )

        # ── Cenários 1, 2 e 6: Iniciar ou trocar em horário específico ────────
        if ativo is not None:
            if inicio is not None:
                # Cenário 6: encerra a tarefa atual e inicia a nova em X.
                parado = self._repo.parar(ativo.id, fim=inicio)
                logger.info(
                    f"⏹  [Service] Troca agendada: parado id={parado.id} ({parado.duracao_str})"
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
            projeto=projeto,
            tarefa=tarefa,
            inicio=_inicio,
            nota=nota,
        )
        logger.info(f"▶️  [Service] Iniciado id={apt.id}")
        return ResultadoIniciar(apontamento=apt, modo="iniciado")

    def _trocar_tarefa(
        self,
        ativo: Apontamento,
        projeto: str,
        tarefa: str,
        nota: str,
        agora: datetime,
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
        fim: datetime | None = None,
        nota: str | None = None,
        agora: datetime | None = None,
    ) -> Apontamento:
        """
        Para o apontamento em execução.

        Raises:
            ApontamentoError: se não há apontamento ativo.
        """
        _agora = agora or datetime.now()
        ativo = self._repo.obter_ativo()

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
        hoje = date.today()
        ativo = self._repo.obter_ativo()
        hoje_apts = self._repo.obter_por_dia(hoje)
        total_hoje = self._repo.total_horas_dia(hoje)
        proj_tarefas = self._projetos_tarefas_como_dicts()

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
        max_itens: int = 5,
        dias_historico: int = 7,
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
            item.contagem += 1
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

    def obter_intervalos_livres(self, dia: date | None = None) -> list[tuple[datetime, datetime]]:
        """Intervalos sem apontamento no dia (default: hoje)."""
        return self._repo.obter_intervalos_livres(dia or date.today())

    # ── Delegações diretas ao Repository ─────────────────────────────────────
    # A UI nunca chama o repo diretamente — usa estas fachadas.

    def dividir(self, apontamento_id: int, horario_corte: datetime):
        return self._repo.dividir(apontamento_id, horario_corte)

    def inserir_apontamento(
        self,
        apt_referencia: Apontamento,
        posicao: str,  # "antes" | "depois"
        projeto: str,
        tarefa: str,
        horario: datetime,
        nota: str = "",
    ) -> Apontamento:
        """
        Insere um novo apontamento antes ou depois de `apt_referencia`,
        deslocando o vizinho correspondente para evitar buraco/sobreposição
        (mesma lógica de slide usada em ajustar_inicio/ajustar_fim).
        """
        if posicao == "antes":
            if not horario < apt_referencia.inicio:
                raise ValueError(
                    "O início deve ser anterior ao início do apontamento de referência."
                )

            anterior = self._repo.buscar_por_fim(apt_referencia.inicio)
            if anterior and horario < anterior.inicio:
                raise ValueError("Horário conflita com o apontamento anterior a ele.")
            if anterior:
                self._repo.ajustar_fim(anterior.id, horario, ignorar_sobreposicao=True)

            novo = self._repo.registrar_retroativo(
                projeto=projeto,
                tarefa=tarefa,
                inicio=horario,
                fim=apt_referencia.inicio,
                nota=nota,
            )

        elif posicao == "depois":
            if apt_referencia.fim is None:
                raise ApontamentoError("Finalize o apontamento para adicionar depois dele.")
            if not horario > apt_referencia.fim:
                raise ValueError("O fim deve ser posterior ao fim do apontamento de referência.")

            proximo = self._repo.buscar_por_inicio(apt_referencia.fim)
            if proximo and proximo.fim is not None and horario > proximo.fim:
                raise ValueError("Horário conflita com o apontamento seguinte a ele.")
            if proximo:
                self._repo.ajustar_inicio(proximo.id, horario, ignorar_sobreposicao=True)

            novo = self._repo.registrar_retroativo(
                projeto=projeto,
                tarefa=tarefa,
                inicio=apt_referencia.fim,
                fim=horario,
                nota=nota,
            )

        else:
            raise ValueError(f"Posição inválida: {posicao!r}")

        logger.info(f"➕ [Service] Inserido {posicao} de id={apt_referencia.id}: novo id={novo.id}")
        return novo

    def atualizar_projeto_tarefa(self, apontamento_id: int, projeto: str, tarefa: str):
        return self._repo.atualizar_projeto_tarefa(apontamento_id, projeto, tarefa)

    def ajustar_inicio(
        self, apontamento_id: int, novo_inicio: datetime, ignorar_sobreposicao: bool = False
    ):
        return self._repo.ajustar_inicio(
            apontamento_id, novo_inicio, ignorar_sobreposicao=ignorar_sobreposicao
        )

    def ajustar_fim(
        self, apontamento_id: int, novo_fim: datetime, ignorar_sobreposicao: bool = False
    ):
        return self._repo.ajustar_fim(
            apontamento_id, novo_fim, ignorar_sobreposicao=ignorar_sobreposicao
        )

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

    def obter_ativo(self) -> Apontamento | None:
        return self._repo.obter_ativo()

    def listar_projetos_tarefas(self) -> list[ProjetoTarefa]:
        return self._repo.listar_projetos_tarefas(apenas_ativos=True)

    def sincronizar_projetos_tarefas(self, dados: list[dict]) -> int:
        return self._repo.sincronizar_projetos_tarefas(dados)

    def obter_historico_audit(self, apontamento_id: int):
        return self._repo.obter_historico_audit(apontamento_id)

    # ── Jornada / Relatório ───────────────────────────────────────────────────

    def obter_config_jornada(self):
        return ConfigJornadaHandler.obter()

    def salvar_config_jornada(self, **kwargs):
        return ConfigJornadaHandler.salvar(**kwargs)

    def listar_excecoes(self) -> list[DiaExcecao]:
        return self._repo.listar_excecoes()

    def criar_excecao(self, **kwargs) -> DiaExcecao:
        return self._repo.criar_excecao(**kwargs)

    def atualizar_excecao(self, excecao_id: int, **kwargs) -> DiaExcecao:
        return self._repo.atualizar_excecao(excecao_id, **kwargs)

    def deletar_excecao(self, excecao_id: int) -> bool:
        return self._repo.deletar_excecao(excecao_id)

    def calcular_relatorio(
        self, data_referencia: date | None = None, sem_segundos: bool = False
    ) -> RelatorioJornada:
        hoje_ref = data_referencia or date.today()
        cfg = ConfigJornadaHandler.obter()
        dias_trabalho = set(cfg.dias_trabalho)

        excecoes = self._repo.listar_excecoes()
        excecoes_fixas = {e.data: e for e in excecoes if not e.recorrente}
        excecoes_recorrentes = {(e.data.month, e.data.day): e for e in excecoes if e.recorrente}

        def excecao_do_dia(dia: date) -> DiaExcecao | None:
            return excecoes_fixas.get(dia) or excecoes_recorrentes.get((dia.month, dia.day))

        def esperado_dia(dia: date) -> float:
            if dia.weekday() not in dias_trabalho:
                return 0.0
            exc = excecao_do_dia(dia)
            if exc is None:
                return cfg.jornada_horas_dia
            if exc.dia_inteiro:
                return 0.0
            return max(0.0, cfg.jornada_horas_dia - exc.horas_abonadas)

        ativo = self._repo.obter_ativo()
        agora = datetime.now()

        def trabalhado_dia(dia: date, totais: dict[date, float]) -> float:
            total = totais.get(dia, 0.0)
            if ativo is not None and ativo.inicio.date() == dia:
                inicio = (
                    ativo.inicio.replace(second=0, microsecond=0) if sem_segundos else ativo.inicio
                )
                ref = agora.replace(second=0, microsecond=0) if sem_segundos else agora
                total += (ref - inicio).total_seconds() / 3600
            return total

        # ── Mês (do dia 1 até a data de referência) ──
        mes_inicio, mes_fim = self._periodo_banco(cfg.banco_horas_ancora, 1, hoje_ref)
        totais_mes = self._repo.total_horas_por_dia(mes_inicio, hoje_ref, sem_segundos)

        dias_mes: list[DiaRelatorio] = []
        saldo_mes = 0.0
        d = mes_inicio
        while d <= hoje_ref:
            esp = esperado_dia(d)
            trab = trabalhado_dia(d, totais_mes)
            dias_mes.append(
                DiaRelatorio(data=d, esperado=esp, trabalhado=trab, excecao=excecao_do_dia(d))
            )
            saldo_mes += trab - esp
            d += timedelta(days=1)

        # ── Banco de horas (período atual, até a data de referência) ──
        periodo_inicio, periodo_fim = self._periodo_banco(
            cfg.banco_horas_ancora, cfg.banco_horas_meses, hoje_ref
        )
        totais_banco = self._repo.total_horas_por_dia(periodo_inicio, hoje_ref, sem_segundos)
        saldo_banco = 0.0
        d = periodo_inicio
        while d <= hoje_ref:
            saldo_banco += trabalhado_dia(d, totais_banco) - esperado_dia(d)
            d += timedelta(days=1)

        dias_uteis_restantes = 0
        d = hoje_ref + timedelta(days=1)
        while d <= periodo_fim:
            if esperado_dia(d) > 0:
                dias_uteis_restantes += 1
            d += timedelta(days=1)

        return RelatorioJornada(
            data_referencia=hoje_ref,
            trabalhado_hoje=trabalhado_dia(hoje_ref, totais_mes),
            esperado_hoje=esperado_dia(hoje_ref),
            saldo_mes=saldo_mes,
            periodo_mes_inicio=mes_inicio,
            periodo_mes_fim=mes_fim,
            saldo_banco=saldo_banco,
            periodo_banco_inicio=periodo_inicio,
            periodo_banco_fim=periodo_fim,
            dias_uteis_restantes_banco=dias_uteis_restantes,
            dias_mes=dias_mes,
        )

    @staticmethod
    def _add_meses(d: date, meses: int) -> date:
        mes_total = d.month - 1 + meses
        ano = d.year + mes_total // 12
        mes = mes_total % 12 + 1
        dia = min(d.day, monthrange(ano, mes)[1])
        return date(ano, mes, dia)

    @staticmethod
    def _fim_periodo(inicio: date, meses: int) -> date:
        """fim = (dia_corte - 1) do mês seguinte ao último mês do período."""
        proximo = ApontamentoService._add_meses(inicio, meses)
        dia = min(proximo.day - 1, monthrange(proximo.year, proximo.month)[1])
        if dia < 1:
            # corte no dia 1: fim é o último dia do mês anterior
            proximo = proximo.replace(day=1) - timedelta(days=1)
            return proximo
        return date(proximo.year, proximo.month, dia)

    @classmethod
    def _periodo_banco(cls, ancora: date, meses: int, referencia: date) -> tuple[date, date]:
        inicio = ancora
        fim = cls._fim_periodo(inicio, meses)
        # Avança se referencia está além do período atual
        while fim < referencia:
            inicio = cls._add_meses(inicio, meses)
            fim = cls._fim_periodo(inicio, meses)
        # Recua se referencia está antes do período atual
        while inicio > referencia:
            inicio = cls._add_meses(inicio, -meses)
            fim = cls._fim_periodo(inicio, meses)
        return inicio, fim

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _projetos_tarefas_como_dicts(self) -> list[dict]:
        """Converte ProjetoTarefa em dicts simples para os ComboBoxes da UI."""
        return [
            {"projeto": pt.projeto, "tarefa": pt.tarefa}
            for pt in self._repo.listar_projetos_tarefas(apenas_ativos=True)
        ]
