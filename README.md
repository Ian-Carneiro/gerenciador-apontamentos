# Apontador de Horas

Aplicação desktop para registro, gerenciamento e envio automático de apontamentos de horas para os sistemas **NetProject** e **SGIWeb**, com interface gráfica em PySide6 e persistência em SQLite via SQLAlchemy.

---

## Funcionalidades

- Registro de apontamentos com início/fim (substituição do fluxo CSV legado)
- Auditoria completa de alterações por campo (tabela `apontamentos_audit`)
- Sincronização de projetos e tarefas via XMLs baixados do NetProject
- Regras de De/Para configuráveis para normalização de nomes de projetos/tarefas
- Automação de envio para NetProject e SGIWeb via Playwright (browser headful)
- Mesclagem de apontamentos locais com o sistema Mikael, com ajuste automático de divergências de horário
- Importação de apontamentos históricos a partir do PDF do Espelho de Ponto (SGIWeb), com prévia e detecção de duplicatas
- Configuração de jornada de trabalho (horas/dia, dias úteis, período do banco de horas) e cadastro de dias de exceção (feriado, dayoff, atestado)
- Relatório de Apontamentos: saldo do dia, do mês e do banco de horas, com detalhamento diário
- Favoritos: acesso rápido aos pares projeto/tarefa mais usados nos últimos 7 dias
- Suporte a múltiplos monitores (browser abre no monitor secundário, se disponível)
- Log rotativo com saída colorida no console e arquivo em `logs/app.log`
- Cache de cookies de sessão para evitar login repetido no NetProject

---

## Estrutura do Projeto

