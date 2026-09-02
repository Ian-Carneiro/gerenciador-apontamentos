# Apontador de Horas

Aplicação desktop para registro, gerenciamento e envio automático de apontamentos de horas para os sistemas **NetProject** e **SGIWeb**, com interface gráfica em PySide6 e persistência em SQLite via SQLAlchemy.

---

## Funcionalidades

- Registro de apontamentos com início/fim (substituição do fluxo CSV legado)
- Auditoria completa de alterações por campo (tabela `apontamentos_audit`)
- Sincronização de projetos e tarefas via XMLs baixados do NetProject
- Regras de De/Para configuráveis para normalização de nomes de projetos/tarefas
- Automação de envio para NetProject e SGIWeb via Playwright (browser headful)
- Suporte a múltiplos monitores (browser abre no monitor secundário, se disponível)
- Log rotativo com saída colorida no console e arquivo em `logs/app.log`
- Cache de cookies de sessão para evitar login repetido no NetProject

---

## Estrutura do Projeto

```
.
├── config.py                        # Configuração centralizada (paths, credenciais, timeouts)
├── main.py                          # Ponto de entrada: init_db → service → QApplication
├── requirements.txt
├── pyproject.toml
├── .env                             # Credenciais (não versionado)
├── data/
│   ├── apontamentos.db              # Banco SQLite
│   ├── config_netproject.json       # Projetos NetProject e regras De/Para
│   └── xmls/                        # XMLs baixados do NetProject (cache local)
├── logs/
│   └── app.log
├── resources/                       # Binários opcionais (Chrome/ChromeDriver)
├── src/
│   ├── automacao/
│   │   ├── exceptions.py            # Exceções de domínio da automação
│   │   ├── page_base.py             # BasePage e BrowserManager (Playwright)
│   │   ├── netproject_pages.py      # Page Objects do NetProject
│   │   ├── netproject_automacao.py  # Orquestrador da automação NetProject
│   │   ├── sgiweb_pages.py          # Page Objects do SGIWeb
│   │   └── sgiweb_automacao.py      # Orquestrador da automação SGIWeb
│   ├── core/
│   │   ├── apontamento_service.py   # Serviço principal (regras de negócio)
│   │   ├── config_netproject_handler.py  # Singleton de configuração NetProject
│   │   ├── credentials_validator.py # Validação de credenciais do .env
│   │   ├── favoritos_service.py     # Serviço de projetos/tarefas favoritos
│   │   └── projetos_tarefas.py      # Download e parsing de XMLs do NetProject
│   ├── db/
│   │   ├── database.py              # Engine SQLAlchemy, sessões e init_db()
│   │   ├── models.py                # Modelos ORM (Apontamento, Audit, ProjetoTarefa, DePara)
│   │   └── repository.py            # Repositório de acesso a dados
│   ├── ui/
│   │   ├── main_window.py           # Janela principal (PySide6)
│   │   ├── workers.py               # QThread workers para operações em background
│   │   ├── messagebox_utils.py      # Utilitários de diálogo
│   │   ├── ui_helpers.py            # Helpers de UI reutilizáveis
│   │   ├── dialogs/                 # Diálogos modais da aplicação
│   │   ├── style/                   # Estilos QSS
│   │   └── widgets/                 # Widgets customizados
│   └── utils/
│       └── logger.py                # Configuração de logging (console colorido + arquivo)
└── tests/
    ├── test_repository.py
    └── test_service.py
```

---

## Pré-requisitos

- Python 3.11+
- Playwright com Chromium instalado
- Variáveis de ambiente configuradas no `.env`

---

## Instalação

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd gerenciador-apontamentos

# 2. Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -e .

# 4. Instale o browser do Playwright
playwright install chromium

# 5. Configure as credenciais
cp .env.example .env
# Edite o .env com suas credenciais
```

---

## Configuração

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
# NetProject
USUARIO_NET_PROJECT=seu_usuario
SENHA_NET_PROJECT=sua_senha

# SGIWeb
SGI_WEB_LOGIN_USUARIO=seu_usuario
SGI_WEB_LOGIN_SENHA=sua_senha

# Opcional
LOG_LEVEL=INFO
```

As credenciais são lidas em `config.py` via `python-dotenv` e nunca expostas na interface.

---

## Uso

```bash
python main.py
```

Na primeira execução, o banco SQLite é criado automaticamente em `data/apontamentos.db` com todas as tabelas e índices necessários.

---

## Banco de Dados

