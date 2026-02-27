# 🛰️ Project Instructions: SentinelNet_FLS

## 📜 Contexto e Visão Geral

O **SentinelNet_FLS** é uma ferramenta de auditoria contínua de rede baseada em **Infrastructure as Code (IaC)**. O objetivo é comparar o estado real dos ativos (MikroTik, Cisco, etc.) com uma **Fonte Única da Verdade (Baseline JSON)** para detectar **Configuration Drift**.

## 🛠️ Stack Técnica Obrigatória

- **Linguagem:** Python 3.10+ com tipagem estática (type hinting) e PEP8. 

- **Não deixar que as linhas excedam 79 caracteres.**

- **Network:** Netmiko (SSH) e TTP (parsing de CLI para JSON).

- **Data/Validation:** Pydantic para schemas e SQLite para persistência.

- **Web:** Flask (App Factory e Blueprints) e Bootstrap 5 no frontend.

- **Segurança:** Criptografia Fernet para segredos.

---

## 🏗️ Padrões de Arquitetura e Código

1. **Strategy Pattern:** Todos os drivers de fabricantes devem herdar obrigatoriamente da classe abstrata `NetworkDeviceDriver` em `core/base_driver.py`.

2. **Modularidade:** O código deve ser desacoplado entre Coleta, Parsing, Auditoria e Persistência.

3. **App Factory:** O Dashboard Flask deve ser inicializado via `create_app()` com Blueprints separados por domínio.

4. **Uso de Pathlib:** Utilize sempre `pathlib.Path` para manipulação de caminhos, garantindo compatibilidade entre Windows 11 e Kali Linux.

---

## 🛡️ Diretrizes Críticas de Segurança

- **Gestão de Segredos:** NUNCA armazene senhas em texto claro. Use sempre o `VaultManager`.

- **Variável de Ambiente:** A chave mestra deve ser lida de `SENTINEL_MASTER_KEY`.

- **Zero-Leaking em Logs:** O `internalloggin` e o `system_logger` estão terminantemente proibidos de registrar payloads que contenham senhas ou tokens.

- **Mínimo Privilégio:** Os drivers devem priorizar usuários com permissão `read-only` nos ativos.

---

## 📁 Estrutura de Diretórios Referência

Ao criar novos arquivos, siga rigorosamente esta hierarquia:

- `core/`: Schemas Pydantic, motores de Diff e Incidentes.

- `drivers/`: Implementações específicas por fabricante.

- `dashboard/`: Blueprints, templates Jinja2 e arquivos estáticos.

- `inventory/`: SQLite (`sentinel_data.db`) e cofre (`vault.enc`).

- `templates/`: Arquivos `.ttp` para o parser.

- `internalloggin/`: Configuração do `RotatingFileHandler`.

---

## 🔄 Fluxo de Trabalho para Desenvolvimento

1. **Observar:** Verificar se a alteração afeta a integridade dos dados ou a conformidade.

2. **Validar:** Novos dados de rede devem ser processados primeiro pelo TTP e validados pelo Pydantic antes de chegar ao Diff Engine.

3. **Persistir:** Qualquer desvio detectado deve ser enviado ao `IncidentEngine` para registro no SQLite.

4. **UX (Palette 🎨):** Melhorias de interface devem focar em acessibilidade e clareza visual de desvios (Diff) usando Bootstrap 5.

---
# 🛰️ Project Instructions: SentinelNet_FLS

 # 🛰️ Project Instructions: SentinelNet_FLS

 ## 📜 Contexto e Visão Geral

 O **SentinelNet_FLS** é uma ferramenta de auditoria contínua de rede baseada em **Infrastructure as Code (IaC)**. O objetivo é comparar o estado real dos ativos (MikroTik, Cisco, etc.) com uma **Fonte Única da Verdade (Baseline JSON)** para detectar **Configuration Drift**.

 ## 🛠️ Stack Técnica Obrigatória

 *
 **Linguagem:** Python 3.10+ com Tipagem Estática (Type Hinting) e PEP8.

 *
 **Network:** Netmiko (SSH) e TTP (Parsing de CLI para JSON).

 *
 **Data/Validation:** Pydantic para Schemas e SQLite para persistência.

 *
 **Web:** Flask (App Factory e Blueprints) e Bootstrap 5 no Frontend.

 *
 **Segurança:** Criptografia Fernet para segredos.

 ---

 ## 🏗️ Padrões de Arquitetura e Código

 1. 
 **Strategy Pattern:** Todos os drivers de fabricantes devem herdar obrigatoriamente da classe abstrata `NetworkDeviceDriver` em `core/base_driver.py`.

 2. 
 **Modularidade:** O código deve ser desacoplado entre Coleta, Parsing, Auditoria e Persistência.

 3. 
 **App Factory:** O Dashboard Flask deve ser inicializado via `create_app()` com Blueprints separados por domínio.

 4. 
 **Uso de Pathlib:** Utilize sempre `pathlib.Path` para manipulação de caminhos, garantindo compatibilidade entre Windows 11 e Kali Linux.

 ---

 ## 🛡️ Diretrizes Críticas de Segurança

 * **Gestão de Segredos:** NUNCA armazene senhas em texto claro. Use sempre o `VaultManager`.

 *
 **Variável de Ambiente:** A chave mestra deve ser lida de `SENTINEL_MASTER_KEY`.

 *
 **Zero-Leaking em Logs:** O `internalloggin` e o `system_logger` estão terminantemente proibidos de registrar payloads que contenham senhas ou tokens.

 *
 **Mínimo Privilégio:** Os drivers devem priorizar usuários com permissão `read-only` nos ativos.

 ---

 ## 📁 Estrutura de Diretórios Referência

 Ao criar novos arquivos, siga rigorosamente esta hierarquia:

 *
 `core/`: Schemas Pydantic, motores de Diff e Incidentes.

 *
 `drivers/`: Implementações específicas por fabricante.

 *
 `dashboard/`: Blueprints, templates Jinja2 e arquivos estáticos.

 *
 `inventory/`: SQLite (`sentinel_data.db`) e cofre (`vault.enc`).

 *
 `templates/`: Arquivos `.ttp` para o parser.

 *
 `internalloggin/`: Configuração do `RotatingFileHandler`.

 ---

 ## 🔄 Fluxo de Trabalho para Desenvolvimento

 1. 
 **Observar:** Verificar se a alteração afeta a integridade dos dados ou a conformidade.

 2. 
 **Validar:** Novos dados de rede devem ser processados primeiro pelo TTP e validados pelo Pydantic antes de chegar ao Diff Engine.

 3. 
 **Persistir:** Qualquer desvio detectado deve ser enviado ao `IncidentEngine` para registro no SQLite.

 4. 
 **UX (Palette 🎨):** Melhorias de interface devem focar em acessibilidade e clareza visual de desvios (Diff) usando Bootstrap 5.

 ---

## 🔄 Fluxo de Trabalho para Desenvolvimento

1.

**Observar:** Verificar se a alteração afeta a integridade dos dados ou a conformidade.

1.

**Validar:** Novos dados de rede devem ser processados primeiro pelo TTP e validados pelo Pydantic antes de chegar ao Diff Engine.

1.

**Persistir:** Qualquer desvio detectado deve ser enviado ao `IncidentEngine` para registro no SQLite.

1.

**UX (Palette 🎨):** Melhorias de interface devem focar em acessibilidade e clareza visual de desvios (Diff) usando Bootstrap 5.

---
