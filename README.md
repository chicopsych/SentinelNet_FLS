# SentinelNet_FLS: Monitoramento de Integridade e Conformidade de Rede

## 📋 Visão Geral

O **SentinelNet_FLS** é uma ferramenta de auditoria contínua para ambientes de rede, baseada em princípios de **Infrastructure as Code (IaC)** e **compliance operacional**.

A proposta central é simples: comparar o estado real dos equipamentos de rede com uma **Fonte Única da Verdade (Baseline)** definida em arquivos JSON versionáveis.

Com isso, a solução identifica rapidamente:

- **Configuration Drift** (desvios entre o esperado e o atual)
- **Alterações não documentadas** em dispositivos críticos
- **Riscos de segurança** causados por mudanças indevidas de configuração

Esse modelo é especialmente útil para MSPs, consultorias de TI e equipes de infraestrutura que precisam de rastreabilidade, padronização e evidências de auditoria.

---

## 📊 Status Atual do Projeto (26/02/2026)

### Resumo executivo

- **Maturidade atual:** MVP técnico funcional (CLI + Dashboard Flask inicial)
- **Coleta de dados de rede:** implementada para MikroTik
- **Detecção de drift:** implementada e integrada ao loop de auditoria em lote no `main.py`
- **Relatórios de auditoria:** persistência em JSON, HTML e SQLite implementada
- **Dashboard Flask:** APIs e telas principais já conectadas ao SQLite (`health`, `devices`, `incidents`)
- **Próximo marco principal:** onboarding completo de ativos pelo dashboard (discovery + cadastro seguro de credenciais + baseline)

### Semáforo de andamento

- 🟢 **Concluído:** schema, driver base, diff engine, report manager, cofre de credenciais, esqueleto Flask
- 🟡 **Em progresso:** onboarding operacional via dashboard (discovery de ativos, cadastro e gestão de inventário)
- 🔴 **Não iniciado:** MCP Server, análise IA de drift, remediação IA com execução controlada

### 📈 Progresso percentual por Task (estimativa)

| Task | Escopo | Status | Progresso |
| --- | --- | --- | ---: |
| 01 | Schema JSON (Pydantic) | ✅ Concluído | 100% |
| 02 | Driver Base Abstrato | ✅ Concluído | 100% |
| 03 | Driver MikroTik (MVP) | 🟡 Parcial | 95% |
| 04 | Parsing TTP (MVP) | 🟡 Parcial | 65% |
| 05 | Diff Engine | ✅ Concluído | 100% |
| 06 | Relatório + Logging | ✅ Concluído | 100% |
| 07 | Gestão de Credenciais | ✅ Concluído | 100% |
| 08 | Exposição MCP Server | 🔴 Não iniciado | 0% |
| 09 | AI Drift Analysis | 🔴 Não iniciado | 0% |
| 10 | Remediação por IA | 🔴 Não iniciado | 0% |

## Progresso geral do roadmap (10 tasks): ~66%

### 📈 Progresso percentual por Fase do Dashboard (estimativa)

| Fase | Escopo | Status | Progresso |
| --- | --- | --- | ---: |
| Fase 1 | Fundamentos de dados e telemetria | 🟡 Parcial | 65% |
| Fase 2 | API de observabilidade (Flask) | 🟡 Parcial | 70% |
| Fase 3 | Dashboard web em Flask | 🟡 Parcial | 68% |
| Fase 4 | Motor de correção segura | 🔴 Não iniciado | 0% |
| Fase 5 | Alertas, SLOs e governança | 🔴 Não iniciado | 0% |

### Progresso geral do dashboard (5 fases): ~41%

---

## 🎯 Objetivos do Projeto

- Garantir a **integridade configuracional** dos ativos de rede
- Reduzir impacto de mudanças manuais fora de processo
- Aumentar previsibilidade operacional em ambientes multi-cliente
- Gerar base de evidência para auditorias internas e externas
- Permitir evolução incremental para múltiplos fabricantes

---

## 🚀 Funcionalidades Principais

- **Snapshot Automático:** coleta da configuração *running* via SSH/API
- **Normalização de Dados:** transformação de saídas CLI proprietárias em JSON estruturado
- **Detecção de Drift:** comparação entre baseline e estado atual
- **Relatórios de Auditoria:** registro de discrepâncias com contexto
- **Arquitetura Multi-Vendor:** suporte extensível por drivers modulares

