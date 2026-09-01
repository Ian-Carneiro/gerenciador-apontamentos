# -*- coding: utf-8 -*-
"""
Testes unitários — ApontamentoRepository (Fase 1)
Roda com banco SQLite em memória, sem UI, sem PySide6.

    cd apontador_v5
    pip install sqlalchemy pytest
    pytest tests/test_repository.py -v
"""
import pytest
from datetime import datetime, date, timedelta
from pathlib import Path

# Bootstrap: aponta para banco em memória antes de importar qualquer módulo db
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.database import init_db, reset_engine_for_tests
from src.db.repository import (
    ApontamentoRepository,
    ApontamentoAtivoError,
    ApontamentoError,
    HorarioInvalidoError,
    SobreposicaoError,
)
from src.db.models import Apontamento


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def banco_em_memoria(tmp_path):
    """Reinicia o banco para cada teste usando arquivo temporário."""
    db = tmp_path / "test.db"
    reset_engine_for_tests(db)
    init_db(db)
    yield


@pytest.fixture
def repo():
    return ApontamentoRepository()


def dt(h: int, m: int = 0, s: int = 0, dia: int = 25) -> datetime:
    """Helper: datetime rápido no dia 2025-08-25."""
    return datetime(2025, 8, dia, h, m, s)


def hoje() -> date:
    return date(2025, 8, 25)


# ── Iniciar / Parar ───────────────────────────────────────────────────────────

class TestIniciarParar:

    def test_iniciar_basico(self, repo):
        apt = repo.iniciar("Projeto A", "Tarefa 1", dt(9))
        assert apt.id is not None
        assert apt.projeto == "Projeto A"
        assert apt.fim is None
        assert apt.em_execucao is True

    def test_iniciar_dois_ao_mesmo_tempo_falha(self, repo):
        repo.iniciar("Projeto A", "Tarefa 1", dt(9))
        with pytest.raises(ApontamentoAtivoError):
            repo.iniciar("Projeto B", "Tarefa 2", dt(10))

    def test_parar_basico(self, repo):
        apt = repo.iniciar("Projeto A", "Tarefa 1", dt(9))
        apt = repo.parar(apt.id, dt(11))
        assert apt.fim == dt(11)
        assert apt.horas == pytest.approx(2.0)

    def test_parar_fim_antes_inicio_falha(self, repo):
        apt = repo.iniciar("Projeto A", "Tarefa 1", dt(9))
        with pytest.raises(HorarioInvalidoError):
            repo.parar(apt.id, dt(8))

    def test_parar_ja_finalizado_falha(self, repo):
        apt = repo.iniciar("Projeto A", "Tarefa 1", dt(9))
        repo.parar(apt.id, dt(11))
        with pytest.raises(ApontamentoError):
            repo.parar(apt.id, dt(12))

    def test_obter_ativo_retorna_none_quando_vazio(self, repo):
        assert repo.obter_ativo() is None

    def test_obter_ativo_retorna_apontamento_em_execucao(self, repo):
        apt = repo.iniciar("Projeto A", "Tarefa 1", dt(9))
        ativo = repo.obter_ativo()
        assert ativo is not None
        assert ativo.id == apt.id

    def test_horas_calculadas_corretamente(self, repo):
        apt = repo.iniciar("Proj", "Tar", dt(9, 0))
        apt = repo.parar(apt.id, dt(10, 30))
        assert apt.horas == pytest.approx(1.5)

    def test_duracao_str(self, repo):
        apt = repo.iniciar("Proj", "Tar", dt(9))
        apt = repo.parar(apt.id, dt(11, 30))
        assert apt.duracao_str == "2h 30min"


# ── Retroativo ────────────────────────────────────────────────────────────────

