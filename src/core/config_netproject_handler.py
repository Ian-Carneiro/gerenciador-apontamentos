"""Gerenciador centralizado de Configurações NetProject."""

import json

import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

_ARQUIVO = config.DATA_DIR / "config_netproject.json"

_PADRAO = {
    "projetos_netproject": {
        "desenvolvimento": 263718,
        "evolucao": 263719,
        "manutencao": 263717,
        "rotina": 263527,
        "escalabilidade_gov": 261699,
    },
    "depara": {
        "projetos": {
            "16543D - ES5 -  Desenvolvimento de Produto": "16543D - ES5 - Desenvolvimento de Produto"
        },
        "tarefas": {},
    },
}


class ConfigNetProjectHandler:
    """Singleton — use os métodos de classe, não instancie. Sem efeito colateral no import."""

    _projetos_netproject: dict[str, int] | None = None
    _depara_projetos: dict[str, str] | None = None
    _depara_tarefas: dict[str, str] | None = None

    @classmethod
    def _garantir_carregado(cls):
        """Carrega do arquivo (ou padrão) na primeira chamada de qualquer método público; idempotente."""
        if cls._projetos_netproject is None:
            cls._carregar_config()

    @classmethod
    def _carregar_config(cls):
        """Carrega configurações do JSON, criando o arquivo padrão se ele não existir."""
        if not _ARQUIVO.exists():
            cls._criar_arquivo_padrao()

        try:
            dados = json.loads(_ARQUIVO.read_text(encoding="utf-8"))
            cls._projetos_netproject = dados.get("projetos_netproject", {})
            depara = dados.get("depara", {})
            cls._depara_projetos = depara.get("projetos", {})
            cls._depara_tarefas = depara.get("tarefas", {})

            total_depara = len(cls._depara_projetos) + len(cls._depara_tarefas)
            logger.info(f"📋 {len(cls._projetos_netproject)} projetos NetProject carregados")
            logger.info(f"📋 {total_depara} regras de de/para carregadas")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao parsear config_netproject.json: {e}")
            cls._carregar_defaults()
        except OSError as e:
            logger.error(f"❌ Erro ao carregar config_netproject.json: {e}")
            cls._carregar_defaults()

    @classmethod
    def _carregar_defaults(cls):
        """Carrega valores padrão em caso de erro de leitura/parse do arquivo."""
        cls._projetos_netproject = dict(_PADRAO["projetos_netproject"])
        cls._depara_projetos = {}
        cls._depara_tarefas = {}

    @classmethod
    def _criar_arquivo_padrao(cls):
        """Cria o arquivo de configuração padrão em disco."""
        try:
            _ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
            _ARQUIVO.write_text(json.dumps(_PADRAO, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("📄 Criado config_netproject.json padrão")
        except OSError as e:
            logger.error(f"❌ Erro ao criar config_netproject.json: {e}")

    # Getters read-only com cópias defensivas
    @classmethod
    def projetos_netproject(cls) -> dict[str, int]:
        """Retorna cópia do dicionário de projetos NetProject."""
        cls._garantir_carregado()
        return dict(cls._projetos_netproject)

    @classmethod
    def depara_projetos(cls) -> dict[str, str]:
        """Retorna cópia do dicionário de/para de projetos."""
        cls._garantir_carregado()
        return dict(cls._depara_projetos)

    @classmethod
    def depara_tarefas(cls) -> dict[str, str]:
        """Retorna cópia do dicionário de/para de tarefas."""
        cls._garantir_carregado()
        return dict(cls._depara_tarefas)

    @classmethod
    def aplicar_projeto(cls, valor: str) -> str:
        """Aplica a regra de/para em projeto, se houver; senão retorna o valor original."""
        cls._garantir_carregado()
        return cls._depara_projetos.get(valor, valor)

    @classmethod
    def aplicar_tarefa(cls, valor: str) -> str:
        """Aplica a regra de/para em tarefa, se houver; senão retorna o valor original."""
        cls._garantir_carregado()
        return cls._depara_tarefas.get(valor, valor)

    @classmethod
    def recarregar(cls):
        """Recarrega configurações do arquivo."""
        cls._carregar_config()

    @classmethod
    def adicionar_projeto_netproject(cls, nome: str, codigo: int):
        """Adiciona projeto NetProject (só em memória; chame salvar() para persistir)."""
        cls._garantir_carregado()
        cls._projetos_netproject[nome] = codigo

    @classmethod
    def remover_projeto_netproject(cls, nome: str):
        """Remove projeto NetProject (só em memória; chame salvar() para persistir)."""
        cls._garantir_carregado()
        cls._projetos_netproject.pop(nome, None)

    @classmethod
    def adicionar_depara_projeto(cls, de: str, para: str):
        """Adiciona regra de/para de projeto (só em memória; chame salvar() para persistir)."""
        cls._garantir_carregado()
        cls._depara_projetos[de] = para

    @classmethod
    def adicionar_depara_tarefa(cls, de: str, para: str):
        """Adiciona regra de/para de tarefa (só em memória; chame salvar() para persistir)."""
        cls._garantir_carregado()
        cls._depara_tarefas[de] = para

    @classmethod
    def salvar(cls) -> bool:
        """Salva o estado em memória (projetos + de/para) no arquivo JSON."""
        cls._garantir_carregado()
        try:
            dados = {
                "projetos_netproject": cls._projetos_netproject,
                "depara": {"projetos": cls._depara_projetos, "tarefas": cls._depara_tarefas},
            }
            _ARQUIVO.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("💾 Configurações salvas em config_netproject.json")
            return True
        except OSError as e:
            logger.error(f"❌ Erro ao salvar config_netproject.json: {e}")
            return False

    @classmethod
    def reset_for_tests(cls):
        """Zera o cache em memória — força recarregar do arquivo na próxima chamada. Uso só em testes."""
        cls._projetos_netproject = None
        cls._depara_projetos = None
        cls._depara_tarefas = None


# Referência de classe (não instância) — mantém `config_netproject.metodo(...)` funcionando
# nos consumidores existentes, mas sem nenhum I/O no momento do import.
config_netproject = ConfigNetProjectHandler

# Alias para compatibilidade
depara = config_netproject
