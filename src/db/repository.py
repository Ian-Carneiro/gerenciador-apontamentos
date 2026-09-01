"""
ApontamentoRepository — Camada de acesso a dados.

Toda operação no banco passa por aqui.
A UI e os services NUNCA acessam o banco diretamente.

Regras de negócio de baixo nível (validações de intervalo, sobreposição)
ficam aqui. Regras de negócio de alto nível (ex: trocar tarefa automaticamente)
ficam em ApontamentoService.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.db.database import get_session
from src.db.models import Apontamento, ApontamentoAudit, ProjetoTarefa
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ── Exceções de domínio ───────────────────────────────────────────────────────


class ApontamentoError(Exception):
    """Erro de regra de negócio nos apontamentos."""


class SobreposicaoError(ApontamentoError):
    """Novo intervalo conflita com um já existente."""

    def __init__(self, conflito: Apontamento):
        self.conflito = conflito
        super().__init__(
            f"Intervalo conflita com apontamento existente: "
            f"{conflito.projeto} / {conflito.tarefa} "
            f"{conflito.inicio.strftime('%H:%M')}–"
            f"{conflito.fim.strftime('%H:%M') if conflito.fim else '…'}"
        )


class ApontamentoAtivoError(ApontamentoError):
    """Já existe um apontamento em execução."""


class HorarioInvalidoError(ApontamentoError):
    """Horário de início >= fim, ou fora do intervalo do apontamento."""


# ── DTOs ──────────────────────────────────────────────────────────────────────


@dataclass
class BlocoHistorico:
    """Grupo de apontamentos de um mesmo dia para exibição no histórico."""

    data: date
    apontamentos: list[Apontamento]

    @property
    def total_horas(self) -> float:
        return sum(a.horas or 0.0 for a in self.apontamentos)

    @property
    def total_str(self) -> str:
        h = int(self.total_horas)
        m = int((self.total_horas - h) * 60)
        return f"{h}h {m:02d}min"


# ── Repository ────────────────────────────────────────────────────────────────


class ApontamentoRepository:
    """
    CRUD + regras de dado para Apontamento.
    Instancie uma vez e reutilize (é stateless).
    """

    # ── Operações principais ──────────────────────────────────────────────────

    def iniciar(
        self,
        projeto: str,
        tarefa: str,
        inicio: datetime,
        nota: str = "",
    ) -> Apontamento:
        """
        Inicia um novo apontamento (fim=None).

        Raises:
            ApontamentoAtivoError: se já há um em execução.
            SobreposicaoError: se o horário de início conflita com um existente.
        """
        with get_session() as s:
            self._assert_sem_ativo(s)
            self._assert_sem_sobreposicao(s, inicio=inicio, fim=None, excluir_id=None)

            apt = Apontamento(
                projeto=projeto.strip(),
                tarefa=tarefa.strip(),
                inicio=inicio,
                fim=None,
                nota=nota.strip(),
            )
            s.add(apt)
            s.flush()
            self._upsert_projeto_tarefa(s, apt.projeto, apt.tarefa)
            logger.info(f"▶️  Iniciado: {apt}")
            return apt

    def parar(
        self,
        apontamento_id: int,
        fim: datetime,
        nota: str | None = None,
    ) -> Apontamento:
        """
        Finaliza o apontamento ativo definindo o horário de fim.

        Raises:
            ApontamentoError: se o apontamento não existir ou já estiver finalizado.
            HorarioInvalidoError: se fim <= inicio.
        """
        with get_session() as s:
            apt = self._get_or_raise(s, apontamento_id)

            if apt.fim is not None:
                raise ApontamentoError(f"Apontamento {apontamento_id} já está finalizado.")

            if fim <= apt.inicio:
                raise HorarioInvalidoError(
                    f"Fim ({fim.strftime('%H:%M:%S')}) deve ser posterior ao início "
                    f"({apt.inicio.strftime('%H:%M:%S')})."
                )

            self._registrar_audit(s, apt, "fim", None, fim.isoformat())
            if nota is not None and nota.strip() != apt.nota:
                self._registrar_audit(s, apt, "nota", apt.nota, nota.strip())
                apt.nota = nota.strip()

            apt.fim = fim
            apt.parada = True
            logger.info(f"⏹  Parado: {apt}")
            return apt

    def reabrir(self, apontamento_id: int) -> Apontamento:
        """
        Reabre um apontamento finalizado, removendo o horário de fim.
        Usado para desfazer um "parar" feito por engano.

        Raises:
            ApontamentoError: se não existir ou já estiver em execução.
            ApontamentoAtivoError: se já houver outro apontamento ativo.
        """
        with get_session() as s:
            apt = self._get_or_raise(s, apontamento_id)

            if apt.fim is None:
                raise ApontamentoError(f"Apontamento {apontamento_id} já está em execução.")

            self._assert_sem_ativo(s)

            posterior = s.scalars(select(Apontamento).where(Apontamento.inicio > apt.fim)).first()
            if posterior is not None:
                raise ApontamentoError(
                    f"Não é possível reabrir: existe apontamento posterior "
                    f"({posterior.projeto} / {posterior.tarefa} às "
                    f"{posterior.inicio.strftime('%H:%M')})."
                )

            self._registrar_audit(s, apt, "fim", apt.fim.isoformat(), None)
            apt.fim = None
            apt.parada = False
            logger.info(f"▶️  Reaberto: {apt}")
            return apt

    def registrar_retroativo(
        self,
        projeto: str,
        tarefa: str,
        inicio: datetime,
        fim: datetime,
        nota: str = "",
        ignorar_sobreposicao: bool = False,
    ) -> Apontamento:
        """
        Registra um apontamento completo (início e fim já definidos).
        Usado tanto para apontamentos normais retroativos quanto para
        inserção em intervalos entre apontamentos já finalizados.

        Args:
            ignorar_sobreposicao: Se True, não valida sobreposição.
                Use apenas quando o chamador já verificou manualmente.

        Raises:
            HorarioInvalidoError: se fim <= inicio.
            SobreposicaoError: se o intervalo conflita com um existente
                               e ignorar_sobreposicao=False.
        """
        if fim <= inicio:
            raise HorarioInvalidoError(
                f"Fim ({fim.strftime('%H:%M:%S')}) deve ser posterior ao início "
                f"({inicio.strftime('%H:%M:%S')})."
            )

        with get_session() as s:
            if not ignorar_sobreposicao:
                self._assert_sem_sobreposicao(s, inicio=inicio, fim=fim, excluir_id=None)

            apt = Apontamento(
                projeto=projeto.strip(),
                tarefa=tarefa.strip(),
                inicio=inicio,
                fim=fim,
                parada=True,
                nota=nota.strip(),
            )
            s.add(apt)
            s.flush()
            self._upsert_projeto_tarefa(s, apt.projeto, apt.tarefa)
            logger.info(f"📝 Retroativo: {apt}")
            return apt

    def obter_intervalos_livres(self, dia: date) -> list[tuple[datetime, datetime]]:
        """
        Retorna os intervalos de tempo sem apontamento em um dia.
        Útil para mostrar ao usuário onde ele pode inserir retroativos.

        Returns:
            Lista de tuplas (inicio_livre, fim_livre). O último intervalo
            vai até o fim do dia (23:59:59) se não houver apontamento em execução.
        """
        with get_session() as s:
            apts = self._apontamentos_do_dia(s, dia, incluir_em_execucao=True)

        if not apts:
            inicio_dia = datetime.combine(dia, datetime.min.time())
            fim_dia = datetime.combine(dia, datetime.max.time().replace(microsecond=0))
            return [(inicio_dia, fim_dia)]

        intervalos: list[tuple[datetime, datetime]] = []
        inicio_dia = datetime.combine(dia, datetime.min.time())

        # Intervalo antes do primeiro apontamento
        if apts[0].inicio > inicio_dia:
            intervalos.append((inicio_dia, apts[0].inicio))

        # Intervalos entre apontamentos consecutivos
        for i in range(len(apts) - 1):
            fim_atual = apts[i].fim
            inicio_prox = apts[i + 1].inicio
            if fim_atual and inicio_prox > fim_atual:
                intervalos.append((fim_atual, inicio_prox))

        # Intervalo após o último apontamento (se finalizado)
        ultimo = apts[-1]
        if ultimo.fim is not None:
            fim_dia = datetime.combine(dia, datetime.max.time().replace(microsecond=0))
            if fim_dia > ultimo.fim:
                intervalos.append((ultimo.fim, fim_dia))

        return intervalos

    def dividir(
        self,
        apontamento_id: int,
        horario_corte: datetime,
    ) -> tuple[Apontamento, Apontamento]:
        """
        Divide um apontamento finalizado em dois no horário de corte.

        Parte 1: [inicio original → horario_corte]
        Parte 2: [horario_corte → fim original]
        Projeto e tarefa são herdados. Notas são copiadas para ambas as partes.

        Raises:
            ApontamentoError: se apontamento não existir ou estiver em execução.
            HorarioInvalidoError: se o corte não estiver dentro do intervalo.
        """
        with get_session() as s:
            original = self._get_or_raise(s, apontamento_id)

            if original.fim is None:
                raise ApontamentoError(
                    "Não é possível dividir um apontamento em execução. Pare-o primeiro."
                )

            if not (original.inicio < horario_corte < original.fim):
                raise HorarioInvalidoError(
                    f"Horário de corte ({horario_corte.strftime('%H:%M:%S')}) "
                    f"deve estar entre {original.inicio.strftime('%H:%M:%S')} "
                    f"e {original.fim.strftime('%H:%M:%S')}."
                )

            fim_original = original.fim

            # Registra auditoria antes de modificar
            self._registrar_audit(
                s, original, "fim", fim_original.isoformat(), horario_corte.isoformat()
            )

            # Encurta o original
            original.fim = horario_corte

            # Cria a segunda metade
            segunda = Apontamento(
                projeto=original.projeto,
                tarefa=original.tarefa,
                inicio=horario_corte,
                fim=fim_original,
                parada=True,
                nota=original.nota,
            )
            s.add(segunda)
            s.flush()

            logger.info(
                f"✂️  Dividido id={apontamento_id}: "
                f"{original.inicio.strftime('%H:%M')}→{horario_corte.strftime('%H:%M')} "
                f"| {horario_corte.strftime('%H:%M')}→{fim_original.strftime('%H:%M')}"
            )
            return original, segunda

    # ── Edição ────────────────────────────────────────────────────────────────

    def atualizar_projeto_tarefa(
        self,
        apontamento_id: int,
        projeto: str,
        tarefa: str,
    ) -> Apontamento:
        """
        Altera projeto e/ou tarefa de um apontamento pelo seu id.
        Com SQLite e uma row por intervalo, não há risco de editar o par errado.
        """
        with get_session() as s:
            apt = self._get_or_raise(s, apontamento_id)

            projeto = projeto.strip()
            tarefa = tarefa.strip()

            if apt.projeto != projeto:
                self._registrar_audit(s, apt, "projeto", apt.projeto, projeto)
                apt.projeto = projeto

            if apt.tarefa != tarefa:
                self._registrar_audit(s, apt, "tarefa", apt.tarefa, tarefa)
                apt.tarefa = tarefa

            logger.info(f"✏️  Projeto/Tarefa atualizado: id={apontamento_id}")
            return apt

    def ajustar_inicio(
        self, apontamento_id: int, novo_inicio: datetime, ignorar_sobreposicao=False
    ) -> Apontamento:
        """
        Ajusta o horário de início.

        Raises:
            HorarioInvalidoError: se novo_inicio >= fim (quando finalizado).
            SobreposicaoError: se o novo horário conflita com outro apontamento.
        """
        with get_session() as s:
            apt = self._get_or_raise(s, apontamento_id)

            if apt.fim is not None and novo_inicio >= apt.fim:
                raise HorarioInvalidoError(
                    f"Novo início ({novo_inicio.strftime('%H:%M:%S')}) "
                    f"deve ser anterior ao fim ({apt.fim.strftime('%H:%M:%S')})."
                )

            if not ignorar_sobreposicao:
                self._assert_sem_sobreposicao(
                    s, inicio=novo_inicio, fim=apt.fim, excluir_id=apontamento_id
                )

            self._registrar_audit(s, apt, "inicio", apt.inicio.isoformat(), novo_inicio.isoformat())
            apt.inicio = novo_inicio
            logger.info(f"⏱  Início ajustado: id={apontamento_id} → {novo_inicio}")
            return apt

    def ajustar_fim(
        self, apontamento_id: int, novo_fim: datetime, ignorar_sobreposicao=False
    ) -> Apontamento:
        """
        Ajusta o horário de fim.

        Raises:
            HorarioInvalidoError: se novo_fim <= inicio.
            SobreposicaoError: se o novo horário conflita com outro apontamento.
        """
        with get_session() as s:
            apt = self._get_or_raise(s, apontamento_id)

            if novo_fim <= apt.inicio:
                raise HorarioInvalidoError(
                    f"Novo fim ({novo_fim.strftime('%H:%M:%S')}) "
                    f"deve ser posterior ao início ({apt.inicio.strftime('%H:%M:%S')})."
                )

            if not ignorar_sobreposicao:
                self._assert_sem_sobreposicao(
                    s, inicio=apt.inicio, fim=novo_fim, excluir_id=apontamento_id
                )

            anterior = apt.fim.isoformat() if apt.fim else None
            self._registrar_audit(s, apt, "fim", anterior, novo_fim.isoformat())
            apt.fim = novo_fim
            apt.parada = True
            logger.info(f"⏱  Fim ajustado: id={apontamento_id} → {novo_fim}")
            return apt

    def atualizar_nota(self, apontamento_id: int, nota: str) -> Apontamento:
        with get_session() as s:
            apt = self._get_or_raise(s, apontamento_id)
            self._registrar_audit(s, apt, "nota", apt.nota, nota.strip())
            apt.nota = nota.strip()
            return apt

    def deletar(self, apontamento_id: int) -> bool:
        """
        Remove um apontamento (e suas auditorias via cascade).
        Retorna True se deletado, False se não encontrado.
        """
        with get_session() as s:
            apt = s.get(Apontamento, apontamento_id)
            if apt is None:
                logger.warning(f"🗑  Deletar: id={apontamento_id} não encontrado")
                return False
            s.delete(apt)
            logger.info(f"🗑  Deletado: id={apontamento_id}")
            return True

    # ── Consultas ─────────────────────────────────────────────────────────────

    def obter_ativo(self) -> Apontamento | None:
        """Retorna o apontamento em execução, ou None."""
        with get_session() as s:
            stmt = select(Apontamento).where(Apontamento.fim.is_(None))
            return s.scalars(stmt).first()

    def obter_por_id(self, apontamento_id: int) -> Apontamento | None:
        with get_session() as s:
            return s.get(Apontamento, apontamento_id)

    def obter_por_dia(self, dia: date) -> list[Apontamento]:
        """Apontamentos de um dia ordenados por início."""
        with get_session() as s:
            return self._apontamentos_do_dia(s, dia, incluir_em_execucao=True)

    def buscar_por_inicio(self, inicio: datetime) -> Apontamento | None:
        """Retorna o apontamento que começa exatamente em `inicio`, ou None."""
        with get_session() as s:
            stmt = select(Apontamento).where(Apontamento.inicio == inicio)
            apt = s.scalars(stmt).first()
            if apt:
                _ = apt.projeto, apt.tarefa, apt.inicio, apt.fim
            return apt

    def buscar_por_fim(self, fim: datetime) -> Apontamento | None:
        """Retorna o apontamento que termina exatamente em `fim`, ou None."""
        with get_session() as s:
            stmt = select(Apontamento).where(Apontamento.fim == fim)
            apt = s.scalars(stmt).first()
            if apt:
                _ = apt.projeto, apt.tarefa, apt.inicio, apt.fim
            return apt

    def obter_blocos_historico(self, limit_dias: int = 30) -> list[BlocoHistorico]:
        """
        Agrupa apontamentos finalizados por dia, ordenados do mais recente
        ao mais antigo. Usado pela tela de Histórico.
        """
        with get_session() as s:
            # Busca apontamentos finalizados agrupados por data
            stmt = select(Apontamento).order_by(Apontamento.inicio.desc())
            apts = list(s.scalars(stmt).all())

        # Agrupa por data
        por_data: dict[date, list[Apontamento]] = {}
        for apt in apts:
            d = apt.inicio.date()
            por_data.setdefault(d, []).append(apt)

        blocos = [
            BlocoHistorico(data=d, apontamentos=apts_dia)
            for d, apts_dia in sorted(por_data.items(), reverse=True)
        ]

        return blocos[:limit_dias]

    def buscar(
        self,
        texto: str = "",
        projeto: str = "",
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> list[Apontamento]:
        """
        Busca com filtros opcionais. Todos os parâmetros são combinados (AND).
        """
        with get_session() as s:
            conditions = []

            if texto:
                like = f"%{texto}%"
                conditions.append(
                    or_(
                        Apontamento.projeto.ilike(like),
                        Apontamento.tarefa.ilike(like),
                        Apontamento.nota.ilike(like),
                    )
                )

            if projeto:
                conditions.append(Apontamento.projeto.ilike(f"%{projeto}%"))

            if data_inicio:
                dt_inicio = datetime.combine(data_inicio, datetime.min.time())
                conditions.append(Apontamento.inicio >= dt_inicio)

            if data_fim:
                dt_fim = datetime.combine(data_fim, datetime.max.time())
                conditions.append(Apontamento.inicio <= dt_fim)

            stmt = select(Apontamento).where(*conditions).order_by(Apontamento.inicio.desc())
            return list(s.scalars(stmt).all())

    def total_horas_dia(self, dia: date) -> float:
        """Total de horas trabalhadas num dia (apenas apontamentos finalizados)."""
        apts = self.obter_por_dia(dia)
        return sum(a.horas or 0.0 for a in apts if a.fim is not None)

    def obter_historico_audit(self, apontamento_id: int) -> list[ApontamentoAudit]:
        with get_session() as s:
            stmt = (
                select(ApontamentoAudit)
                .where(ApontamentoAudit.apontamento_id == apontamento_id)
                .order_by(ApontamentoAudit.alterado_em)
            )
            return list(s.scalars(stmt).all())

    # ── Projetos / Tarefas ────────────────────────────────────────────────────

    def listar_projetos_tarefas(self, apenas_ativos: bool = True) -> list[ProjetoTarefa]:
        with get_session() as s:
            stmt = select(ProjetoTarefa)
            if apenas_ativos:
                stmt = stmt.where(ProjetoTarefa.ativo.is_(True))
            stmt = stmt.order_by(ProjetoTarefa.projeto, ProjetoTarefa.tarefa)
            return list(s.scalars(stmt).all())

    def sincronizar_projetos_tarefas(self, dados: list[dict]) -> int:
        """
        Upsert em lote de projetos/tarefas baixados do NetProject.
        Retorna quantidade de registros processados.
        """
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with get_session() as s:
            agora = datetime.now()
            count = 0
            for d in dados:
                stmt = sqlite_insert(ProjetoTarefa).values(
                    projeto=d["projeto"],
                    tarefa=d["tarefa"],
                    ativo=d.get("ativo", True),
                    start_date=d.get("start", ""),
                    finish_date=d.get("finish", ""),
                    percent_complete=int(d.get("percent_complete", 0) or 0),
                    notes=d.get("notes", ""),
                    atualizado_em=agora,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["projeto", "tarefa"],
                    set_={
                        "ativo": stmt.excluded.ativo,
                        "start_date": stmt.excluded.start_date,
                        "finish_date": stmt.excluded.finish_date,
                        "percent_complete": stmt.excluded.percent_complete,
                        "notes": stmt.excluded.notes,
                        "atualizado_em": agora,
                    },
                )
                s.execute(stmt)
                count += 1

            logger.info(f"🔄 {count} projetos/tarefas sincronizados")
            return count

    def renomear_projeto_tarefa(
        self,
        projeto_atual: str,
        tarefa_atual: str,
        projeto_novo: str,
        tarefa_novo: str,
    ) -> int:
        """
        Corrige projeto/tarefa em massa: atualiza todos os Apontamentos que
        usam o par atual e a entrada correspondente em ProjetoTarefa.

        Returns:
            Quantidade de apontamentos afetados.
        """
        projeto_novo = projeto_novo.strip()
        tarefa_novo = tarefa_novo.strip()

        with get_session() as s:
            apts = list(
                s.scalars(
                    select(Apontamento).where(
                        Apontamento.projeto == projeto_atual,
                        Apontamento.tarefa == tarefa_atual,
                    )
                ).all()
            )

            for apt in apts:
                if apt.projeto != projeto_novo:
                    self._registrar_audit(s, apt, "projeto", apt.projeto, projeto_novo)
                    apt.projeto = projeto_novo
                if apt.tarefa != tarefa_novo:
                    self._registrar_audit(s, apt, "tarefa", apt.tarefa, tarefa_novo)
                    apt.tarefa = tarefa_novo

            pt_atual = s.scalars(
                select(ProjetoTarefa).where(
                    ProjetoTarefa.projeto == projeto_atual,
                    ProjetoTarefa.tarefa == tarefa_atual,
                )
            ).first()
            pt_novo = s.scalars(
                select(ProjetoTarefa).where(
                    ProjetoTarefa.projeto == projeto_novo,
                    ProjetoTarefa.tarefa == tarefa_novo,
                )
            ).first()

            if pt_atual and pt_novo and pt_atual.id != pt_novo.id:
                s.delete(pt_atual)  # destino já existia — funde, descarta o antigo
            elif pt_atual and not pt_novo:
                pt_atual.projeto = projeto_novo
                pt_atual.tarefa = tarefa_novo
            elif not pt_atual and not pt_novo:
                s.add(
                    ProjetoTarefa(
                        projeto=projeto_novo,
                        tarefa=tarefa_novo,
                        ativo=True,
                        atualizado_em=datetime.now(),
                    )
                )

            logger.info(
                f"✏️ Renomeado em massa: '{projeto_atual}/{tarefa_atual}' → "
                f"'{projeto_novo}/{tarefa_novo}' ({len(apts)} apontamentos)"
            )
            return len(apts)

    def atualizar_ativo_projeto_tarefa(self, projeto: str, tarefa: str, ativo: bool) -> None:
        with get_session() as s:
            pt = s.scalars(
                select(ProjetoTarefa).where(
                    ProjetoTarefa.projeto == projeto,
                    ProjetoTarefa.tarefa == tarefa,
                )
            ).first()
            if pt:
                pt.ativo = ativo

    def deletar_projeto_tarefa(self, projeto: str, tarefa: str) -> bool:
        """Remove só da lista de sugestão (combos). Apontamentos já lançados não são afetados."""
        with get_session() as s:
            pt = s.scalars(
                select(ProjetoTarefa).where(
                    ProjetoTarefa.projeto == projeto,
                    ProjetoTarefa.tarefa == tarefa,
                )
            ).first()
            if not pt:
                return False
            s.delete(pt)
            logger.info(f"🗑 ProjetoTarefa removido: {projeto} / {tarefa}")
            return True

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _get_or_raise(self, s: Session, apontamento_id: int) -> Apontamento:
        apt = s.get(Apontamento, apontamento_id)
        if apt is None:
            raise ApontamentoError(f"Apontamento id={apontamento_id} não encontrado.")
        return apt

    def _assert_sem_ativo(self, s: Session) -> None:
        ativo = s.scalars(select(Apontamento).where(Apontamento.fim.is_(None))).first()
        if ativo is not None:
            raise ApontamentoAtivoError(
                f"Já há um apontamento em execução: {ativo.projeto} / {ativo.tarefa} "
                f"desde {ativo.inicio.strftime('%H:%M:%S')}."
            )

    def _assert_sem_sobreposicao(
        self,
        s: Session,
        inicio: datetime,
        fim: datetime | None,
        excluir_id: int | None,
    ) -> None:
        """
        Verifica se o intervalo [inicio, fim] conflita com algum apontamento existente.

        Um conflito ocorre quando dois intervalos se sobrepõem:
            inicio_A < fim_B  AND  fim_A > inicio_B

        Para apontamentos em execução (fim=None), verificamos apenas
        se o novo início está depois do início do ativo.
        """
        stmt = select(Apontamento).where(
            Apontamento.fim.is_not(None)  # só verifica finalizados
        )

        if excluir_id is not None:
            stmt = stmt.where(Apontamento.id != excluir_id)

        fim_para_check = fim or datetime.max

        # Sobreposição: os intervalos se cruzam se
        # novo_inicio < apt.fim  AND  novo_fim > apt.inicio
        stmt = stmt.where(
            and_(
                Apontamento.inicio < fim_para_check,
                Apontamento.fim > inicio,
            )
        )

        conflito = s.scalars(stmt).first()
        if conflito is not None:
            _ = conflito.projeto, conflito.tarefa, conflito.inicio, conflito.fim
            s.expunge(conflito)  # desanexa da sessão para sobreviver ao fechamento dela
            raise SobreposicaoError(conflito)

    def _apontamentos_do_dia(
        self,
        s: Session,
        dia: date,
        incluir_em_execucao: bool = True,
    ) -> list[Apontamento]:
        inicio_dia = datetime.combine(dia, datetime.min.time())
        fim_dia = datetime.combine(dia, datetime.max.time())

        stmt = (
            select(Apontamento)
            .where(Apontamento.inicio >= inicio_dia)
            .where(Apontamento.inicio <= fim_dia)
        )

        if not incluir_em_execucao:
            stmt = stmt.where(Apontamento.fim.is_not(None))

        stmt = stmt.order_by(Apontamento.inicio)
        return list(s.scalars(stmt).all())

    def _upsert_projeto_tarefa(self, s: Session, projeto: str, tarefa: str) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(ProjetoTarefa).values(
            projeto=projeto,
            tarefa=tarefa,
            ativo=True,
            atualizado_em=datetime.now(),
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["projeto", "tarefa"])
        s.execute(stmt)

    @staticmethod
    def _registrar_audit(
        s: Session,
        apt: Apontamento,
        campo: str,
        valor_anterior: str | None,
        valor_novo: str | None,
    ) -> None:
        if campo not in ApontamentoAudit.CAMPOS_VALIDOS:
            raise ValueError(f"Campo de auditoria inválido: {campo!r}")
        s.add(
            ApontamentoAudit(
                apontamento_id=apt.id,
                campo=campo,
                valor_anterior=valor_anterior,
                valor_novo=valor_novo,
            )
        )