### ✅ Implementações já concluídas

- **Core / Modelagem (`core/schemas.py`)**
  - Modelos Pydantic completos para `DeviceConfig`, `Interface`, `Route` e `FirewallRule`
  - Validação estrutural padronizada para entrada/saída de snapshots

- **Driver Abstrato (`core/base_driver.py`)**
  - Contrato padrão para vendors (`connect`, `get_config_snapshot`, `disconnect`)
  - Context manager implementado para garantir encerramento de sessão

- **Driver MikroTik (`drivers/mikrotik_driver.py`)**
  - Conexão SSH com Netmiko
  - Coleta `/export verbose`
  - Parse de metadados (hostname/model/version)
  - Parse de rotas e firewall com templates TTP
  - Factory `from_vault(...)` para uso com cofre criptografado

- **Diff Engine (`core/diff_engine.py`)**
  - Comparação baseline × current para campos escalares e listas
  - Auditoria especializada de firewall com:
    - `position_drift`
    - `parameter_drift`
    - `missing_rules`
    - `extra_rules`

- **Auditoria e Persistência (`core/audit_report.py` + `core/report_manager.py`)**
  - Classificação automática de severidade (`COMPLIANT` → `CRITICAL`)
  - Persistência simultânea em JSON + HTML + SQLite
  - Consulta de histórico e estatísticas agregadas

- **Segurança de Credenciais (`utils/vault.py` + `utils/vault_setup.py`)**
  - Cofre criptografado com Fernet
  - Master key via variável `SENTINEL_MASTER_KEY`
  - CLI utilitário para gerar chave e gerenciar credenciais

- **Observabilidade (`internalloggin/logger.py`)**
  - Logging central com `RotatingFileHandler`
  - Integração em módulos centrais e fluxo de demonstração

- **Dashboard Flask (`dashboard/` + `run.py`)**
  - App Factory (`create_app`)
  - Blueprints de `auth`, `health`, `devices`, `incidents`, `remediation`
  - Camadas compartilhadas `dashboard/common` e `dashboard/repositories` para HTTP/DB/queries
  - Templates base com Bootstrap 5 + páginas de overview/incidentes
  - Rota raiz `/` redirecionando para `/health/overview`
  - Overview em tempo real com SSE (`/health/stream`) e fallback por polling (`/health/api/overview`)
  - Rotas de `incidents` e `devices` conectadas ao SQLite real (`inventory/sentinel_data.db`)
  - Remediação separada em fluxo UI (`/remediation/ui/*`) e API tokenizada (`/remediation/api/*`)

- **Incident Engine (`core/incident_engine.py`)**
  - Tabela `incidents` criada automaticamente no SQLite
  - Persistência de incidentes com `payload_json`
  - Pronto para alimentar dashboard e histórico operacional

- **Stress Test (`stress_test.py`)**
  - Geração de incidentes simulados realistas para validar dashboard e consultas
  - Cenários para drift escalar e auditoria de firewall

---

## 🔄 Fluxo de Funcionamento

1. O inventário define quais dispositivos devem ser auditados.
2. O driver do fabricante realiza conexão segura no ativo.
3. A configuração bruta é coletada (*running config* ou equivalente).
4. O parser converte texto não estruturado em objetos JSON normalizados.
5. O Diff Engine compara baseline x estado real.
6. O sistema grava relatório com os desvios encontrados.

Esse fluxo desacopla coleta, parsing e auditoria, facilitando manutenção e evolução do projeto.

---

## 🏗️ Arquitetura Técnica

O projeto segue o padrão **Strategy**, mantendo o núcleo desacoplado das particularidades de cada fabricante.

### Camadas principais

1. **Core Engine**

- Coordena o ciclo de auditoria
- Invoca parser, comparador e logger
- Define regras de comparação e severidade

1. **Drivers Layer**

- Implementa conexão/coleta por vendor
- Isola comandos e diferenças de protocolo
- Facilita inclusão de novos fabricantes sem alterar o core

1. **Baseline (JSON)**

- Representa o estado esperado por cliente, site ou dispositivo
- Pode ser versionado em Git
- Serve como referência para compliance

1. **Parser (TTP/TextFSM)**

- Converte CLI textual em estrutura previsível
- Permite comparação por campos semânticos
- Reduz ruído de formatação textual

---

