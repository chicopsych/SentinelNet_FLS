# 🛡️ Política de Segurança — SentinelNet_FLS

## Relatar Vulnerabilidades com Responsabilidade

Se você descobrir uma vulnerabilidade de segurança no SentinelNet_FLS,  
**por favor não publique em Issues públicas**. Em vez disso:

1. **Envie um email** para: chicopsych@protonmail.com
   - Assunto: `[SECURITY] Vulnerabilidade em SentinelNet_FLS`
   - Inclua descrição, passos para reproduzir e impacto estimado

2. **Aguarde resposta** em até 48 horas (máximo 7 dias úteis)

3. **Coordene a divulgação** — trabalharemos juntos para:
   - Confirmar e avaliar a severidade
   - Desenvolver e testar um patch
   - Preparar uma divulgação responsável

> **Não será feito nenhum retardo intencional na divulgação  
> após a correção estar pronta e testada.**

---

## Estrutura de Segurança do Projeto

### 🔐 Proteção de Credenciais

**Decisão de Design:** Nenhuma credencial é armazenada em texto claro  
no repositório ou em arquivos de configuração.

1. **Credenciais de Dispositivos:**
   - Armazenadas no cofre criptografado (`inventory/vault.enc`)
   - Criptografia: **AES-128-CBC** (Fernet da `cryptography` library)
   - Master Key: variável de ambiente `SENTINEL_MASTER_KEY`
   - Master Key NUNCA aparece em código, logs ou arquivo `.env` versionado

2. **Tokens de API:**
   - Tokens administrativos: variável de ambiente `API_STATIC_TOKEN`
   - Passados via headers `X-API-Token` (não em query string)
   - Validados antes de cada operação sensível

3. **Chaves SSH / Certificados:**
   - Não incluidas no repositório (`.gitignore`)
   - Gerenciadas pelo usuário em ambiente seguro

---

### 🚫 O que NUNCA será aceito no repositório

- [ ] Senhas em texto claro (em código ou arquivos)
- [ ] Chaves privadas (`.key`, `.pem`, `.pfx`)
- [ ] Tokens de API ou JWT
- [ ] Certificados SSL/TLS
- [ ] Arquivos `.env` ou `.env.*` com valores reais
- [ ] Dados de cliente (IPs reais, hostnames, configurações sensíveis)
- [ ] Banco de dados SQLite com credenciais (`sentinel_data.db`)
- [ ] Logs que possam conter informações sensíveis

---

### ✅ Boas Práticas de Segurança Implementadas

1. **Sanitização de Logs:**
   - Senhas e tokens nunca são registrados
   - Função `_sanitize_error()` remove dados sensíveis antes de logar

2. **Validação de Entrada:**
   - Pydantic valida schemas de todos os dados de entrada
   - Ranges CIDR validados (máximo /20 para discovery nmap)

3. **Separação de Privilégios:**
   - Endpoints sensiveis (`/admin/*`, `/remediation/api/*`) requerem token
   - Operações de remediação exigem aprovação explícita

4. **Context Managers:**
   - Conexões SSH encerradas automaticamente (`with` statement)
   - Recursos de rede liberados mesmo em caso de erro

5. **Tratamento de Erros:**
   - Mensagens de erro não expõem detalhes internos ao cliente
   - Stack traces apenas em logs internos (not exposed to users)

---

## Configuração Segura para Produção

### Variáveis de Ambiente Obrigatórias

```bash
# Master Key do cofre de credenciais (gere com: python -m utils.vault_setup generate-key)
SENTINEL_MASTER_KEY=<chave-fernet-aqui>

# Token estático para API admin (gere com: python3 -c "import secrets; print(secrets.token_urlsafe(32))")
API_STATIC_TOKEN=<token-aqui>

# Ambiente de execução
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### Arquivo `.env` em Desenvolvimento

1. Crie o `.env` **apenas em desenvolvimento**, nunca fazer deploy
2. O `.env` está no `.gitignore` — não será versionado
3. Gere uma **chave nova para cada ambiente** (dev, staging, prod)

```bash
# No desenvolvimento local (.env local — não versionar!)
SENTINEL_MASTER_KEY=sua_chave_desenvolvimento_aqui
API_STATIC_TOKEN=seu_token_desenvolvimento_aqui
```

### Produção: Injetar via Ambiente do SO

**Nunca use arquivo `.env` em produção.**  
Injete variáveis diretamente:

#### systemd

```ini
# /etc/systemd/system/sentinelnet.service
[Service]
Environment="SENTINEL_MASTER_KEY=CHAVE_SEGURA_AQUI"
Environment="API_STATIC_TOKEN=TOKEN_SEGURO_AQUI"
Environment="FLASK_ENV=production"
ExecStart=/opt/sentinelnet/venv/bin/python main.py server
```

#### Docker / docker-compose

```yaml
services:
  sentinelnet:
    image: sentinelnet:latest
    environment:
      SENTINEL_MASTER_KEY: "${SENTINEL_MASTER_KEY}"  # lê do host
      API_STATIC_TOKEN: "${API_STATIC_TOKEN}"
      FLASK_ENV: production