```
.
├── assets/
│   └── app_icon.png
├── config.py                        # Configuração centralizada (paths, credenciais, timeouts)
├── main.py                          # Ponto de entrada: init_db → service → QApplication
├── requirements.txt
├── pyproject.toml
├── .env                             # Credenciais (não versionado)
├── data/
│   ├── apontamentos.db              # Banco SQLite
│   ├── config_netproject.json       # Projetos NetProject e regras De/Para
│   ├── config_jornada.json          # Configuração de jornada e banco de horas
│   └── xmls/                        # XMLs baixados do NetProject (cache local)
├── logs/
│   └── app.log
├── resources/                       # Binários opcionais (Chrome/ChromeDriver)
├── src/
│   ├── automacao/
│   │   ├── exceptions.py            # Exceções de domínio da automação
│   │   ├── folha_ponto_import.py    # Parser do PDF do Espelho de Ponto (SGIWeb)
│   │   ├── mesclar_apontamentos.py  # Lógica de mesclagem, gaps e ajustes com Mikael
│   │   ├── mikael_automacao.py      # Download e parse do XLS do Mikael via Playwright
│   │   ├── netproject_automacao.py  # Orquestrador da automação NetProject
│   │   ├── netproject_pages.py      # Page Objects do NetProject
│   │   ├── page_base.py             # BasePage e BrowserManager (Playwright)
│   │   ├── sgiweb_automacao.py      # Orquestrador da automação SGIWeb
│   │   └── sgiweb_pages.py          # Page Objects do SGIWeb
│   ├── core/
│   │   ├── apontamento_service.py   # Serviço principal (regras de negócio)
│   │   ├── config_jornada_handler.py     # Singleton de configuração de jornada/banco de horas
│   │   ├── config_netproject_handler.py  # Singleton de configuração NetProject
│   │   ├── credentials_validator.py # Validação de credenciais do .env
│   │   └── projetos_tarefas.py      # Download e parsing de XMLs do NetProject
│   ├── db/
│   │   ├── database.py              # Engine SQLAlchemy, sessões e init_db()
│   │   ├── models.py                # Modelos ORM (Apontamento, Audit, ProjetoTarefa, DePara, DiaExcecao)
│   │   └── repository.py            # Repositório de acesso a dados
│   ├── ui/
│   │   ├── dialogs/
│   │   │   ├── adicionar_dialog.py      # Inserir apontamento antes/depois de um existente
│   │   │   ├── ajustar_horario_dialog.py # Ajustar início e/ou fim de um apontamento
│   │   │   ├── confirmacao_dialogs.py   # Confirmação visual para NetProject e SGIWeb
│   │   │   ├── dividir_dialog.py        # Dividir apontamento em dois no horário de corte
│   │   │   ├── editar_dialog.py         # Editar projeto, tarefa e nota
│   │   │   ├── folha_ponto_dialog.py    # Prévia e importação de apontamentos do Espelho de Ponto
│   │   │   ├── historico_dialog.py      # Histórico de apontamentos agrupado por dia
│   │   │   ├── jornada_config_dialog.py # Config. de jornada, banco de horas e dias de exceção
│   │   │   ├── mesclar_dialog.py        # Mesclagem e ajuste com Mikael
│   │   │   ├── projetos_tarefas_dialog.py # Editar/renomear pares projeto/tarefa no banco
│   │   │   ├── relatorio_dialog.py      # Relatório de horas: hoje, mês e banco de horas
│   │   │   └── utils_dialogs.py         # Diálogos utilitários (pedir_data, selecionar_recurso)
│   │   ├── main_window.py           # Janela principal (PySide6)
│   │   ├── messagebox_utils.py      # Wrappers de QMessageBox (showinfo, askyesno, etc.)
│   │   ├── style/
│   │   │   ├── theme.qss            # Folha de estilos global (QSS)
│   │   │   └── tokens.py            # Paleta de cores e constantes visuais (Mariana)
│   │   ├── ui_helpers.py            # Helpers de UI reutilizáveis (centralizar_janela, truncar_texto)
│   │   └── workers.py               # QThread workers (atualização de projetos, importação de folha de ponto)
│   │   └── widgets/
│   │       ├── favoritos_popup.py   # Popup de seleção rápida de favoritos
│   │       ├── filterable_combo.py  # Campo editável com dropdown filtrado (sem QComboBox)
│   │       ├── hora_field.py        # Widget de entrada HH:MM:SS com máscara automática
│   │       └── status_bar.py        # Barra de estado com timer do apontamento ativo
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

# SGIWeb / Mikael (mesmo login)
SGI_WEB_LOGIN_USUARIO=seu_usuario
SGI_WEB_LOGIN_SENHA=sua_senha

# Opcional
LOG_LEVEL=INFO
```

As credenciais do SGIWeb são reutilizadas para o login no Mikael. O threshold de gap (em minutos) abaixo do qual divergências são marcadas para ajuste automático está definido diretamente em `config.py`:

```python
MIKAEL_GAP_THRESHOLD_MIN = 5  # gaps < 5min vêm com checkbox marcado por padrão
```

Altere esse valor em `config.py` para ajustar o comportamento padrão da mesclagem.

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
| `dias_excecao`       | Feriados, dayoffs e atestados que abatem a jornada esperada  |

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

> Preencher só o **Fim** sem o **Início** é bloqueado com o aviso "Preencha também o Início quando informar o Fim". Um intervalo que conflita com um apontamento já existente é rejeitado com o horário e a tarefa em conflito.

---

## Favoritos

O menu **★ Favoritos** (na barra de menus) abre um popup com os pares projeto/tarefa mais usados nos últimos 7 dias, ordenados por tempo total. Clicar em um item preenche automaticamente os campos Projeto e Tarefa da janela principal. O tooltip de cada item exibe o total de horas registradas naquele par no período.

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

## Mesclagem com Mikael

### Como acionar

Há dois pontos de entrada para a mesclagem:

**Manualmente:** **Automação → 🔀 Mesclar Apontamentos com Mikael** (`Ctrl+M`). Um seletor de data é exibido antes de abrir o diálogo.