## 🧰 Stack Técnica

- **Python 3.10+**
- **Netmiko** (coleta via SSH)
- **TTP / TextFSM** (parsing)
- **Pydantic** (validação de schema)
- **Flask** (API e backend do dashboard)
- **SQLite** (opcional para histórico)
- **Logging nativo do Python + RotatingFileHandler** (observabilidade básica)

---

## 📁 Estrutura do Diretório

```text
SentinelNet_FLS/
├── .gitignore
├── README.md
├── core/                       # Núcleo da auditoria e contratos base
│   ├── __init__.py
│   ├── base_driver.py
│   └── schemas.py
├── drivers/                    # Drivers por fabricante
│   ├── __init__.py
│   └── mikrotik_driver.py
├── internalloggin/             # Logging interno centralizado
│   ├── __init__.py
│   ├── logger.py
├── inventory/                  # Inventário e dados por cliente
│   ├── .gitkeep
│   ├── customer/
│   │   └── customer.py
│   └── inventorycreator.py
├── logs/                       # Saídas/histórico de execução
│   └── .gitkeep
├── templates/                  # Templates de parsing (TTP/TextFSM)
│   ├── .gitkeep
│   ├── __init__.py
│   ├── mikrotik_firewall.ttp
│   └── mikrotik_routes.ttp
├── dashboard/                  # Dashboard Flask (API + frontend)
│   ├── __init__.py             # App Factory (create_app)
│   ├── config.py               # Configurações por ambiente
│   ├── extensions.py           # Extensões Flask compartilhadas
│   ├── blueprints/             # Módulos de rotas por domínio
│   │   ├── __init__.py
│   │   ├── auth.py             # Autenticação por token
│   │   ├── health.py           # GET /health/overview
│   │   ├── devices.py          # GET /devices
│   │   ├── incidents.py        # GET /incidents
│   │   └── remediation.py      # POST /incidents/<id>/remediation/*
│   ├── common/                 # Helpers compartilhados (HTTP, DB, constantes)
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── db.py
│   │   └── http.py
│   ├── repositories/          # Camada de acesso a dados por domínio
│   │   ├── __init__.py
│   │   └── incidents_repository.py
│   ├── templates/              # Templates Jinja2
│   │   ├── base.html           # Layout base (Bootstrap 5)
│   │   ├── overview.html       # Painel executivo KPIs
│   │   ├── incidents.html      # Lista de incidentes
│   │   ├── incident_detail.html# Detalhe + diff + remediação
│   │   ├── 404.html
│   │   └── partials/           # Fragmentos reutilizáveis (badges/alerts/empty-state)
│   └── static/
│       ├── css/
│       │   ├── main.css        # Entrada principal de estilos
│       │   ├── base/           # Tokens/reset/utilitários
│       │   ├── layout/         # Navbar/footer
│       │   ├── components/     # Badge/table/card/diff/empty-state
│       │   └── pages/          # Ajustes por página
│       └── js/
│           └── overview.js     # SSE/polling da overview
├── utils/                      # Utilitários compartilhados
│   └── __init__.py
├── main.py                     # Ponto de entrada da auditoria CLI
├── run.py                      # Ponto de entrada do dashboard Flask
└── requirements.txt            # Dependências do projeto
```

---

## 🛡️ Premissas de Segurança

- **Integridade da conexão:** validar fingerprint SSH para mitigar MITM
- **Proteção de segredos:** nunca armazenar credenciais em texto puro
- **Mínimo privilégio:** usar contas de coleta com perfil somente leitura
- **Rastreabilidade:** registrar quem executou, quando e contra quais ativos
- **Separação por cliente:** isolar inventário, logs e parâmetros sensíveis

---

## ⚙️ Execução Local (Guia Rápido)

> Ajuste os comandos conforme a estrutura final do repositório.

```bash
# 1) Criar e ativar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 2) Instalar dependências
pip install -r requirements.txt

# 3) Executar auditoria CLI (exemplo)
python main.py

# 4) Iniciar o dashboard Flask (desenvolvimento)
python run.py
# Acesse: http://127.0.0.1:5000/health/overview
```

### Pré-requisitos

- Acesso de rede aos dispositivos alvo
- Credenciais de leitura válidas
- Baseline JSON definido para os ativos auditados
- Templates de parsing compatíveis com o firmware/versão dos equipamentos

