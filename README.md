# 🛰️ SentinelNet_FLS

## *Enterprise-Grade Configuration Integrity & Network Compliance Orchestrator*

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python)
![Architecture](https://img.shields.io/badge/Architecture-Strategy%20Pattern-orange?style=for-the-badge)
![Security](https://img.shields.io/badge/Security-AES%20Fernet-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=for-the-badge)

[cite_start]**SentinelNet_FLS** é uma plataforma avançada de auditoria contínua e observabilidade configuracional[cite: 163, 195]. [cite_start]Projetado para ambientes de missão crítica, ele implementa os princípios de **Infrastructure as Code (IaC)** para detectar e mitigar o *Configuration Drift* através de uma arquitetura resiliente e agnóstica a fabricantes[cite: 4, 7, 56, 165].

---

## 💎 Proposta de Valor: A "Fonte Única da Verdade"

[cite_start]Em redes modernas, o maior risco de segurança é o ajuste temporário que se torna permanente[cite: 16]. [cite_start]O SentinelNet estabelece uma **Baseline Imutável** (Golden Config), garantindo que qualquer alteração não documentada seja detectada, categorizada e neutralizada[cite: 3, 55, 164, 196].

* [cite_start]**Integridade Operacional:** Elimine falhas causadas por comandos manuais fora da janela de manutenção[cite: 166, 198].
* **Segurança Ofensiva (Red Team):** Detecte imediatamente backdoors e regras de firewall suspeitas[cite: 165, 197].
* [cite_start]**Compliance Multitenancy:** Gerencie múltiplos clientes (MSPs) com isolamento total de dados e segredos[cite: 32, 173, 210].

---

## ⚙️ Arquitetura de Próxima Geração

[cite_start]O sistema foi concebido sobre camadas desacopladas, garantindo que o núcleo permaneça estável enquanto novos fabricantes são adicionados via plugins[cite: 30, 61, 170, 207].

### O Ciclo de Vida do Dado

1. [cite_start]**Ingestion Layer:** Drivers especializados (Netmiko) realizam a coleta segura via SSH utilizando validação de fingerprint para mitigar ataques MITM[cite: 9, 57, 65, 171].
2. [cite_start]**Normalization Layer:** Motores **TTP (Template Text Parser)** convertem o caos textual da CLI em objetos JSON estruturados e tipados[cite: 40, 58, 63, 171].
3. [cite_start]**Analysis Engine:** O **Diff Engine Semântico** realiza a comparação lógica bit-a-bit, tratando listas de firewall não apenas como texto, mas como regras ordenadas[cite: 11, 59, 171, 232, 255].
4. [cite_start]**Persistence Layer:** O **Incident Engine** registra desvios no SQLite, mantendo uma trilha histórica para auditoria e remediação futura[cite: 74, 172, 321, 343].

---

## 🛡️ O Modelo de Segurança "Sentinel"

Segurança não é um recurso, é a fundação. [cite_start]O SentinelNet implementa um cofre de credenciais rigoroso[cite: 43, 66, 210, 281].

* [cite_start]**Criptografia em Repouso:** Todas as credenciais de ativos são protegidas com **AES-128 via Fernet (Cryptography)**[cite: 284, 289, 300].
* **Injeção Dinâmica:** A chave mestra de descriptografia (`SENTINEL_MASTER_KEY`) reside apenas na memória volátil, injetada via variáveis de ambiente[cite: 285, 292, 299].
* [cite_start]**Zero-Logging Policy:** Logs internos são sanitizados automaticamente para evitar o vazamento inadvertido de credenciais ou tokens[cite: 32, 293, 301].

---

## 🚀 Tecnologias Core

[cite_start]O projeto utiliza o que há de mais estável e performático no ecossistema Python moderno[cite: 171, 208]:

| Tecnologia | Função | Vantagem Estratégica |
| :--- | :--- | :--- |
| **Pydantic** | Validação de Schema | [cite_start]Garante integridade dos dados antes da auditoria[cite: 88, 171, 199]. |
| **Netmiko** | Orquestração SSH | [cite_start]Abstração estável para comunicação multi-vendor[cite: 9, 171, 209]. |
| **TTP** | Parsing Declarativo | [cite_start]Manutenção simples: mude o template, não o código[cite: 42, 112, 171]. |
| **Flask + BS5** | Dashboard Full-stack | [cite_start]Interface executiva com foco em UX e acessibilidade[cite: 329, 435, 436]. |

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