class TestRetroativo:

    def test_retroativo_basico(self, repo):
        apt = repo.registrar_retroativo("Proj A", "Tar 1", dt(9), dt(11))
        assert apt.fim == dt(11)
        assert apt.horas == pytest.approx(2.0)
        assert apt.parada is True

    def test_retroativo_fim_antes_inicio_falha(self, repo):
        with pytest.raises(HorarioInvalidoError):
            repo.registrar_retroativo("Proj", "Tar", dt(11), dt(9))

    def test_retroativo_sem_sobreposicao_em_intervalo_livre(self, repo):
        """Cenário real: há apontamento 09-10h e 11-12h. Inserir 10-11h deve funcionar."""
        repo.registrar_retroativo("Proj A", "Tar 1", dt(9), dt(10))
        repo.registrar_retroativo("Proj A", "Tar 2", dt(11), dt(12))
        # Intervalo livre 10-11h
        apt = repo.registrar_retroativo("Proj B", "Tar 3", dt(10), dt(11))
        assert apt.horas == pytest.approx(1.0)

    def test_retroativo_com_sobreposicao_falha(self, repo):
        repo.registrar_retroativo("Proj A", "Tar 1", dt(9), dt(11))
        with pytest.raises(SobreposicaoError):
            repo.registrar_retroativo("Proj B", "Tar 2", dt(10), dt(12))

    def test_retroativo_sobrepondo_inicio_de_outro_falha(self, repo):
        repo.registrar_retroativo("Proj A", "Tar 1", dt(10), dt(12))
        with pytest.raises(SobreposicaoError):
            repo.registrar_retroativo("Proj B", "Tar 2", dt(9), dt(11))

    def test_retroativo_exatamente_adjacente_funciona(self, repo):
        """10:00→11:00 e depois 11:00→12:00 — adjacentes, sem sobreposição."""
        repo.registrar_retroativo("Proj A", "Tar 1", dt(10), dt(11))
        apt = repo.registrar_retroativo("Proj B", "Tar 2", dt(11), dt(12))
        assert apt.horas == pytest.approx(1.0)

    def test_obter_intervalos_livres_dia_vazio(self, repo):
        livres = repo.obter_intervalos_livres(hoje())
        assert len(livres) == 1
        assert livres[0][0].hour == 0  # começa meia-noite

    def test_obter_intervalos_livres_com_apontamentos(self, repo):
        repo.registrar_retroativo("P", "T", dt(9), dt(10))
        repo.registrar_retroativo("P", "T", dt(11), dt(12))
        livres = repo.obter_intervalos_livres(hoje())
        # Deve ter: 00:00-09:00, 10:00-11:00, 12:00-23:59
        horarios_inicio = [l[0].hour for l in livres]
        assert 10 in horarios_inicio  # buraco entre 10h e 11h


# ── Dividir ───────────────────────────────────────────────────────────────────

class TestDividir:

    def test_dividir_basico(self, repo):
        apt = repo.registrar_retroativo("Proj", "Tar", dt(9), dt(12))
        p1, p2 = repo.dividir(apt.id, dt(10, 30))

        assert p1.inicio == dt(9)
        assert p1.fim    == dt(10, 30)
        assert p2.inicio == dt(10, 30)
        assert p2.fim    == dt(12)

    def test_dividir_preserva_projeto_e_tarefa(self, repo):
        apt = repo.registrar_retroativo("Meu Projeto", "Minha Tarefa", dt(9), dt(12))
        p1, p2 = repo.dividir(apt.id, dt(10))
        assert p1.projeto == "Meu Projeto"
        assert p2.tarefa  == "Minha Tarefa"

    def test_dividir_preserva_nota(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(12), nota="minha nota")
        p1, p2 = repo.dividir(apt.id, dt(10))
        assert p1.nota == "minha nota"
        assert p2.nota == "minha nota"

    def test_dividir_corte_fora_do_intervalo_falha(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(12))
        with pytest.raises(HorarioInvalidoError):
            repo.dividir(apt.id, dt(13))  # depois do fim

    def test_dividir_corte_igual_ao_inicio_falha(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(12))
        with pytest.raises(HorarioInvalidoError):
            repo.dividir(apt.id, dt(9))

    def test_dividir_em_execucao_falha(self, repo):
        apt = repo.iniciar("P", "T", dt(9))
        with pytest.raises(ApontamentoError):
            repo.dividir(apt.id, dt(10))

    def test_dividir_horas_somam_ao_original(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(12))
        horas_original = apt.horas
        p1, p2 = repo.dividir(apt.id, dt(10, 30))
        assert (p1.horas + p2.horas) == pytest.approx(horas_original)

    def test_dividir_registra_auditoria(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(12))
        repo.dividir(apt.id, dt(10))
        audits = repo.obter_historico_audit(apt.id)
        campos = [a.campo for a in audits]
        assert "fim" in campos