### Endpoints disponíveis no Dashboard Flask (estado atual)

> `health`, `devices` e `incidents` já operam com dados reais do SQLite; remediação ainda está em estágio inicial/controlado.

- `GET /` → redireciona para overview
- `GET /health/ping` → healthcheck simples
- `GET /health/overview` → overview (HTML/JSON)
- `GET /health/api/overview` → endpoint JSON para polling
- `GET /health/stream` → Server-Sent Events (atualização em tempo real)
- `GET /devices/` e `GET /devices/<device_id>`
- `GET /devices/discover` e `POST /devices/discover` → discovery de ativos por faixa CIDR (nmap)
- `GET /incidents/` e `GET /incidents/<incident_id>`
- `GET /auth/verify` (protegido por token)
- `POST /incidents/<incident_id>/remediation/ui/suggest` (UI)
- `POST /incidents/<incident_id>/remediation/ui/approve` (UI)
- `POST /incidents/<incident_id>/remediation/ui/execute` (UI)
- `POST /incidents/<incident_id>/remediation/api/suggest` (token)
- `POST /incidents/<incident_id>/remediation/api/approve` (token)
- `POST /incidents/<incident_id>/remediation/api/execute` (token)
- `GET /incidents/<incident_id>/remediation/api/status` (token)

---

## 📌 Escopo Inicial (MVP)

Para garantir entregas rápidas e validar valor cedo, o MVP pode focar em:

1. Suporte inicial a **MikroTik**
2. Coleta de configuração via `/export`
3. Parsing de blocos essenciais (interfaces, rotas, firewall)
4. Diff com saída legível em log
5. Execução por linha de comando para um inventário simples

---

## 🛠️ Roadmap de Execução (Task List)

Esta sequência prioriza base sólida antes de aumentar o escopo multi-fabricante e IA.

1. [x] **Task 01: Definição do Schema JSON**
   - ✅ Implementada em `core/schemas.py`

2. [x] **Task 02: Implementação da Classe Abstrata (Driver Base)**
   - ✅ Implementada em `core/base_driver.py`

3. [~] **Task 03: Desenvolvimento do Driver MikroTik (MVP)**
   - ✅ Conexão Netmiko e coleta `/export verbose`
   - ✅ Parse de cabeçalho e montagem de `DeviceConfig`
   - ✅ Integrado ao loop de auditoria em lote no `main.py`
   - ⏳ Pendente: ampliar cobertura para cenários de firmware/saída heterogênea

4. [~] **Task 04: Criação dos Templates de Parsing (TTP)**
   - ✅ Cobertura inicial para rotas e firewall
   - ⏳ Falta ampliar cobertura (interfaces e outros blocos do MVP)

5. [x] **Task 05: Construção do Diff Engine**
   - ✅ Implementado em `core/diff_engine.py`
   - ✅ Comparação semântica + auditoria específica de firewall

6. [x] **Task 06: Módulo de Relatório e Logging**
   - ✅ Logging central implementado
   - ✅ Persistência de relatório em JSON, HTML e SQLite

7. [x] **Task 07: Sistema de Gestão de Credenciais**
   - ✅ Cofre criptografado implementado em `utils/vault.py`
   - ✅ CLI de setup e gestão em `utils/vault_setup.py`

8. [ ] **Task 08: Exposição como MCP Server**
   - ❌ Ainda não iniciado

9. [ ] **Task 09: Análise de Desvio Assistida por IA (AI Drift Analysis)**
   - ❌ Ainda não iniciado

10. [ ] **Task 10: Remediação Sugerida por IA**

- ❌ Ainda não iniciado

### Próximas prioridades recomendadas (curto prazo)

1. Implementar discovery de ativos via `nmap` no dashboard (`/devices/discover`) com execução controlada no backend.
2. Implementar cadastro de dispositivo + credenciais pelo dashboard, persistindo segredos no `VaultManager`.
3. Migrar de inventário estático (`DEVICE_INVENTORY`) para inventário dinâmico em SQLite com telas de gestão.
4. Conectar baseline por cliente/dispositivo no fluxo de onboarding e auditoria recorrente.
5. Incluir testes automatizados de regressão para `diff`, `incident_engine`, `vault` e rotas Flask.

---

## 🧭 Alinhamento com o Contexto do Chat (`conversa-com-ia.txt`)