```

```bash
# Executar:
docker run -e SENTINEL_MASTER_KEY="$SENTINEL_MASTER_KEY" sentinelnet
```

---

## Gestão de Chaves e Secrets

### Master Key (SENTINEL_MASTER_KEY)

**Geração:**
```bash
python -m utils.vault_setup generate-key
```

**Armazenamento seguro:**
- [ ] Gerenciador de senhas corporativo (Bitwarden, 1Password)
- [ ] Secrets da CI/CD (GitHub Secrets, GitLab Variables, etc.)
- [ ] HSM / KMS em escala enterprise (AWS KMS, Azure Key Vault)
- [ ] Nunca em texto claro no disco

**Backup:**
- [ ] Armazene em duplicate em local seguro separado do código
- [ ] Teste a recuperação periodicamente
- [ ] Se perdida, o cofre `vault.enc` se torna irrecuperável

### API Token (API_STATIC_TOKEN)

**Geração:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Rotação recomendada:** a cada 90 dias em produção

---

## Auditoria e Compliance

### Checklist Pré-Deploy

- [ ] Não há `.env` com dados reais nos commits
- [ ] `vault.enc` não foi versionado
- [ ] Nenhum arquivo `.key`, `.pem` ou `.crt` no repo
- [ ] Logs não contêm senhas ou tokens (validar com grep)
- [ ] Variáveis de ambiente estão configuradas no servidor
- [ ] Certificados SSL/TLS estão em vigência
- [ ] Backups da Master Key existem em local seguro

### Verificação de Secrets no Código

```bash
# Procurar padrões suspeitos (rodar antes de push)
grep -r "password\|token\|secret\|API_KEY" --include="*.py" --include="*.json" \
  --exclude-dir=venv --exclude-dir=__pycache__ .
```

### Logs de Auditoria

Todos os acessos ao banco de dados e alterações de configuração são registrados:
- Arquivo: `internalloggin/internallogs/SentinelNet_FLS.log`
- Retenção: 13 backups rotativos (tamanho máximo: 5 MB cada)
- Nunca contêm senhas — apenas `customer_id` e `device_id`

---

## Dependências Seguras

O projeto usa bibliotecas amplamente auditadas:

| Biblioteca | Segurança |
|---|---|
| `cryptography` | Mantida pela comunidade OpenStack, auditada regularmente |
| `flask` | Framework maduro, patches de segurança rápidos |
| `pydantic` | Validação robusta contra injeção |
| `netmiko` | Baseado em Paramiko (SSH bem testado) |
| `pysnmp` | Código legado bem establecido |

**Manter atualizado:**
```bash
pip install --upgrade -r requirements.txt
pip-audit  # verificar vulnerabilidades conhecidas
```

---

## Relatório de Segurança Anterior

- ✅ Nenhuma credencial hardcoded detectada
- ✅ Senhas sempre saltadas para o Vault
- ✅ Logs sanitizados (sem exposição de secrets)
- ✅ `.env` e `vault.enc` no `.gitignore`
- ✅ Context managers previnem vazamento de recursos

---

## Contatos e Suporte

- **Segurança:** chicopsych@protonmail.com
- **Documentação:** Veja [docs/configuracao-vault.md](docs/configuracao-vault.md)
- **Issues públicas:** Apenas bugs não-sensíveis no GitHub

---

**Última atualização:** 26 de fevereiro de 2026

_Obrigado por ajudar a manter o SentinelNet_FLS seguro! 🛡️_
