# Configuração do Cofre de Credenciais — SentinelNet_FLS

## O que é e por quê existe

O SentinelNet_FLS nunca armazena senhas de dispositivos em texto claro.  
Todas as credenciais ficam em `inventory/vault.enc` — um arquivo criptografado  
com **AES-128-CBC** (Fernet). Para abrir esse cofre é necessária uma **Master Key**  
que existe **somente** como variável de ambiente (`SENTINEL_MASTER_KEY`).

> **Regra de ouro:** a Master Key não fica no código, não fica em arquivo
> que vai para o Git, e não fica no banco de dados. Ela vive no ambiente
> de execução do servidor.

---

## Pré-requisitos

- Python 3.10+ instalado
- Ambiente virtual ativo (`source venv/bin/activate`)
- Dependência `cryptography` instalada (`pip install -r requirements.txt`)

---

## Passo a Passo (instalação em um cliente novo)

### Passo 1 — Gerar a Master Key

```bash
python -m utils.vault_setup generate-key
```

Saída esperada:

```
════════════════════════════════════════════════════════════════
  NOVA MASTER KEY (Fernet / AES-128-CBC)
════════════════════════════════════════════════════════════════

  CHAVE_GERADA_NO_AMBIENTE_LOCAL

  INSTRUÇÕES:
  1. Copie a chave acima.
  2. Configure a variável de ambiente:
    export SENTINEL_MASTER_KEY="CHAVE_GERADA_NO_AMBIENTE_LOCAL"
  3. Para persistir, adicione a linha acima ao seu ~/.bashrc
     ou ~/.zshrc (ou use um .env com dotenv).
  4. NUNCA versione esta chave no Git.
════════════════════════════════════════════════════════════════
```

> Cada instalação em cliente diferente deve ter sua **própria** Master Key.  
> Nunca reutilize a mesma chave entre ambientes.

---

### Passo 2 — Criar o arquivo `.env`

Na raiz do projeto crie o arquivo `.env` (ele já está no `.gitignore`):

```bash
# No diretório raiz do projeto:
cat > .env << 'EOF'
SENTINEL_MASTER_KEY=cole_aqui_a_chave_gerada_no_passo_1
EOF
```

Exemplo real:

```
SENTINEL_MASTER_KEY=CHAVE_GERADA_NO_AMBIENTE_LOCAL
```

> O `.env` serve para desenvolvimento local. Em produção prefira
> injetar a variável de ambiente direto no servidor (systemd, Docker,
> Heroku Config Vars, etc.) — veja a seção **Produção** mais abaixo.

---

### Passo 3 — Instalar `python-dotenv` e carregar o `.env` no `main.py`

```bash
pip install python-dotenv
pip freeze | grep python-dotenv >> requirements.txt
```

O `main.py` já carrega o `.env` automaticamente ao iniciar o servidor.
O trecho relevante:

```python
# main.py → run_server() já faz isso internamente
from dotenv import load_dotenv
load_dotenv()          # lê .env e injeta as variáveis no os.environ
```

O servidor é iniciado com:

```bash
python main.py server
```

> `load_dotenv()` sem argumento procura o arquivo `.env` automaticamente
> a partir do diretório de trabalho. Se executar de outro diretório,
> passe o caminho explícito:
> `load_dotenv(Path(__file__).parent / ".env")`

---

### Passo 4 — Verificar se a variável está sendo lida

```bash
# Com o .env criado e dotenv instalado:
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('SENTINEL_MASTER_KEY', 'NÃO DEFINIDA'))"
```

Se retornar a chave (não "NÃO DEFINIDA"), está tudo certo.

---

### Passo 5 — Adicionar as credenciais do primeiro dispositivo

```bash
# A variável de ambiente precisa estar definida (pelo .env ou export)
python -m utils.vault_setup add --customer cliente_a --device borda-01
```

O script pedirá interativamente:

```
  Adicionando credenciais: customer='cliente_a', device='borda-01'
  (A senha NÃO será exibida no terminal)

  Host (IP ou hostname): 192.168.88.1
  Username SSH: admin
  Password SSH: ********
  Porta SSH [22]:
```

O cofre `inventory/vault.enc` será criado automaticamente na primeira vez.

---

### Passo 6 — Confirmar que o cofre foi criado

```bash
python -m utils.vault_setup list
```

Saída esperada:

```
══════════════════════════════════════════
  INVENTÁRIO DO COFRE (sem senhas)
══════════════════════════════════════════

  Customer: cliente_a
    ├─ borda-01: host=192.168.88.1, user=admin, port=22

══════════════════════════════════════════
```

---

### Passo 7 — Iniciar o dashboard

```bash
python main.py server
```

O erro `SENTINEL_MASTER_KEY não está configurada` deixará de aparecer.

---

## Resumo dos comandos (checklist de instalação)

```bash
# 1. Entrar no diretório do projeto
cd /caminho/para/SentinelNet_FLS

# 2. Ativar o ambiente virtual
source venv/bin/activate

# 3. Instalar dependências (incluindo dotenv)
pip install -r requirements.txt

# 4. Gerar Master Key
python -m utils.vault_setup generate-key

# 5. Criar .env com a chave gerada
echo 'SENTINEL_MASTER_KEY=COLE_A_CHAVE_AQUI' > .env

# 6. Adicionar primeiro dispositivo ao cofre
python -m utils.vault_setup add --customer CLIENTE --device DEVICE

# 7. Verificar cofre
python -m utils.vault_setup list

# 8. Iniciar dashboard
python main.py server
```

---

## Produção (sem arquivo `.env`)

Em servidores de produção injete a variável diretamente no ambiente de execução.  
Nunca faça deploy do arquivo `.env`.

### systemd

```ini
# /etc/systemd/system/sentinelnet.service
[Service]
Environment="SENTINEL_MASTER_KEY=sua_chave_aqui"
ExecStart=/opt/sentinelnet/venv/bin/python main.py server
WorkingDirectory=/opt/sentinelnet
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart sentinelnet
```

### Docker

```dockerfile
# Dockerfile
ENV SENTINEL_MASTER_KEY=""   # não coloque o valor aqui!
```

```bash
# Passar em runtime:
docker run -e SENTINEL_MASTER_KEY="sua_chave" sentinelnet
```

Ou via `docker-compose.yml`:

```yaml
services:
  sentinelnet:
    image: sentinelnet
    environment:
      SENTINEL_MASTER_KEY: "${SENTINEL_MASTER_KEY}"   # lê do shell do host
```

### Variável de sessão (desenvolvimento rápido, sem .env)

```bash
export SENTINEL_MASTER_KEY="sua_chave_aqui"
python main.py server
```

> Para tornar permanente adicione o `export` ao `~/.zshrc` ou `~/.bashrc`
> e execute `source ~/.zshrc`.

---

## Backup da Master Key

A Master Key deve ser armazenada em local seguro separado do código:

- Gerenciador de senhas da empresa (Bitwarden, 1Password, etc.)
- Secrets da plataforma de CI/CD (GitHub Secrets, GitLab Variables)
- HSM ou KMS (AWS KMS, Azure Key Vault) em ambientes enterprise

> Se a Master Key for perdida, o cofre `vault.enc` se torna
> **irrecuperável**. Será necessário recriar o cofre e recadastrar
> todas as credenciais.

---

## Segurança: o que proteger e o que não proteger

| Arquivo / dado | Vai para o Git? | Ação |
|---|---|---|
| `inventory/vault.enc` | ❌ Não (`.gitignore`) | Backup manual seguro |
| `.env` | ❌ Não (`.gitignore`) | Nunca versionar |
| `SENTINEL_MASTER_KEY` (variável) | ❌ Nunca | Armazenar em secrets manager |
| `requirements.txt` | ✅ Sim | Versionar normalmente |
| `utils/vault_setup.py` | ✅ Sim | Código público, sem segredos |