# ── Edição ────────────────────────────────────────────────────────────────────

class TestEdicao:

    def test_atualizar_projeto_tarefa(self, repo):
        apt = repo.registrar_retroativo("Antigo", "Tarefa Antiga", dt(9), dt(11))
        apt = repo.atualizar_projeto_tarefa(apt.id, "Novo Projeto", "Nova Tarefa")
        assert apt.projeto == "Novo Projeto"
        assert apt.tarefa  == "Nova Tarefa"

    def test_atualizar_projeto_registra_auditoria(self, repo):
        apt = repo.registrar_retroativo("Antigo", "T", dt(9), dt(11))
        repo.atualizar_projeto_tarefa(apt.id, "Novo", "T")
        audits = repo.obter_historico_audit(apt.id)
        assert any(a.campo == "projeto" and a.valor_anterior == "Antigo" for a in audits)

    def test_ajustar_inicio(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        apt = repo.ajustar_inicio(apt.id, dt(8, 30))
        assert apt.inicio == dt(8, 30)
        assert apt.horas == pytest.approx(2.5)

    def test_ajustar_inicio_apos_fim_falha(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        with pytest.raises(HorarioInvalidoError):
            repo.ajustar_inicio(apt.id, dt(12))

    def test_ajustar_inicio_sobreposicao_falha(self, repo):
        repo.registrar_retroativo("P", "T1", dt(7), dt(9))
        apt = repo.registrar_retroativo("P", "T2", dt(10), dt(12))
        with pytest.raises(SobreposicaoError):
            repo.ajustar_inicio(apt.id, dt(8))  # entraria em cima do T1

    def test_ajustar_fim(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        apt = repo.ajustar_fim(apt.id, dt(12))
        assert apt.fim == dt(12)

    def test_ajustar_fim_antes_inicio_falha(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        with pytest.raises(HorarioInvalidoError):
            repo.ajustar_fim(apt.id, dt(8))

    def test_deletar(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        assert repo.deletar(apt.id) is True
        assert repo.obter_por_id(apt.id) is None

    def test_deletar_nao_encontrado_retorna_false(self, repo):
        assert repo.deletar(9999) is False


class TestAjusteIgnorandoSobreposicao:
    """Regras do parâmetro ignorar_sobreposicao em ajustar_inicio/ajustar_fim."""

    def test_ajustar_inicio_ignorando_sobreposicao_permite_conflito(self, repo):
        repo.registrar_retroativo("P", "T1", dt(7), dt(9))
        apt = repo.registrar_retroativo("P", "T2", dt(10), dt(12))
        apt = repo.ajustar_inicio(apt.id, dt(8), ignorar_sobreposicao=True)
        assert apt.inicio == dt(8)

    def test_ajustar_fim_ignorando_sobreposicao_permite_conflito(self, repo):
        apt = repo.registrar_retroativo("P", "T1", dt(7), dt(9))
        repo.registrar_retroativo("P", "T2", dt(10), dt(12))
        apt = repo.ajustar_fim(apt.id, dt(11), ignorar_sobreposicao=True)
        assert apt.fim == dt(11)

    def test_ajustar_inicio_ignorando_sobreposicao_ainda_valida_horario(self, repo):
        """ignorar_sobreposicao pula só o conflito com outros registros, não fim > início."""
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        with pytest.raises(HorarioInvalidoError):
            repo.ajustar_inicio(apt.id, dt(12), ignorar_sobreposicao=True)

    def test_ajustar_fim_ignorando_sobreposicao_ainda_valida_horario(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        with pytest.raises(HorarioInvalidoError):
            repo.ajustar_fim(apt.id, dt(8), ignorar_sobreposicao=True)

    def test_ajustar_fim_tocando_inicio_de_outro_nao_e_sobreposicao(self, repo):
        """Fronteira exata (toque) nunca é sobreposição, mesmo sem a flag."""
        apt = repo.registrar_retroativo("P", "T1", dt(9), dt(10))
        repo.registrar_retroativo("P", "T2", dt(11), dt(12))
        apt = repo.ajustar_fim(apt.id, dt(11))
        assert apt.fim == dt(11)


# ── Consultas ─────────────────────────────────────────────────────────────────

class TestConsultas:

    def test_obter_por_dia(self, repo):
        repo.registrar_retroativo("P", "T1", dt(9, dia=25), dt(10, dia=25))
        repo.registrar_retroativo("P", "T2", dt(9, dia=26), dt(10, dia=26))
        apts = repo.obter_por_dia(date(2025, 8, 25))
        assert len(apts) == 1
        assert apts[0].tarefa == "T1"

    def test_blocos_historico_agrupa_por_dia(self, repo):
        repo.registrar_retroativo("P", "T1", dt(9, dia=25), dt(10, dia=25))
        repo.registrar_retroativo("P", "T2", dt(11, dia=25), dt(12, dia=25))
        repo.registrar_retroativo("P", "T3", dt(9, dia=26), dt(10, dia=26))
        blocos = repo.obter_blocos_historico()
        assert len(blocos) == 2
        assert len(blocos[0].apontamentos) == 1  # dia 26 (mais recente primeiro)
        assert len(blocos[1].apontamentos) == 2  # dia 25

    def test_total_horas_dia(self, repo):
        repo.registrar_retroativo("P", "T1", dt(9), dt(11))
        repo.registrar_retroativo("P", "T2", dt(11), dt(12, 30))
        total = repo.total_horas_dia(hoje())
        assert total == pytest.approx(3.5)

    def test_buscar_por_texto(self, repo):
        repo.registrar_retroativo("Projeto Alpha", "Tarefa X", dt(9), dt(10))
        repo.registrar_retroativo("Projeto Beta",  "Tarefa Y", dt(10), dt(11))
        resultados = repo.buscar(texto="alpha")
        assert len(resultados) == 1
        assert resultados[0].projeto == "Projeto Alpha"

    def test_buscar_sem_filtros_retorna_tudo(self, repo):
        repo.registrar_retroativo("P1", "T1", dt(9), dt(10))
        repo.registrar_retroativo("P2", "T2", dt(10), dt(11))
        assert len(repo.buscar()) == 2


# ── Auditoria ─────────────────────────────────────────────────────────────────

class TestAuditoria:

    def test_parar_registra_auditoria_fim(self, repo):
        apt = repo.iniciar("P", "T", dt(9))
        repo.parar(apt.id, dt(11))
        audits = repo.obter_historico_audit(apt.id)
        assert any(a.campo == "fim" for a in audits)

    def test_multiplas_edicoes_geram_multiplas_auditorias(self, repo):
        apt = repo.registrar_retroativo("P", "T", dt(9), dt(11))
        repo.ajustar_inicio(apt.id, dt(8, 30))
        repo.ajustar_fim(apt.id, dt(12))
        repo.atualizar_nota(apt.id, "nota nova")
        audits = repo.obter_historico_audit(apt.id)
        campos = {a.campo for a in audits}
        assert {"inicio", "fim", "nota"} == campos


# ── Projetos/Tarefas ──────────────────────────────────────────────────────────

class TestProjetosTarefas:

    def test_sincronizar_e_listar(self, repo):
        dados = [
            {"projeto": "Proj A", "tarefa": "Tar 1", "ativo": True},
            {"projeto": "Proj A", "tarefa": "Tar 2", "ativo": True},
            {"projeto": "Proj B", "tarefa": "Tar 3", "ativo": False},
        ]
        count = repo.sincronizar_projetos_tarefas(dados)
        assert count == 3

        ativos = repo.listar_projetos_tarefas(apenas_ativos=True)
        assert len(ativos) == 2

        todos = repo.listar_projetos_tarefas(apenas_ativos=False)
        assert len(todos) == 3

    def test_sincronizar_upsert(self, repo):
        """Segunda sincronização deve atualizar, não duplicar."""
        dados = [{"projeto": "P", "tarefa": "T", "ativo": True}]
        repo.sincronizar_projetos_tarefas(dados)
        repo.sincronizar_projetos_tarefas(dados)  # segunda vez
        todos = repo.listar_projetos_tarefas(apenas_ativos=False)
        assert len(todos) == 1