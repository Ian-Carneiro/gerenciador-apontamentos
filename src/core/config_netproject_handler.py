"""Gerenciador centralizado de Configurações NetProject - REFATORADO"""

import json
from pathlib import Path

import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigNetProjectHandler:
    """Gerenciador único de configurações NetProject e De/Para"""

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton - garante instância única"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializa apenas uma vez"""
        if not ConfigNetProjectHandler._initialized:
            self._projetos_netproject = {}
            self._depara_projetos = {}
            self._depara_tarefas = {}
            self._carregar_config()
            ConfigNetProjectHandler._initialized = True

    def _carregar_config(self):
        """Carrega configurações do JSON"""
        arquivo_config = config.DATA_DIR / "config_netproject.json"

        if not arquivo_config.exists():
            self._criar_arquivo_padrao(arquivo_config)

        try:
            with open(arquivo_config, encoding="utf-8") as f:
                dados = json.load(f)

                self._projetos_netproject = dados.get("projetos_netproject", {})
                depara = dados.get("depara", {})
                self._depara_projetos = depara.get("projetos", {})
                self._depara_tarefas = depara.get("tarefas", {})

            total_depara = len(self._depara_projetos) + len(self._depara_tarefas)
            logger.info(f"📋 {len(self._projetos_netproject)} projetos NetProject carregados")
            logger.info(f"📋 {total_depara} regras de de/para carregadas")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao parsear config_netproject.json: {e}")
            self._carregar_defaults()
        except Exception as e:
            logger.error(f"❌ Erro ao carregar config_netproject.json: {e}")
            self._carregar_defaults()

    def _carregar_defaults(self):
        """Carrega valores padrão em caso de erro"""
        self._projetos_netproject = {
            "desenvolvimento": 263718,
            "evolucao": 263719,
            "manutencao": 263717,
            "rotina": 263527,
            "escalabilidade_gov": 261699,
        }
        self._depara_projetos = {}
        self._depara_tarefas = {}

    def _criar_arquivo_padrao(self, arquivo: Path):
        """Cria arquivo de configuração padrão"""
        padrao = {
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

        try:
            with open(arquivo, "w", encoding="utf-8") as f:
                json.dump(padrao, f, indent=2, ensure_ascii=False)
            logger.info("📄 Criado config_netproject.json padrão")
        except OSError as e:
            logger.error(f"❌ Erro ao criar config_netproject.json: {e}")

    # Properties read-only com cópias defensivas
    @property
    def projetos_netproject(self) -> dict[str, int]:
        """Retorna cópia do dicionário de projetos NetProject"""
        return self._projetos_netproject.copy()

    @property
    def depara_projetos(self) -> dict[str, str]:
        """Retorna cópia do dicionário de/para de projetos"""
        return self._depara_projetos.copy()

    @property
    def depara_tarefas(self) -> dict[str, str]:
        """Retorna cópia do dicionário de/para de tarefas"""
        return self._depara_tarefas.copy()

    def aplicar_projeto(self, valor: str) -> str:
        """Aplica de/para em projeto (com cache)"""
        return self._depara_projetos.get(valor, valor)

    def aplicar_tarefa(self, valor: str) -> str:
        """Aplica de/para em tarefa (com cache)"""
        return self._depara_tarefas.get(valor, valor)

    def recarregar(self):
        """Recarrega configurações do arquivo"""
        self._carregar_config()

    def adicionar_projeto_netproject(self, nome: str, codigo: int):
        """Adiciona projeto NetProject (só em memória)"""
        self._projetos_netproject[nome] = codigo

    def remover_projeto_netproject(self, nome: str):
        """Remove projeto NetProject (só em memória)"""
        self._projetos_netproject.pop(nome, None)

    def adicionar_depara_projeto(self, de: str, para: str):
        """Adiciona regra de/para de projeto (só em memória)"""
        self._depara_projetos[de] = para

    def adicionar_depara_tarefa(self, de: str, para: str):
        """Adiciona regra de/para de tarefa (só em memória)"""
        self._depara_tarefas[de] = para

    def salvar(self) -> bool:
        """Salva alterações no arquivo JSON"""
        arquivo_config = config.DATA_DIR / "config_netproject.json"

        try:
            dados = {
                "projetos_netproject": self._projetos_netproject,
                "depara": {"projetos": self._depara_projetos, "tarefas": self._depara_tarefas},
            }

            with open(arquivo_config, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)

            logger.info("💾 Configurações salvas em config_netproject.json")
            return True
        except OSError as e:
            logger.error(f"❌ Erro ao salvar config_netproject.json: {e}")
            return False


# Instância global (singleton)
config_netproject = ConfigNetProjectHandler()

# Alias para compatibilidade
depara = config_netproject
