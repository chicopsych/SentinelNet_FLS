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

2. **Drivers Layer**
	- Implementa conexão/coleta por vendor
	- Isola comandos e diferenças de protocolo
	- Facilita inclusão de novos fabricantes sem alterar o core

3. **Baseline (JSON)**
	- Representa o estado esperado por cliente, site ou dispositivo
	- Pode ser versionado em Git
	- Serve como referência para compliance

4. **Parser (TTP/TextFSM)**
	- Converte CLI textual em estrutura previsível
	- Permite comparação por campos semânticos
	- Reduz ruído de formatação textual

---

## 🧰 Stack Técnica

- **Python 3.10+**
- **Netmiko** (coleta via SSH)
- **TTP / TextFSM** (parsing)
- **Pydantic** (validação de schema)
- **SQLite** (opcional para histórico)
- **Logging nativo do Python + RotatingFileHandler** (observabilidade básica)

---

## 📁 Estrutura do Diretório

```text
SentinelNet_FLS/
├── core/                       # Núcleo da auditoria e contratos base
│   ├── __init__.py
│   ├── base_driver.py
│   └── schemas.py
├── drivers/                    # Drivers por fabricante
│   └── __init__.py
├── internalloggin/             # Logging interno centralizado
│   ├── __init__.py
│   ├── logger.py
│   └── internallogs/           # Arquivos .log gerados pela aplicação
├── inventory/                  # Inventário e dados por cliente
│   ├── customer/
│   │   └── customer.py
│   └── inventorycreator.py
├── logs/                       # Saídas/histórico de execução
├── templates/                  # Templates de parsing (TTP/TextFSM)
├── utils/                      # Utilitários compartilhados
│   └── __init__.py
├── main.py                     # Ponto de entrada da aplicação
├── README.md
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

# 3) Executar auditoria (exemplo)
python main.py
```

### Pré-requisitos

- Acesso de rede aos dispositivos alvo
- Credenciais de leitura válidas
- Baseline JSON definido para os ativos auditados
- Templates de parsing compatíveis com o firmware/versão dos equipamentos

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

Esta sequência prioriza base sólida antes de aumentar o escopo multi-fabricante.

1. [x] **Task 01: Definição do Schema JSON** ✅
   - Modelar entidades (interfaces, rotas, firewall, usuários) com `Pydantic`
   - Definir validações mínimas e campos obrigatórios
   - **Entregável:** `core/schemas.py` — modelos `Interface`, `Route`, `FirewallRule`, `DeviceConfig`

2. [x] **Task 02: Implementação da Classe Abstrata (Driver Base)** ✅
   - Criar contrato comum (`connect`, `get_config_snapshot`, `disconnect`)
   - Padronizar erros e retorno de dados
   - **Entregável:** `core/base_driver.py` — classe `NetworkDeviceDriver(ABC)` com context manager

3. [ ] **Task 03: Desenvolvimento do Driver MikroTik (MVP)**
	- Implementar conexão via `Netmiko`
	- Capturar saída de configuração (`/export`)

4. [ ] **Task 04: Criação dos Templates de Parsing (TTP)**
	- Converter saída textual em JSON normalizado
	- Cobrir blocos críticos do MVP

5. [ ] **Task 05: Construção do Diff Engine**
	- Comparar baseline x estado atual
	- Identificar ausência, adição e alteração de valores

6. [ ] **Task 06: Módulo de Relatório e Logging**
	- ✅ Logging interno centralizado implementado (`internalloggin/logger.py`)
	- ✅ Integração inicial aplicada em `main.py`, `core/base_driver.py` e `inventory/customer/customer.py`
	- Persistir resultados em logs estruturados de auditoria
	- Opcional: persistência em SQLite para histórico

7. [ ] **Task 07: Sistema de Gestão de Credenciais**
	- Integrar variáveis de ambiente/cofre de segredos
	- Garantir uso seguro em ambientes multi-cliente

---

## ✅ Critérios de Sucesso (MVP)

- Auditoria executa ponta a ponta para ao menos 1 vendor
- Drift é detectado com saída clara e reproduzível
- Baseline possui validação de schema
- Erros de conexão/parsing são tratados com logs úteis
- Projeto está pronto para expansão de novos drivers

---

## 📎 Licença e Uso

Defina neste bloco o modelo de licenciamento e as restrições de uso comercial conforme a estratégia do projeto.