As tasks abaixo foram adicionadas para manter o desenvolvimento aderente ao planejamento discutido no chat (foco em operação comercial, dashboard e onboarding seguro de clientes).

1. [x] **Task A1: Discovery de Ativos via Nmap (Dashboard)**
   - ✅ Fluxo de descoberta por faixa CIDR implementado no dashboard (`/devices/discover`)
   - ✅ Execução de `nmap` no backend com parser XML estruturado
   - ✅ Exibição de ativos encontrados com seleção para cadastro (handoff para Task A2)

2. [ ] **Task A2: Cadastro de Dispositivo via Dashboard**
   - Criar formulário de onboarding (`customer`, `device`, `vendor`, `host`, `porta`)
   - Validar campos obrigatórios e evitar duplicidade de dispositivo
   - Persistir metadados do ativo no SQLite

3. [ ] **Task A3: Cadastro Seguro de Credenciais (UI → Vault)**
   - Integrar formulário do dashboard ao `VaultManager`
   - Gravar credenciais apenas no `inventory/vault.enc`
   - Garantir que logs nunca incluam senha/token

4. [ ] **Task A4: Inventário Dinâmico no Lugar do Estático**
   - Substituir uso de `DEVICE_INVENTORY` estático por consulta ao banco
   - Permitir ativar/desativar ativos sem editar código
   - Atualizar `main.py` para consumir inventário persistido

5. [ ] **Task A5: Baseline no Onboarding**
   - Definir baseline inicial no primeiro snapshot de cada ativo
   - Permitir atualização controlada de baseline (com trilha de auditoria)
   - Exibir estado da baseline por dispositivo no dashboard

6. [ ] **Task A6: Detalhe de Incidente com Diff Comercial**
   - Melhorar visualização baseline × current no detalhe do incidente
   - Destacar impacto técnico e severidade para leitura executiva
   - Preparar saída reutilizável para relatório de cliente

7. [ ] **Task A7: Relatório Mensal de Conformidade**
   - Gerar relatório consolidado por cliente (período, severidades, MTTA/MTTR)
   - Exportar em formato entregável ao cliente (HTML/PDF)
   - Incluir evidências de remediações executadas

8. [ ] **Task A8: Testes E2E do Fluxo Operacional**
   - Cobrir fluxo completo: descoberta → cadastro → auditoria → incidente → dashboard
   - Adicionar massa de teste baseada no `stress_test.py`
   - Validar comportamento com falha parcial por dispositivo

---

## 🤖 Integração com IA & OpenClaw.ai (Futuro)

O projeto está sendo construído com foco em interoperabilidade com agentes de IA. A estrutura de dados em JSON e a validação via Pydantic permitem que o SentinelNet_FLS atue como um **provedor de contexto para LLMs** através do protocolo **MCP (Model Context Protocol)** e orquestradores como o **OpenClaw**.

### Plano de Implementação do Dashboard (Monitoramento + Correção)

Objetivo: implementar um dashboard operacional completo para **detectar, priorizar e corrigir** erros de configuração e falhas de dispositivos de rede com rastreabilidade fim a fim.

#### Fase 1 — Fundamentos de Dados e Telemetria

1. Consolidar um modelo único de eventos (`drift`, `falha de coleta`, `erro de parsing`, `falha de autenticação`, `inconsistência de baseline`).
2. Padronizar severidade (`INFO`, `WARNING`, `CRITICAL`) e incluir metadados mínimos: cliente, site, dispositivo, vendor, timestamp, causa provável e impacto.
3. Persistir eventos em armazenamento consultável (SQLite no MVP) com histórico e trilha de auditoria.
4. Definir janelas de retenção e rotação para dados operacionais e evidências.

##### Entregáveis da Fase 1

- Tabela/coleção de eventos operacionais
- Contrato JSON versionado para eventos e status de remediação
- Camada de consulta pronta para alimentar API do dashboard

#### Fase 2 — API de Observabilidade e Orquestração (Flask)

1. Criar endpoints para visão operacional:
   - `GET /health/overview` (saúde geral)
   - `GET /devices` (estado por dispositivo)
   - `GET /incidents` (lista e filtro de incidentes)
   - `GET /incidents/{id}` (detalhes + evidências)
2. Implementar endpoint de ação corretiva assistida:
   - `POST /incidents/{id}/remediation/api/suggest`
   - `POST /incidents/{id}/remediation/api/approve`
   - `POST /incidents/{id}/remediation/api/execute` (modo controlado)
