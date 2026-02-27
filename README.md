# 🔍 Lint de Frontend (webhint)

O arquivo de configuração do webhint está em `dashboard/.hintrc`.

Use o comando abaixo para rodar a auditoria com o config correto:

```bash
npx hint "templates/**/*.html" --config dashboard/.hintrc
```

Se preferir validar a aplicação em execução local:

```bash
npx hint http://127.0.0.1:5000 --config dashboard/.hintrc
```

# 🛰️ SentinelNet_FLS

## *Enterprise-Grade Configuration Integrity & Network Compliance Orchestrator*

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python)
![Architecture](https://img.shields.io/badge/Architecture-Strategy%20Pattern-orange?style=for-the-badge)
![Security](https://img.shields.io/badge/Security-AES%20Fernet-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=for-the-badge)

**SentinelNet_FLS** é uma plataforma avançada de auditoria contínua e observabilidade configuracional. Projetado para ambientes de missão crítica, ele implementa os princípios de **Infrastructure as Code (IaC)** para detectar e mitigar o *Configuration Drift* através de uma arquitetura resiliente e agnóstica a fabricantes.

---

## 💎 Proposta de Valor: A "Fonte Única da Verdade"

Em redes modernas, o maior risco de segurança é o ajuste temporário que se torna permanente. O SentinelNet estabelece uma **Baseline Imutável** (Golden Config), garantindo que qualquer alteração não documentada seja detectada, categorizada e neutralizada.

* **Integridade Operacional:** Elimine falhas causadas por comandos manuais fora da janela de manutenção.
* **Segurança Ofensiva (Red Team):** Detecte imediatamente backdoors e regras de firewall suspeitas.
* **Compliance Multitenancy:** Gerencie múltiplos clientes (MSPs) com isolamento total de dados e segredos.

---

## ⚙️ Arquitetura de Próxima Geração

O sistema foi concebido sobre camadas desacopladas, garantindo que o núcleo permaneça estável enquanto novos fabricantes são adicionados via plugins.

### O Ciclo de Vida do Dado

1. **Ingestion Layer:** Drivers especializados (Netmiko) realizam a coleta segura via SSH utilizando validação de fingerprint para mitigar ataques MITM.
2. **Normalization Layer:** Motores **TTP (Template Text Parser)** convertem o caos textual da CLI em objetos JSON estruturados e tipados.
3. **Analysis Engine:** O **Diff Engine Semântico** realiza a comparação lógica bit-a-bit, tratando listas de firewall não apenas como texto, mas como regras ordenadas.
4. **Persistence Layer:** O **Incident Engine** registra desvios no SQLite, mantendo uma trilha histórica para auditoria e remediação futura.

---

## 🛡️ O Modelo de Segurança "Sentinel"

Segurança não é um recurso, é a fundação. O SentinelNet implementa um cofre de credenciais rigoroso.

* **Criptografia em Repouso:** Todas as credenciais de ativos são protegidas com **AES-128 via Fernet (Cryptography)**.
* **Injeção Dinâmica:** A chave mestra de descriptografia (`SENTINEL_MASTER_KEY`) reside apenas na memória volátil, injetada via variáveis de ambiente.
* **Zero-Logging Policy:** Logs internos são sanitizados automaticamente para evitar o vazamento inadvertido de credenciais ou tokens.

---

## 🚀 Tecnologias Core

O projeto utiliza o que há de mais estável e performático no ecossistema Python moderno:

| Tecnologia | Função | Vantagem Estratégica |
| :--- | :--- | :--- |
| **Pydantic** | Validação de Schema | Garante integridade dos dados antes da auditoria. |
| **Netmiko** | Orquestração SSH | Abstração estável para comunicação multi-vendor. |
| **TTP** | Parsing Declarativo | Manutenção simples: mude o template, não o código. |
| **Flask + BS5** | Dashboard Full-stack | Interface executiva com foco em UX e acessibilidade. |

---

## 📂 Organização do Projeto

```text
SentinelNet_FLS/
├── core/               # Inteligência de auditoria, serviços e contratos (ABC)
├── drivers/            # Abstrações de hardware (MikroTik, Cisco, etc)
├── dashboard/          # Interface Frontend Web (Templates & Static)
├── web_api/            # Camada de Controllers e API Flask
├── internalloggin/     # Observabilidade com RotatingFileHandler
├── inventory/          # Baselines imutáveis, SQLite e segredos criptografados
└── templates/          # Inteligência de parsing (TTP Templates)
