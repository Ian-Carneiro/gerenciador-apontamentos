"""
Testes unitários — ApontamentoService (Fase 2)
Roda com banco SQLite em memória, sem UI, sem PySide6.

    cd apontador_v5
    pytest tests/test_service.py -v
"""

from datetime import date, datetime, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.apontamento_service import (
    ApontamentoService,
    ItemFavorito,
)
from src.db.database import init_db, reset_engine_for_tests
from src.db.repository import (
    ApontamentoError,
    ApontamentoRepository,
    HorarioInvalidoError,
    SobreposicaoError,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def banco_em_memoria(tmp_path):
    db = tmp_path / "test.db"
    reset_engine_for_tests(db)
    init_db(db)
    yield


@pytest.fixture
def repo():
    return ApontamentoRepository()


@pytest.fixture
def svc(repo):
    return ApontamentoService(repo=repo)


_HOJE = date.today()
_ANO = _HOJE.year
_MES = _HOJE.month


def dt(
    h: int,
    m: int = 0,
    s: int = 0,
    dia: int | None = None,
    dias_atras: int = 0,
) -> datetime:
    """Helper: datetime relativo a hoje."""
    data = _HOJE - timedelta(days=dias_atras)

    if dia is not None:
        data = data.replace(day=dia)

    return datetime(data.year, data.month, data.day, h, m, s)


def hoje() -> date:
    return _HOJE


def dia_n(n: int) -> int:
    """Retorna um dia válido no mês atual (1-based offset a partir do dia 1)."""
    return n  # os testes usam dias 1-28, todos válidos em qualquer mês


# ── ResultadoIniciar.mensagem ─────────────────────────────────────────────────


class TestResultadoIniciarMensagem:
    def test_mensagem_iniciado(self, svc):
        res = svc.iniciar_ou_registrar("P", "T", agora=dt(9))
        assert "Iniciado" in res.mensagem or "▶️" in res.mensagem

    def test_mensagem_retroativo(self, svc):
        res = svc.iniciar_ou_registrar("P", "T", inicio=dt(9), fim=dt(11))
        assert "Registrado" in res.mensagem or "📝" in res.mensagem

    def test_mensagem_troca(self, svc):
        svc.iniciar_ou_registrar("P", "T1", agora=dt(9))
        res = svc.iniciar_ou_registrar("P", "T2", agora=dt(10))
        assert "T1" in res.mensagem
        assert "T2" in res.mensagem


# ── Cenário 1: Iniciar agora ──────────────────────────────────────────────────


class TestCenario1IniciarAgora:
    def test_inicio_sem_horario_usa_agora(self, svc):
        agora = dt(9)
        res = svc.iniciar_ou_registrar("Proj", "Tar", agora=agora)
        assert res.apontamento.inicio == agora
        assert res.apontamento.fim is None
        assert res.modo == "iniciado"

    def test_inicio_sem_horario_cria_ativo(self, svc):
        svc.iniciar_ou_registrar("Proj", "Tar", agora=dt(9))
        assert svc.obter_ativo() is not None

    def test_inicio_sem_horario_sem_projeto_falha(self, svc):
        with pytest.raises(ValueError):
            svc.iniciar_ou_registrar("", "Tar", agora=dt(9))


# ── Cenário 2: Iniciar em horário específico ──────────────────────────────────


class TestCenario2IniciarHorario:
    def test_inicio_com_horario_especifico(self, svc):
        res = svc.iniciar_ou_registrar("Proj", "Tar", inicio=dt(9), agora=dt(10))
        assert res.apontamento.inicio == dt(9)
        assert res.apontamento.fim is None
        assert res.modo == "iniciado"

    def test_inicio_especifico_no_passado(self, svc):
        # Deve funcionar: o usuário pode ter esquecido de iniciar às 8h
        res = svc.iniciar_ou_registrar("Proj", "Tar", inicio=dt(8), agora=dt(10))
        assert res.apontamento.inicio == dt(8)


# ── Cenário 3: Retroativo completo ───────────────────────────────────────────


class TestCenario3Retroativo:
    def test_retroativo_cria_finalizado(self, svc):
        res = svc.iniciar_ou_registrar("Proj", "Tar", inicio=dt(9), fim=dt(11))
        assert res.modo == "retroativo"
        assert res.apontamento.fim == dt(11)
        assert res.apontamento.horas == pytest.approx(2.0)

    def test_retroativo_nao_cria_ativo(self, svc):
        svc.iniciar_ou_registrar("Proj", "Tar", inicio=dt(9), fim=dt(11))
        assert svc.obter_ativo() is None

    def test_retroativo_preserva_nota(self, svc):
        res = svc.iniciar_ou_registrar("Proj", "Tar", inicio=dt(9), fim=dt(11), nota="minha nota")
        assert res.apontamento.nota == "minha nota"

    def test_retroativo_fim_antes_inicio_falha(self, svc):
        with pytest.raises(HorarioInvalidoError):
            svc.iniciar_ou_registrar("Proj", "Tar", inicio=dt(11), fim=dt(9))

    def test_retroativo_com_sobreposicao_propaga_erro(self, svc):
        svc.iniciar_ou_registrar("P", "T1", inicio=dt(9), fim=dt(11))
        with pytest.raises(SobreposicaoError) as exc_info:
            svc.iniciar_ou_registrar("P", "T2", inicio=dt(10), fim=dt(12))
        # O erro carrega o apontamento conflitante para a UI exibir
        assert exc_info.value.conflito is not None

    def test_retroativo_em_intervalo_livre(self, svc):
        """Caso solicitado: inserir entre dois apontamentos já existentes."""
        svc.iniciar_ou_registrar("P", "T1", inicio=dt(9), fim=dt(10))
        svc.iniciar_ou_registrar("P", "T2", inicio=dt(11), fim=dt(12))
        # Buraco 10h–11h: deve funcionar
        res = svc.iniciar_ou_registrar("P", "T3", inicio=dt(10), fim=dt(11))
        assert res.apontamento.horas == pytest.approx(1.0)

    def test_multiplos_retroativos_mesmo_dia(self, svc):
        svc.iniciar_ou_registrar("P", "T1", inicio=dt(9), fim=dt(10))
        svc.iniciar_ou_registrar("P", "T2", inicio=dt(10), fim=dt(11))
        svc.iniciar_ou_registrar("P", "T3", inicio=dt(11), fim=dt(12))
        total = svc._repo.total_horas_dia(hoje())
        assert total == pytest.approx(3.0)


# ── Cenário 5: Troca de tarefa ────────────────────────────────────────────────


class TestCenario5TrocaTarefa:
    def test_troca_para_atual_e_inicia_nova(self, svc):
        svc.iniciar_ou_registrar("Proj", "T1", agora=dt(9))
        res = svc.iniciar_ou_registrar("Proj", "T2", agora=dt(10))

        assert res.modo == "troca"
        assert res.anterior_parado is not None
        assert res.anterior_parado.tarefa == "T1"
        assert res.anterior_parado.fim == dt(10)
        assert res.apontamento.tarefa == "T2"
        assert res.apontamento.inicio == dt(10)
        assert res.apontamento.fim is None

    def test_troca_registra_horas_do_anterior(self, svc):
        svc.iniciar_ou_registrar("Proj", "T1", agora=dt(9))
        res = svc.iniciar_ou_registrar("Proj", "T2", agora=dt(10, 30))
        assert res.anterior_parado.horas == pytest.approx(1.5)

    def test_troca_apenas_um_ativo_apos(self, svc):
        svc.iniciar_ou_registrar("P", "T1", agora=dt(9))
        svc.iniciar_ou_registrar("P", "T2", agora=dt(10))
        svc.iniciar_ou_registrar("P", "T3", agora=dt(11))
        ativo = svc.obter_ativo()
        assert ativo is not None
        assert ativo.tarefa == "T3"

    def test_troca_preserva_nota_do_novo(self, svc):
        svc.iniciar_ou_registrar("P", "T1", agora=dt(9))
        res = svc.iniciar_ou_registrar("P", "T2", nota="nota nova", agora=dt(10))
        assert res.apontamento.nota == "nota nova"

    def test_troca_sequencia_longa(self, svc):
        """5 trocas consecutivas — só deve existir 1 ativo no final."""
        for i in range(1, 6):
            svc.iniciar_ou_registrar("P", f"T{i}", agora=dt(8 + i))
        ativo = svc.obter_ativo()
        assert ativo is not None
        assert ativo.tarefa == "T5"
        # As 4 anteriores devem estar finalizadas
        blocos = svc._repo.obter_blocos_historico()
        finalizados = [a for b in blocos for a in b.apontamentos if a.fim is not None]
        assert len(finalizados) == 4


# ── Parar ativo ───────────────────────────────────────────────────────────────


class TestPararAtivo:
    def test_parar_com_horario(self, svc):
        svc.iniciar_ou_registrar("P", "T", agora=dt(9))
        parado = svc.parar_ativo(fim=dt(11))
        assert parado.fim == dt(11)
        assert svc.obter_ativo() is None

    def test_parar_sem_horario_usa_agora(self, svc):
        svc.iniciar_ou_registrar("P", "T", agora=dt(9))
        agora = dt(11)
        parado = svc.parar_ativo(agora=agora)
        assert parado.fim == agora

    def test_parar_sem_ativo_falha(self, svc):
        with pytest.raises(ApontamentoError, match="Nenhum"):
            svc.parar_ativo(agora=dt(10))

    def test_parar_com_nota_final(self, svc):
        svc.iniciar_ou_registrar("P", "T", agora=dt(9))
        parado = svc.parar_ativo(fim=dt(11), nota="nota final")
        assert parado.nota == "nota final"


# ── Recuperar estado ──────────────────────────────────────────────────────────


class TestRecuperarEstado:
    def test_estado_inicial_vazio(self, svc):
        # Monkey-patch date.today para retornar dia fixo
        import src.core.apontamento_service as svc_mod

        orig = svc_mod.date

        class FakeDate(date):
            @classmethod
            def today(cls):
                return hoje()

        svc_mod.date = FakeDate
        try:
            estado = svc.recuperar_estado()
            assert estado.ativo is None
            assert estado.em_execucao is False
            assert estado.total_horas_hoje == 0.0
        finally:
            svc_mod.date = orig

    def test_estado_com_ativo(self, svc, repo):
        # Injeta diretamente no repo para controle total do datetime
        apt = repo.iniciar("P", "T", dt(9))

        import src.core.apontamento_service as svc_mod

        orig = svc_mod.date

        class FakeDate(date):
            @classmethod
            def today(cls):
                return hoje()

        svc_mod.date = FakeDate
        try:
            estado = svc.recuperar_estado()
            assert estado.em_execucao is True
            assert estado.ativo.id == apt.id
        finally:
            svc_mod.date = orig

    def test_total_hoje_str_formato(self, svc, repo):
        repo.registrar_retroativo("P", "T1", dt(9), dt(10, 30))
        repo.registrar_retroativo("P", "T2", dt(10, 30), dt(12))

        import src.core.apontamento_service as svc_mod

        orig = svc_mod.date

        class FakeDate(date):
            @classmethod
            def today(cls):
                return hoje()

        svc_mod.date = FakeDate
        try:
            estado = svc.recuperar_estado()
            assert estado.total_horas_hoje == pytest.approx(3.0)
            assert estado.total_hoje_str == "3h 00min"
        finally:
            svc_mod.date = orig


# ── Favoritos ─────────────────────────────────────────────────────────────────


class TestFavoritos:
    def test_sem_historico_retorna_vazio(self, svc):
        favoritos = svc.calcular_favoritos()
        assert favoritos == []

    def test_mais_usado_aparece_primeiro(self, svc, repo):
        # T1: 3 vezes em dias diferentes dentro do período
        dia_base = max(1, _HOJE.day - 10)
        for i in range(3):
            d = max(1, dia_base + i)
            repo.registrar_retroativo("P", "T1", dt(9, dia=d), dt(10, dia=d))
        # T2: 1 vez hoje
        repo.registrar_retroativo("P", "T2", dt(13), dt(14))

        favoritos = svc.calcular_favoritos(dias_historico=30)
        assert len(favoritos) >= 2
        assert favoritos[0].tarefa == "T1"

    def test_limite_max_itens(self, svc, repo):
        # 10 projetos/tarefas distintos, todos hoje em horários diferentes
        for i in range(10):
            repo.registrar_retroativo(f"P{i}", f"T{i}", dt(i, 0), dt(i, 30))

        favoritos = svc.calcular_favoritos(max_itens=3, dias_historico=30)
        assert len(favoritos) == 3

    def test_score_tem_bonus_recencia_hoje(self, svc, repo):
        # Apontamento de hoje deve ter score maior que de 5 dias atrás
        repo.registrar_retroativo("P", "T_hoje", dt(9), dt(10))
        repo.registrar_retroativo(
            "P",
            "T_antigo",
            dt(9, dias_atras=5),
            dt(10, dias_atras=5),
        )

        favoritos = svc.calcular_favoritos(dias_historico=30)
        labels = [f.tarefa for f in favoritos]

        assert labels[0] == "T_hoje"

    def test_item_favorito_label(self):
        item = ItemFavorito(projeto="Meu Projeto", tarefa="Minha Tarefa", score=1.0)
        assert item.label == "Meu Projeto  ›  Minha Tarefa"

    def test_item_favorito_horas_str(self):
        item = ItemFavorito(projeto="P", tarefa="T", score=1.0, total_horas=2.5)
        assert item.horas_str == "2h 30min"

    def test_em_execucao_nao_conta_para_favoritos(self, svc, repo):
        # Apontamento sem fim não deve ser contabilizado
        repo.registrar_retroativo("P", "T_fin", dt(7), dt(8))
        repo.iniciar("P", "T_ativa", dt(9))  # ativo — sem fim

        favoritos = svc.calcular_favoritos(dias_historico=30)
        tarefas = [f.tarefa for f in favoritos]
        assert "T_ativa" not in tarefas
        assert "T_fin" in tarefas


# ── Intervalos livres ─────────────────────────────────────────────────────────


class TestIntervalosLivres:
    def test_dia_vazio_retorna_dia_inteiro(self, svc):
        livres = svc.obter_intervalos_livres(hoje())
        assert len(livres) == 1
        assert livres[0][0].hour == 0

    def test_buraco_entre_apontamentos(self, svc, repo):
        repo.registrar_retroativo("P", "T1", dt(9), dt(10))
        repo.registrar_retroativo("P", "T2", dt(11), dt(12))
        livres = svc.obter_intervalos_livres(hoje())
        # Deve incluir o buraco 10h–11h
        buracos_inicio = [iv[0].hour for iv in livres]
        assert 10 in buracos_inicio

    def test_sem_buraco_entre_adjacentes(self, svc, repo):
        repo.registrar_retroativo("P", "T1", dt(9), dt(10))
        repo.registrar_retroativo("P", "T2", dt(10), dt(11))
        livres = svc.obter_intervalos_livres(hoje())
        # Não deve ter buraco entre 10h e 10h
        buracos_inicio = [iv[0].hour for iv in livres]
        assert 10 not in buracos_inicio


# ── Delegações ao Repository ──────────────────────────────────────────────────


class TestDelegacoes:
    def test_dividir_via_service(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(12))
        p1, p2 = svc.dividir(apt.id, dt(10, 30))
        assert p1.fim == dt(10, 30)
        assert p2.inicio == dt(10, 30)

    def test_atualizar_projeto_tarefa_via_service(self, svc, repo):
        apt = repo.registrar_retroativo("Antigo", "T", dt(9), dt(11))
        apt = svc.atualizar_projeto_tarefa(apt.id, "Novo", "T")
        assert apt.projeto == "Novo"

    def test_ajustar_inicio_via_service(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        apt = svc.ajustar_inicio(apt.id, dt(8, 30))
        assert apt.inicio == dt(8, 30)

    def test_ajustar_fim_via_service(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        apt = svc.ajustar_fim(apt.id, dt(12))
        assert apt.fim == dt(12)

    def test_ajustar_inicio_via_service_repassa_ignorar_sobreposicao(self, svc, repo):
        repo.registrar_retroativo("P", "T1", dt(7), dt(9))
        apt = repo.registrar_retroativo("P", "T2", dt(10), dt(12))
        apt = svc.ajustar_inicio(apt.id, dt(8), ignorar_sobreposicao=True)
        assert apt.inicio == dt(8)

    def test_ajustar_fim_via_service_repassa_ignorar_sobreposicao(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T1", dt(7), dt(9))
        repo.registrar_retroativo("P", "T2", dt(10), dt(12))
        apt = svc.ajustar_fim(apt.id, dt(11), ignorar_sobreposicao=True)
        assert apt.fim == dt(11)

    def test_deletar_via_service(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        assert svc.deletar(apt.id) is True
        assert repo.obter_por_id(apt.id) is None

    def test_atualizar_nota_via_service(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        svc.atualizar_nota(apt.id, "nova nota")
        atualizado = repo.obter_por_id(apt.id)
        assert atualizado.nota == "nova nota"

    def test_listar_projetos_tarefas_via_service(self, svc, repo):
        repo.sincronizar_projetos_tarefas(
            [
                {"projeto": "P1", "tarefa": "T1", "ativo": True},
                {"projeto": "P2", "tarefa": "T2", "ativo": False},
            ]
        )
        ativos = svc.listar_projetos_tarefas()
        assert len(ativos) == 1
        assert ativos[0].projeto == "P1"

    def test_historico_audit_via_service(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        svc.ajustar_inicio(apt.id, dt(8))
        audits = svc.obter_historico_audit(apt.id)
        assert any(a.campo == "inicio" for a in audits)


# ── slide_adjacentes ──────────────────────────────────────────────────────────


class TestSlideAdjacentes:
    """Regras de ApontamentoService.slide_adjacentes."""

    def test_desloca_proximo_para_tras_mantendo_contiguidade(self, svc, repo):
        apt1 = repo.registrar_retroativo("P", "T1", dt(16), dt(17))
        apt2 = repo.registrar_retroativo("P", "T2", dt(17), dt(18, 21))

        delta_fim = dt(15, 4) - apt1.fim  # -1h56min
        svc.slide_adjacentes(apt1, delta_fim=delta_fim)

        prox = repo.obter_por_id(apt2.id)
        assert prox.inicio == dt(15, 4)
        assert prox.fim == dt(16, 25)

    def test_desloca_proximo_para_frente(self, svc, repo):
        apt1 = repo.registrar_retroativo("P", "T1", dt(9), dt(10))
        apt2 = repo.registrar_retroativo("P", "T2", dt(10), dt(11))

        delta_fim = dt(10, 30) - apt1.fim  # +30min
        svc.slide_adjacentes(apt1, delta_fim=delta_fim)

        prox = repo.obter_por_id(apt2.id)
        assert prox.inicio == dt(10, 30)
        assert prox.fim == dt(11, 30)

    def test_desloca_anterior_ao_mudar_inicio(self, svc, repo):
        apt1 = repo.registrar_retroativo("P", "T1", dt(9), dt(10))
        apt2 = repo.registrar_retroativo("P", "T2", dt(10), dt(11))

        delta_ini = dt(10, 20) - apt2.inicio  # +20min
        svc.slide_adjacentes(apt2, delta_ini=delta_ini)

        anterior = repo.obter_por_id(apt1.id)
        assert anterior.fim == dt(10, 20)

    def test_sem_vizinho_nao_faz_nada(self, svc, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(10))
        svc.slide_adjacentes(apt, delta_ini=timedelta(minutes=-10), delta_fim=timedelta(minutes=10))
        atual = repo.obter_por_id(apt.id)
        assert atual.inicio == dt(9)
        assert atual.fim == dt(10)

    def test_desloca_proximo_em_execucao_ajusta_so_inicio(self, svc, repo):
        """Próximo sem fim (em execução): só o início dele se move."""
        apt1 = repo.registrar_retroativo("P", "T1", dt(9), dt(10))
        ativo = repo.iniciar("P", "T2", dt(10))

        svc.slide_adjacentes(apt1, delta_fim=timedelta(minutes=-15))

        prox = repo.obter_por_id(ativo.id)
        assert prox.inicio == dt(9, 45)
        assert prox.fim is None


# ── Fluxo AjustarHorarioDialog (regressão) ──────────────────────────────────


class TestFluxoAjusteHorarioComVizinho:
    """
    Reproduz slide_adjacentes() + ajustar_inicio()/ajustar_fim() como o
    AjustarHorarioDialog._salvar() faz. Cobre os dois bugs corrigidos:
    ordem de ajuste do vizinho e sobreposição temporária do próprio registro.
    """

    def test_encolher_inicio_e_fim_com_vizinho_seguinte_adjacente(self, svc, repo):
        repo.registrar_retroativo("P", "Anterior", dt(13), dt(16))
        alvo = repo.registrar_retroativo("P", "Alvo", dt(16), dt(17))
        vizinho = repo.registrar_retroativo("P", "Vizinho", dt(17), dt(18, 21))

        novo_inicio, novo_fim = dt(13, 45), dt(15, 4)
        delta_ini = novo_inicio - alvo.inicio
        delta_fim = novo_fim - alvo.fim

        svc.slide_adjacentes(alvo, delta_ini=delta_ini, delta_fim=delta_fim)
        svc.ajustar_inicio(alvo.id, novo_inicio, ignorar_sobreposicao=bool(delta_fim))
        svc.ajustar_fim(alvo.id, novo_fim)

        alvo_final = repo.obter_por_id(alvo.id)
        vizinho_final = repo.obter_por_id(vizinho.id)
        assert alvo_final.inicio == dt(13, 45)
        assert alvo_final.fim == dt(15, 4)
        assert vizinho_final.inicio == dt(15, 4)
        assert vizinho_final.fim == dt(16, 25)

    def test_expandir_fim_com_vizinho_seguinte_adjacente(self, svc, repo):
        alvo = repo.registrar_retroativo("P", "Alvo", dt(9), dt(10))
        vizinho = repo.registrar_retroativo("P", "Vizinho", dt(10), dt(11))

        novo_fim = dt(10, 30)
        svc.slide_adjacentes(alvo, delta_fim=novo_fim - alvo.fim)
        svc.ajustar_fim(alvo.id, novo_fim)

        vizinho_final = repo.obter_por_id(vizinho.id)
        assert vizinho_final.inicio == dt(10, 30)
        assert vizinho_final.fim == dt(11, 30)

    def test_recuar_inicio_com_vizinho_anterior_nao_precisa_ignorar_sobreposicao(self, svc, repo):
        """Quando só o início muda, o anterior já fica exatamente encostado — sem flag."""
        anterior = repo.registrar_retroativo("P", "Anterior", dt(8), dt(9))
        alvo = repo.registrar_retroativo("P", "Alvo", dt(9), dt(10))

        novo_inicio = dt(8, 30)
        svc.slide_adjacentes(alvo, delta_ini=novo_inicio - alvo.inicio)
        svc.ajustar_inicio(alvo.id, novo_inicio)  # sem ignorar_sobreposicao

        anterior_final = repo.obter_por_id(anterior.id)
        assert anterior_final.fim == dt(8, 30)


# ── Fluxo completo dia de trabalho ────────────────────────────────────────────


class TestFluxoCompleto:
    def test_dia_completo_com_trocas_e_retroativo(self, svc, repo):
        """
        Simula um dia real:
        08:00 retroativo (esqueceu de iniciar)
        09:00 inicia T1
        10:30 troca para T2
        12:00 para para almoço
        13:00 inicia T3
        17:00 para
        """
        # Retroativo que esqueceu
        svc.iniciar_ou_registrar("P", "Reunião", inicio=dt(8), fim=dt(9))

        # T1 → T2 → parar
        svc.iniciar_ou_registrar("P", "T1", agora=dt(9))
        svc.iniciar_ou_registrar("P", "T2", agora=dt(10, 30))
        svc.parar_ativo(fim=dt(12))

        # T3
        svc.iniciar_ou_registrar("P", "T3", inicio=dt(13))
        svc.parar_ativo(fim=dt(17))

        apts = repo.obter_por_dia(hoje())
        finalizados = [a for a in apts if a.fim is not None]
        # Reunião(08-09) + T1(09-10:30) + T2(10:30-12) + T3(13-17) = 4
        assert len(finalizados) == 4

        total = repo.total_horas_dia(hoje())
        # 1h (reunião) + 1.5h (T1) + 1.5h (T2) + 4h (T3) = 8h
        assert total == pytest.approx(8.0)

    def test_retroativo_em_buraco_apos_dia_preenchido(self, svc, repo):
        """
        09–10h e 11–12h registrados. Usuário lembra que fez algo 10–11h.
        """
        svc.iniciar_ou_registrar("P", "T1", inicio=dt(9), fim=dt(10))
        svc.iniciar_ou_registrar("P", "T2", inicio=dt(11), fim=dt(12))

        livres = svc.obter_intervalos_livres(hoje())
        buraco = next((iv for iv in livres if iv[0].hour == 10), None)
        assert buraco is not None

        svc.iniciar_ou_registrar(
            "P",
            "T_esquecida",
            inicio=buraco[0],
            fim=buraco[1],
        )
        total = repo.total_horas_dia(hoje())
        assert total == pytest.approx(3.0)
