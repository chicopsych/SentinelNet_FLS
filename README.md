# 🛰️ SentinelNet_FLS

**Monitoramento de Integridade Configuracional para Redes Críticas**

---

## 📋 O que é?

**SentinelNet_FLS** é uma ferramenta de auditoria contínua que detecta **Configuration Drift** em ambientes de rede, comparando o estado real dos equipamentos com uma **Fonte Única da Verdade (Baseline)** definida em JSON e versionada em Git.

### Propósito

- Automatizar detecção de alterações não autorizadas em ativos críticos
- Gerar trilha de auditoria para conformidade regulatória
- Reduzir riscos de segurança causados por mudanças manuais fora de processo
- Facilitar rastreabilidade multi-cliente em ambientes de MSP

### Use Cases

- **MSP (Managed Service Providers):** auditoria contínua de múltiplos clientes
- **Consultorias de TI:** validação pós-implementação e conformidade operacional
- **Equipes de Infraestrutura:** detecção automática de Configuration Drift
- **DevOps/NetOps:** IaC para redes (Network as Code principles)

---

## 🔄 Como Funciona

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  1. INVENTÁRIO (JSON / SQLite)                         │
│     └─ Define dispositivos, clientes, credenciais      │
│                                                         │
│  2. COLETA (SSH/API via Driver)                        │
│     └─ Conecta aos ativos, extrai running config      │
│                                                         │
│  3. PARSING (TTP/TextFSM)                              │
│     └─ Converte CLI textual em JSON estruturado        │
│                                                         │
│  4. DIFF (Comparison Engine)                           │
│     └─ Baseline vs Estado Atual → Desvios             │
│                                                         │
│  5. AUDITORIA (SQLite + Relatórios)                   │
│     └─ Persiste incidentes com contexto e severidade   │
│                                                         │
│  6. DASHBOARD (Flask Web UI)                           │
│     └─ Operadores visualizam, aprovam e remediam       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Stack Técnica

- **Python 3.10+** — Tipagem estática, PEP8
- **Netmiko** — Coleta via SSH
- **TTP** — Parsing de CLI para JSON
- **Pydantic** — Validação de schema
- **Flask** — API e Dashboard
- **SQLite** — Histórico e persistência
- **Fernet** — Criptografia de credenciais

---

## 🚀 QuickStart

### 1. Pré-requisitos

- Python 3.10+
- Acesso SSH (read-only) aos dispositivos alvo
- Git (para versionamento de baselines)

### 2. Instalação

```bash
# Clonar repositório
git clone https://github.com/chicopsych/SentinelNet_FLS.git
cd SentinelNet_FLS

# Criar e ativar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt
```

### 3. Configuração Segura de Credenciais

```bash
# Gerar Master Key para criptografia
python3 -c "
from cryptography.fernet import Fernet
import os

key = Fernet.generate_key().decode()
with open('.env', 'w') as f:
    f.write(f'SENTINEL_MASTER_KEY={key}\n')
print(f'✅ Master Key criada:\n{key[:30]}...')
"

# Verificar carregamento
python3 -c "
from dotenv import load_dotenv
import os
load_dotenv()
key = os.getenv('SENTINEL_MASTER_KEY')
print(f'✅ Carregado: {key[:30]}...' if key else '❌ Não encontrado')
"
```

### 4. Iniciar Dashboard

```bash
# Desenvolvimento (com hot-reload)
python run.py
# Acesse: http://127.0.0.1:5000

# Produção (debug desativado)
FLASK_ENV=production python run.py
```

### 5. Usar via Dashboard

1. **Descobrir Ativos:** `GET /devices/discover` → insira faixa CIDR
2. **Cadastrar Dispositivo:** `GET /devices/onboard` → preencha dados + credenciais
3. **Executar Auditoria:** `main.py` coleta configs no background
4. **Visualizar Incidentes:** `GET /incidents` → filtre por severidade, cliente
5. **Remediar:** Clique em incidente → visualize diff → aprove correção

### 6. Executar Auditoria CLI (opcional)

```bash
# Coleta, parseia e compara com baseline
python main.py

# Resultados em: logs/, inventory/reports/
```

---

## 📁 Estrutura Básica

- **`core/`** — Schemas, diff engine, auditoria
- **`drivers/`** — Implementações por fabricante (MikroTik, etc.)
- **`dashboard/`** — API Flask + templates web
- **`inventory/`** — Baselines JSON, credenciais criptografadas
- **`templates/`** — Parsers TTP para cada comando
- **`main.py`** — Ponto de entrada CLI
- **`run.py`** — Ponto de entrada Dashboard

---

## 🛡️ Segurança

- ✅ Credenciais **criptografadas** com Fernet (no arquivo `vault.enc`)
- ✅ Master Key via **variável de ambiente** (`.env`)
- ✅ **Zero hardcoding** de secrets no repositório
- ✅ **Git hooks** bloqueiam commit de secrets
- ✅ **Logs sanitizados** (sem exposição de senhas)
- ✅ **Mínimo privilégio** — contas read-only recomendadas

Para detalhes, consulte [SECURITY.md](SECURITY.md) e [docs/configuracao-vault.md](docs/configuracao-vault.md).

---

## 📌 Endpoints Principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/health/overview` | Painel executivo com KPIs |
| `GET` | `/devices` | Lista de ativos cadastrados |
| `POST` | `/devices/discover` | Discovery de ativos (nmap) |
| `POST` | `/devices/onboard` | Cadastrar novo ativo |
| `GET` | `/incidents` | Lista de desvios detectados |
| `GET` | `/incidents/<id>` | Detalhe com diff baseline vs atual |
| `POST` | `/incidents/<id>/remediation/ui/approve` | Aprovar correção |
| `POST` | `/incidents/<id>/remediation/ui/execute` | Executar remediação |

---

## 🔧 Próximos Passos

1. **Adicionar baseline para seus ativos:**
   ```bash
   cp inventory/baselines/cliente_a/borda-01.json inventory/baselines/seu_cliente/seu_ativo.json
   # Editar com valores esperados
   ```

2. **Cadastrar ativos no dashboard** via `/devices/onboard`

3. **Executar primeira auditoria:**
   ```bash
   python main.py
   ```

4. **Visualizar resultados** em `http://127.0.0.1:5000/incidents`

---

## 📚 Documentação Completa

Para detalhes sobre arquitetura, roadmap, fases do dashboard, integração com IA e tarefas em andamento, consulte **[PROJECT_CONTROL.md](PROJECT_CONTROL.md)** (arquivo pessoal de gerenciamento do projeto).

- [SECURITY.md](SECURITY.md) — Políticas e controles de segurança
- [docs/configuracao-vault.md](docs/configuracao-vault.md) — Setup completo do cofre de credenciais

---

## 📄 Licença

Distribuído sob a licença **MIT**. Ver arquivo [LICENSE](LICENSE).

---

**Desenvolvido com foco em auditoria contínua, segurança de credenciais e rastreabilidade operacional.**