O banco usa SQLite com WAL mode, foreign keys e índices de performance aplicados no bootstrap.

| Tabela               | Descrição                                                    |
|----------------------|--------------------------------------------------------------|
| `apontamentos`       | Registros de trabalho com início/fim na mesma linha          |
| `apontamentos_audit` | Histórico imutável de cada alteração por campo               |
| `projetos_tarefas`   | Cache local dos projetos/tarefas baixados do NetProject      |
| `depara`             | Regras de substituição de nomes de projeto/tarefa            |

Um apontamento com `fim IS NULL` indica sessão em execução. No máximo um por vez.

---

## Cenários de Apontamentos

A tela principal tem os campos **Projeto**, **Tarefa**, **Nota**, **Início** e **Fim**, e um botão que alterna entre **"Iniciar / Registrar"** (sem tarefa em execução) e **"Trocar Tarefa"** (com tarefa em execução), além do botão **"Parar Apontamento"**.

### 1. Iniciar agora
Sem apontamento em execução. Preencha Projeto e Tarefa, deixe Início e Fim em branco, clique em **Iniciar / Registrar**.
→ A barra de status passa a exibir "● Em execução · ERP › Dev · 00:00:01" e o botão vira "Trocar Tarefa".

### 2. Iniciar em horário específico
Sem apontamento em execução. Preencha Projeto e Tarefa, informe só o **Início** (ex.: 08:30) e deixe o Fim em branco. Clique em **Iniciar / Registrar**.
→ A sessão passa a rodar desde as 08:30, como se você tivesse iniciado naquele horário.

### 3. Retroativo completo
Sem apontamento em execução. Preencha Projeto, Tarefa, **Início** e **Fim** (ex.: 10:00–10:30). Clique em **Iniciar / Registrar**.
→ Toast "📝 Registrado: 0h 30min". Nada fica em execução — os campos são limpos e o botão permanece "Iniciar / Registrar".

### 4. Retroativo com tarefa ativa
Já existe uma tarefa em execução (ex.: "Dev" desde as 09:00). Preencha o Projeto/Tarefa da nova atividade e **Início/Fim** do intervalo (ex.: 10:00–10:30). Clique em **Trocar Tarefa**.
→ "Dev" é interrompida às 10:00, o intervalo é registrado como a nova atividade, e a barra de status volta a mostrar "Dev" em execução, como se ela nunca tivesse parado.

### 5. Troca de tarefa (agora)
Já existe uma tarefa em execução. Selecione o novo Projeto/Tarefa, deixe Início e Fim em branco. Clique em **Trocar Tarefa**.
→ Toast "⏹ Dev parado (1h 30min) / ▶️ Testes iniciado". A barra de status atualiza para a nova tarefa em execução.

### 6. Troca de tarefa em horário específico
Já existe uma tarefa em execução. Selecione o novo Projeto/Tarefa e informe só o **Início** (ex.: 11:00), com Fim em branco. Clique em **Trocar Tarefa**.
→ A tarefa anterior encerra às 11:00 e a nova passa a rodar a partir desse horário.

### Parar apontamento ativo
Com uma tarefa em execução, opcionalmente informe o **Fim** (senão usa o horário atual) e/ou uma **Nota**. Clique em **Parar Apontamento**.
→ Toast "Parado: ERP › Dev (2h 15min)". O botão "Parar Apontamento" é desabilitado e o principal volta a exibir "Iniciar / Registrar".

> Preencher só o **Fim** sem o **Início** é bloqueado com o aviso "Preencha também o Início quando informar o Fim". Um intervalo que conflita com um apontamento já existente é rejeitado com o horário e a tarefa em conflito, sugerindo consultar **Visualizar → Intervalos Livres Hoje**.

---

## Edição no Histórico

Acesse em **Visualizar → Histórico de Apontamentos** (`Ctrl+H`). A tabela agrupa os apontamentos por dia, com o total de horas ao final de cada bloco, e cada linha tem 5 ícones de ação: **✏️ Editar**, **⏱ Ajustar horário**, **✂️ Dividir**, **➕ Adicionar** e **🗑️ Deletar**.

### ✏️ Editar projeto/tarefa/nota
Abre um diálogo com Projeto, Tarefa e Nota pré-preenchidos; os horários aparecem só como referência (somente leitura). Altere o que quiser e clique em **Salvar**.