3. Garantir RBAC mínimo (operador, revisor, admin) e trilha de aprovação para ações sensíveis.
4. Incluir rate limit e autenticação por token para integração segura.
5. Estruturar backend em Flask com Blueprints separados por domínio (health, devices, incidents, remediation, auth).

##### Entregáveis da Fase 2

- API REST documentada para consumo do dashboard
- Fluxo de aprovação de remediação com auditoria
- Contratos de erro padronizados para troubleshooting

#### Fase 3 — Dashboard Web em Flask (Operação em Tempo Real)

1. Implementar painel executivo com KPIs:
   - Dispositivos saudáveis x com incidente
   - Incidentes por severidade
   - Top 10 causas recorrentes
   - MTTA e MTTR
2. Implementar visão de incidentes com filtros por cliente, site, vendor, severidade, status e período.
3. Implementar página de detalhe do incidente com:
   - Diff baseline x atual
   - Evidência técnica (trechos de config/log)
   - Sugestão de remediação
   - Histórico de ações e aprovações
4. Implementar fila de remediação com estados: `novo`, `em análise`, `aprovado`, `executado`, `falhou`, `revertido`.
5. Implementar frontend inicial com templates server-side (Jinja2) para acelerar o MVP.

##### Entregáveis da Fase 3

- Interface web funcional para NOC/SOC
- Navegação por cliente e ativo com drill-down
- Linha do tempo de incidentes e remediações

#### Fase 4 — Motor de Correção Segura

1. Implementar geração de comandos corretivos (rule-based + IA opcional).
2. Validar comandos por *allowlist* e políticas de segurança antes da execução.
3. Suportar modo `dry-run` obrigatório no MVP para simulação de impacto.
4. Executar remediação em janela controlada com rollback pré-definido.
5. Recoletar snapshot após execução para confirmar convergência com a baseline.

##### Entregáveis da Fase 4

- Pipeline de remediação com validação e rollback
- Evidência automática de sucesso/falha pós-ação
- Política de bloqueio para comandos de alto risco

#### Fase 5 — Alertas, SLOs e Governança

1. Integrar alertas (e-mail/Slack/Webhook) para incidentes `CRITICAL` e falhas repetidas.
2. Definir SLOs operacionais:
   - Detecção de drift crítico em até 5 min
   - Geração de sugestão de correção em até 2 min
   - Atualização de status em tempo quase real
3. Implementar relatórios executivos e técnicos por período e por cliente.
4. Estabelecer processo de revisão pós-incidente (RCA) para redução de recorrência.

##### Entregáveis da Fase 5

- Matriz de alertas por severidade e canal
- Painel de SLO com tendências
- Relatórios mensais de conformidade e estabilidade

#### Backlog Técnico Prioritário (MVP Dashboard)

1. Criar módulo `core/incident_engine.py` para consolidar eventos em incidentes.
2. Evoluir `core/report_manager.py` para saída operacional consumível por API.
3. Adicionar persistência de incidentes e ações (`core/audit_report.py` + camada de repositório).
4. Criar serviço de remediação controlada (`core/remediation_service.py`).
5. Expor API Flask (`api/`) para dashboard com autenticação e filtros.
6. Criar frontend Flask (`dashboard/`) com telas de overview, lista e detalhe de incidente.
7. Incluir testes de integração para fluxo completo: detecção → sugestão → aprovação → execução → validação.

#### Critérios de Aceite do Dashboard

- Incidente crítico aparece no dashboard em até 1 ciclo de auditoria.
- Operador consegue identificar causa, impacto e ação sugerida sem acesso ao host.
- Remediação exige aprovação quando severidade for `CRITICAL`.
- Toda ação corretiva gera trilha de auditoria e evidência pós-execução.
- Sistema registra falhas de correção sem interromper o pipeline de monitoramento.

## ✅ Critérios de Sucesso (MVP)

- Auditoria executa ponta a ponta para ao menos 1 vendor
- Drift é detectado com saída clara e reproduzível
- Baseline possui validação de schema
- Erros de conexão/parsing são tratados com logs úteis
- Projeto está pronto para expansão de novos drivers

---

## 📎 Licença e Uso

Defina neste bloco o modelo de licenciamento e as restrições de uso comercial conforme a estratégia do projeto.
