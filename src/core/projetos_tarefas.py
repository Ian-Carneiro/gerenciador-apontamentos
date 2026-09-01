"""Gerenciador de Projetos e Tarefas - Com messageboxes"""

import os
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

import config
from src.core.config_netproject_handler import config_netproject
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://synchro.netproject.com.br//index.php?func=download_mpx&cod_projeto={codigo}&_show_pdf=1"


class ProjetosTarefasHandler:
    """Gerenciador de projetos e tarefas"""

    def __init__(self):
        self.dir_xmls = config.DATA_DIR / "xmls"
        os.makedirs(self.dir_xmls, exist_ok=True)

    def atualizar_projetos_tarefas(self, recurso: str, forcar_download: bool = False) -> list[dict]:
        """
        Baixa XMLs do NetProject, extrai tarefas do recurso e retorna os
        dados já prontos para ApontamentoRepository.sincronizar_projetos_tarefas().
        """
        try:
            logger.info("📥 Baixando XMLs do NetProject...")
            self._baixar_xmls(forcar_download)

            logger.info(f"🔍 Processando tarefas para recurso: {recurso}")
            todas_tarefas = []

            for nome_proj, _codigo in config_netproject.projetos_netproject.items():
                xml_path = self.dir_xmls / f"{nome_proj}.xml"
                if not xml_path.exists():
                    logger.warning(f"⚠️ XML não encontrado: {xml_path}")
                    continue

                todas_tarefas.extend(self._extrair_tarefas_recurso(xml_path, recurso))

            if not todas_tarefas:
                logger.warning(f"⚠️ Nenhuma tarefa encontrada para '{recurso}'")
                return []

            dados = self._aplicar_de_para(todas_tarefas)
            logger.info(f"✅ {len(dados)} tarefas prontas para sincronização")
            return dados

        except requests.RequestException as e:
            logger.error(f"❌ Erro de rede ao atualizar: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"❌ Erro na atualização: {e}", exc_info=True)
            return []

    def _aplicar_de_para(self, tarefas: list[dict]) -> list[dict]:
        """Aplica de/para e mapeia para o formato esperado pelo repository"""
        dados = []
        for t in tarefas:
            dados.append(
                {
                    "projeto": config_netproject.aplicar_projeto(t["project"]),
                    "tarefa": config_netproject.aplicar_tarefa(t["tarefa"]),
                    "ativo": t["ativo"] not in ("0", "", None),
                    "start": t["start"],
                    "finish": t["finish"],
                    "percent_complete": t["percent_complete"],
                    "notes": (t["notes"] or "").replace("\n", " ").strip(),
                }
            )
        return dados

    def _baixar_xmls(self, forcar: bool = False):
        """Baixa XMLs dos projetos NetProject"""
        for nome_proj, codigo in config_netproject.projetos_netproject.items():
            xml_path = self.dir_xmls / f"{nome_proj}.xml"

            if xml_path.exists() and not forcar:
                logger.debug(f"📄 Usando cache: {xml_path.name}")
                continue

            url = BASE_URL.format(codigo=codigo)
            logger.info(f"⬇️ Baixando {nome_proj}...")

            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                with open(xml_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"✅ {nome_proj}.xml salvo")
            except requests.RequestException as e:
                logger.error(f"❌ Erro ao baixar {nome_proj}: {e}")
            except OSError as e:
                logger.error(f"❌ Erro ao salvar {nome_proj}.xml: {e}")

    def _extrair_tarefas_recurso(self, xml_path: Path, recurso: str) -> list[dict]:
        """Extrai tarefas atribuídas a um recurso específico"""
        ns = {"ns": "http://schemas.microsoft.com/project"}

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            project_title = root.findtext("ns:Title", default=xml_path.stem, namespaces=ns)

            # Mapeia recursos
            resources = {}
            for r in root.findall(".//ns:Resource", ns):
                uid = r.findtext("ns:UID", default="", namespaces=ns)
                name = r.findtext("ns:Name", default="", namespaces=ns)
                if name:
                    resources[uid] = name

            # Encontra UID do recurso
            resource_uid = None
            for uid, name in resources.items():
                if name.lower() == recurso.lower():
                    resource_uid = uid
                    break

            if not resource_uid:
                logger.debug(f"Recurso '{recurso}' não encontrado em {xml_path.name}")
                return []

            # Encontra tarefas atribuídas
            assigned_task_uids = set()
            for a in root.findall(".//ns:Assignment", ns):
                ruid = a.findtext("ns:ResourceUID", default="", namespaces=ns)
                tuid = a.findtext("ns:TaskUID", default="", namespaces=ns)
                if ruid == resource_uid:
                    assigned_task_uids.add(tuid)

            # Mapeia tarefas
            tasks = {}
            outline_to_name = {}
            parent_map = {}

            for t in root.findall(".//ns:Task", ns):
                uid = t.findtext("ns:UID", default="", namespaces=ns)
                name = t.findtext("ns:Name", default="", namespaces=ns)
                active = t.findtext("ns:Active", default="0", namespaces=ns)
                start = t.findtext("ns:Start", default="", namespaces=ns)
                finish = t.findtext("ns:Finish", default="", namespaces=ns)
                percent = t.findtext("ns:PercentComplete", default="", namespaces=ns)
                notes = t.findtext("ns:Notes", default="", namespaces=ns)
                outline = t.findtext("ns:OutlineNumber", default="", namespaces=ns)

                if not uid or not name:
                    continue

                outline_to_name[outline] = name

                tasks[uid] = {
                    "project": project_title,
                    "tarefa": name,
                    "ativo": active,
                    "start": start,
                    "finish": finish,
                    "percent_complete": percent,
                    "notes": notes or "",
                    "outline": outline,
                }

                if outline and "." in outline:
                    parent_outline = ".".join(outline.split(".")[:-1])
                    parent_map.setdefault(parent_outline, []).append(uid)

            # Filtra apenas tarefas folha
            leaf_uids = {uid for uid, t in tasks.items() if t["outline"] not in parent_map}

            # Adiciona nome do pai se existir
            for uid in leaf_uids:
                outline = tasks[uid]["outline"]
                if outline and "." in outline:
                    parent_outline = ".".join(outline.split(".")[:-1])
                    parent_name = outline_to_name.get(parent_outline)
                    if parent_name:
                        tasks[uid]["tarefa"] = f"{tasks[uid]['tarefa']} <- {parent_name}"

            # Filtra tarefas válidas
            tarefas_validas = []
            for uid, t in tasks.items():
                if uid not in leaf_uids:
                    continue

                atribuida = uid in assigned_task_uids
                concluida = t["percent_complete"].isdigit() and int(t["percent_complete"]) == 100

                if atribuida and not concluida:
                    tarefas_validas.append(t)

            return tarefas_validas
        except ET.ParseError as e:
            logger.error(f"❌ Erro ao parsear XML {xml_path.name}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro ao processar {xml_path.name}: {e}")
            return []

    def obter_recursos_disponiveis(self) -> list[str]:
        """Retorna lista de recursos do primeiro XML disponível"""
        xmls = list(self.dir_xmls.glob("*.xml"))

        if not xmls:
            logger.info("📥 Nenhum XML encontrado, baixando...")
            self._baixar_xmls(forcar=True)
            xmls = list(self.dir_xmls.glob("*.xml"))

        if not xmls:
            return []

        ns = {"ns": "http://schemas.microsoft.com/project"}

        try:
            tree = ET.parse(xmls[0])
            root = tree.getroot()

            recursos = set()
            for r in root.findall(".//ns:Resource", ns):
                name = r.findtext("ns:Name", default="", namespaces=ns)
                if name:
                    recursos.add(name)

            return sorted(recursos)

        except ET.ParseError as e:
            logger.error(f"❌ Erro ao parsear XML para recursos: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro ao extrair recursos: {e}")
            return []