### ⏱ Ajustar horário
Abre um diálogo com o Início atual (e o Fim atual, se o apontamento já estiver encerrado) e um campo ao lado para o novo valor de cada um — preencha só o que quiser mudar. A duração resultante é recalculada em tempo real conforme você digita.
- Se for o apontamento mais recente do dia e ainda tiver Fim, aparece a opção **"Remover fim (reabrir apontamento)"**, que volta a deixá-lo em execução.
- Mudar o Início ou o Fim desloca automaticamente o apontamento vizinho (o anterior ou o seguinte), mantendo a sequência do dia sem buracos nem sobreposição.
- Um novo horário que colida com outro apontamento já existente é rejeitado, mostrando projeto, tarefa e horário do conflito.

### ✂️ Dividir apontamento
Só fica habilitado para apontamentos já finalizados — em uma tarefa ainda em execução, o ícone aparece desabilitado com o aviso "Finalize o apontamento para dividir". Informe o **horário de corte** e o diálogo mostra em tempo real como ficam a Parte 1 e a Parte 2 (mesmo projeto/tarefa, cada uma com seu próprio intervalo e duração). Clique em **Dividir** para confirmar.

### ➕ Adicionar apontamento
Insere um novo apontamento imediatamente antes ou depois do apontamento de referência. Selecione a posição (**Adicionar antes** ou **Adicionar depois**), informe Projeto, Tarefa, o **Horário** de início (se antes) ou de fim (se depois) e, opcionalmente, uma Nota. O preview é atualizado em tempo real mostrando o intervalo do novo apontamento.
- **Adicionar depois** só fica disponível para apontamentos já finalizados.
- O horário informado deve ser anterior ao início do apontamento de referência (se antes) ou posterior ao seu fim (se depois).
- O apontamento vizinho afetado tem seu horário ajustado automaticamente para evitar buracos ou sobreposições.

### 🗑️ Deletar
Pede confirmação mostrando projeto, tarefa e horário do apontamento, avisando que a ação não pode ser desfeita.

---

## Automação

### NetProject

A classe `AutomacaoNetProject` (em `src/automacao/netproject_automacao.py`) orquestra:

1. Validação de credenciais via `CredentialsValidator`
2. Login no NetProject (reusa cookies salvos em `data/.cache/state.json` se disponíveis)
3. Preenchimento de projeto, tarefa e horários via Page Objects com Select2
4. Envio e confirmação via callback opcional (`confirmar_envio`)

### SGIWeb

A classe `AutomacaoSGIWeb` (em `src/automacao/sgiweb_automacao.py`) orquestra:

1. Validação de credenciais
2. Login e navegação para marcação de jornada
3. Verificação se a data já possui horários preenchidos (com callback `confirmar_sobrescrita`)
4. Preenchimento dos horários de entrada/saída derivados dos apontamentos do dia

### Exceções de domínio

| Exceção                   | Quando é levantada                                       |
|---------------------------|----------------------------------------------------------|
| `AutomacaoError`          | Falha genérica durante a automação                       |
| `CredenciaisInvalidasError` | Credenciais ausentes ou inválidas no `.env`             |
| `NenhumApontamentoError`  | Nenhum apontamento encontrado para a data solicitada     |
| `SobrescritaCanceladaError` | Usuário recusou sobrescrever dados já existentes no SGIWeb |
| `EnvioCanceladoError`     | Usuário cancelou a confirmação final no NetProject       |

---

## Sincronização de Projetos

O `ProjetosTarefasHandler` (em `src/core/projetos_tarefas.py`) baixa XMLs no formato Microsoft Project do NetProject, extrai tarefas folha atribuídas ao recurso informado e sincroniza com a tabela `projetos_tarefas` do banco local.

Os XMLs são armazenados em cache em `data/xmls/`. Use `forcar_download=True` para ignorar o cache.

As configurações de projetos e regras de De/Para ficam em `data/config_netproject.json`, gerenciado pelo singleton `ConfigNetProjectHandler`.

---

## Logging

- **Console**: saída colorida por nível (DEBUG=azul, INFO=verde, WARNING=amarelo, ERROR=vermelho, CRITICAL=magenta)
- **Arquivo**: `logs/app.log` com rotação em 1 MB, mantendo até 10 backups
- Nível configurável via `LOG_LEVEL` no `.env` (padrão: `INFO`)

---

## Testes

```bash
pytest tests/
```

Para testes que envolvem banco de dados, use `reset_engine_for_tests(db_path)` disponível em `src/db/database.py` para apontar o engine para um banco temporário.

---