**Durante o envio ao SGIWeb:** No diálogo de confirmação de horários (**Automação → Apontar no SGIWeb**, `Ctrl+G`), marque o checkbox **"Ajustar horários com o Mikael"**. A mesclagem é executada antes do envio; se cancelada, o envio também é cancelado. Após aplicar os ajustes, os horários são recalculados e uma segunda confirmação é exibida antes de prosseguir.

### O que acontece

A tela de mesclagem baixa o XLS de apontamentos do Mikael via Playwright (uma janela de browser aparece brevemente e é fechada automaticamente após o download), compara com os apontamentos locais do dia e apresenta uma tabela unificada. O processo permite fechar automaticamente pequenas divergências de horário entre as duas fontes antes do envio.

A tabela mostra Origem (**Local** ou **Mikael**), Início, Fim, Projeto, Tarefa e uma coluna **Ajustar** com checkbox nas linhas onde há divergência de horário com o registro adjacente.

**Regras:**
- O Mikael é sempre a fonte da verdade — seus horários nunca são alterados.
- Apenas o apontamento **Local** adjacente se desloca para fechar a divergência.
- Apontamentos locais totalmente englobados por um intervalo do Mikael são silenciosamente removidos da mesclagem (o intervalo do Mikael os substitui).
- O checkbox vem marcado por padrão quando a divergência é menor que `MIKAEL_GAP_THRESHOLD_MIN` (padrão: 5 minutos), seja ela um intervalo em aberto ou uma sobreposição entre os dois registros.
- Divergências grandes vêm com o checkbox desmarcado, exigindo confirmação manual.
- A tabela é uma prévia ao vivo: marcar/desmarcar o checkbox atualiza o horário exibido na hora, sem gravar nada no banco. A gravação só ocorre ao clicar em **"Aplicar ajustes"**.
- Passe o mouse sobre o checkbox para ver a descrição completa da divergência (horários, duração e os dois lados envolvidos).
- A operação é idempotente: reaplicar a mesclagem para a mesma data não duplica os intervalos já gravados.

### O que é gravado no banco

Ao confirmar, para cada intervalo do Mikael que ainda não existe no banco, é criado um apontamento com projeto `"Mikael Apontamentos"` e tarefa no formato `"CÓDIGO - Nome do Projeto"`. Para apontamentos locais com ajuste marcado, apenas o início ou o fim é atualizado.

### Exemplos práticos

**1. Intervalo pequeno em aberto (imprecisão no fim do apontamento Local)**
Local termina 13:56:44, Mikael começa 13:57:44 (1min de diferença).
→ Checkbox vem marcado. Tabela mostra o Fim do Local ajustado para `13:57:44`, eliminando o intervalo.

**2. Sobreposição pequena (Local "vazando" sobre o Mikael)**
Local vai até 13:58:44, mas o Mikael já começou às 13:57:44 (1min de sobreposição).
→ Checkbox vem marcado. Tabela mostra o Fim do Local recuado para `13:57:44`.

**3. Sobreposição grande**
Local vai até 15:08:46, mas o Mikael começou às 13:57:44 (71min de sobreposição).
→ Checkbox vem **desmarcado** por padrão (ajuste grande demais para ser automático). Tabela mantém o Fim original do Local até o usuário decidir marcar manualmente.

**4. Intervalo após o Mikael (retomada do trabalho Local)**
Mikael termina 13:59:18, o próximo apontamento Local só começa às 14:04:00 (intervalo de 4min42s).
→ Se pequeno o suficiente, checkbox vem marcado. Tabela mostra o Início do Local recuado para `13:59:18`, alinhando com o fim do Mikael.

---

## Jornada de Trabalho e Relatório

### Configuração

Acesse em **Configurar → 🗓️ Jornada de Trabalho**. O diálogo tem duas partes:

- **Jornada**: horas esperadas por dia, dias da semana considerados úteis, e a âncora do banco de horas (data de início de um período — o dia do mês define o "corte" e deve estar entre 1 e 28). A quantidade de meses por período (padrão: 4) determina o tamanho do ciclo do banco de horas; um preview mostra os próximos períodos gerados a partir da âncora escolhida.
- **Dias de exceção**: feriados, dayoffs e atestados que abatem a jornada esperada. Podem ser **fixos** (uma data específica) ou **recorrentes** (repetem todo ano, considerando só dia/mês). Cada exceção abona o dia inteiro ou uma quantidade parcial de horas.

Tudo é persistido em `data/config_jornada.json` (config de jornada) e na tabela `dias_excecao` (exceções).

### Relatório de Apontamentos

Acesse em **Visualizar → 📊 Relatório de Apontamentos** (`Ctrl+J`). Mostra três cartões — **Hoje**, **Mês** e **Banco de Horas** — com horas trabalhadas, saldo e (no banco de horas) dias úteis restantes até o fim do período. Uma tabela detalha esperado/trabalhado/saldo dia a dia dentro do mês corrente.

- A **data de referência** pode ser alterada para consultar o relatório em qualquer dia.
- **Ignorar segundos** consolida apontamentos contínuos em blocos antes de arredondar, evitando ruído de segundos na soma.
- **Horas em decimal** alterna o formato entre `Xh MMmin` e `X.XXh`.
- Dias com exceção cadastrada aparecem marcados na tabela (🔁 recorrente, • fixa).

---

## Importação de Folha de Ponto (Espelho de Ponto)

Acesse em **Automação → 📄 Importar Folha de Ponto (PDF)**. Permite selecionar um ou mais PDFs do Espelho de Ponto do SGIWeb e importar os horários como apontamentos históricos.

### Como funciona

1. O(s) PDF(s) são lidos em background (`ImportarFolhaPontoWorker`), extraindo pares de entrada/saída por dia via `pdfplumber`.
2. Uma prévia é exibida com uma linha por par entrada/saída, mostrando data, horários e duração, cada uma com um checkbox de importação.
3. Dias que já possuem apontamento local no banco vêm com o checkbox **desmarcado** por padrão, para evitar duplicidade — o usuário pode marcar manualmente para sobrescrever.
4. Ao confirmar, cada linha marcada é gravada como um apontamento retroativo com projeto `"Histórico (folha de ponto)"`, ignorando checagem de sobreposição.

> Apontamentos importados por esta via (assim como os do Mikael) são ignorados automaticamente pelo envio ao NetProject.

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

| Exceção                     | Quando é levantada                                            |
|-----------------------------|---------------------------------------------------------------|
| `AutomacaoError`            | Falha genérica durante a automação                            |
| `CredenciaisInvalidasError` | Credenciais ausentes ou inválidas no `.env`                   |
| `NenhumApontamentoError`    | Nenhum apontamento encontrado para a data solicitada          |
| `SobrescritaCanceladaError` | Usuário recusou sobrescrever dados já existentes no SGIWeb    |
| `EnvioCanceladoError`       | Usuário cancelou a confirmação final no NetProject            |

---

## Sincronização de Projetos

O `ProjetosTarefasHandler` (em `src/core/projetos_tarefas.py`) baixa XMLs no formato Microsoft Project do NetProject, extrai tarefas folha atribuídas ao recurso informado e sincroniza com a tabela `projetos_tarefas` do banco local.

Os XMLs são armazenados em cache em `data/xmls/`. Use `forcar_download=True` para ignorar o cache.

Acesse em **Configurar → 🔄 Atualizar Projetos / Tarefas** (`Ctrl+R`). Um seletor de recurso é exibido (nome do usuário conforme cadastrado no NetProject) e o download ocorre em background via `AtualizarProjetosWorker`.

Para corrigir typos ou renomear pares projeto/tarefa já lançados, use **Configurar → ✏️ Editar Projetos / Tarefas**. A correção é aplicada retroativamente em todos os apontamentos que usam aquele par.

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