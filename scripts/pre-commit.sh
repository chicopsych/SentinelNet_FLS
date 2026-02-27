#!/bin/bash
# .git/hooks/pre-commit
# ════════════════════════════════════════════════════════════════════════════════
# Hook: Bloquear commits que tentam adicionar secrets (senhas, tokens, chaves)
#
# Instalação:
#   cp scripts/pre-commit.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Bypass (último recurso, não recomendado):
#   git commit --no-verify
# ════════════════════════════════════════════════════════════════════════════════

set -e

# Cores para output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Padrões perigosos que nunca devem ir para o repositório
FORBIDDEN_PATTERNS=(
    # Variáveis de ambiente com valores
    'SENTINEL_MASTER_KEY\s*=\s*["\'\`]?.+'
    'API_STATIC_TOKEN\s*=\s*["\'\`]?.+'
    'PASSWORD\s*=\s*["\'\`]?.+'
    'SECRET\s*=\s*["\'\`]?.+'
    'TOKEN\s*=\s*["\'\`]?.+'
    'API_KEY\s*=\s*["\'\`]?.+'
    'PRIVATE_KEY\s*=\s*["\'\`]?.+'
    
    # Padrões comuns de senha
    'password\s*:\s*["\'].*["\']'
    'passwd\s*:\s*["\'].*["\']'
    'pwd\s*:\s*["\'].*["\']'
    
    # Certificados e chaves PEM/DER
    '-----BEGIN\s(RSA\s)?PRIVATE\sKEY-----'
    '-----BEGIN\sCERTIFICATE-----'
    
    # Arquivo .env com valores
    'SENTINEL_MASTER_KEY=.+'
)

# Extensões perigosas
DANGEROUS_EXTENSIONS=(
    'pem'
    'key'
    'crt'
    'cer'
    'p12'
    'pfx'
    'jks'
)

echo -e "${YELLOW}🔍 Verificando secrets...${NC}"

FOUND_SECRETS=0

# Verificar arquivos staged
while IFS= read -r file; do
    # Ignorar arquivos que devem estar no gitignore (não devem ser detectados aqui)
    if [[ "$file" =~ \.git/hooks/ ]] || [[ "$file" =~ venv/ ]] || [[ "$file" =~ __pycache__/ ]]; then
        continue
    fi
    
    # Verificar extensões perigosas
    for ext in "${DANGEROUS_EXTENSIONS[@]}"; do
        if [[ "$file" == *".$ext" ]]; then
            echo -e "${RED}❌ ERRO: Arquivo com extensão perigosa ($ext) não pode ser versionado!${NC}"
            echo -e "   Arquivo: $file"
            FOUND_SECRETS=1
        fi
    done
    
    # Verificar padrões de secret no conteúdo
    for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
        if git show ":$file" 2>/dev/null | grep -qP "$pattern"; then
            echo -e "${RED}❌ ERRO: Arquivo contém padrão de secret!${NC}"
            echo -e "   Arquivo: $file"
            echo -e "   Padrão detectado: $pattern"
            FOUND_SECRETS=1
        fi
    done
done < <(git diff --cached --name-only)

if [ $FOUND_SECRETS -eq 1 ]; then
    echo ""
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  ⛔ COMMIT BLOQUEADO: SECRETS DETECTADOS!${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Você está tentando fazer commit de informações sensíveis!"
    echo ""
    echo "Ações recomendadas:"
    echo "  1. git reset HEAD <arquivo>     # remover do stage"
    echo "  2. Remova credenciais / secrets do arquivo"
    echo "  3. git add <arquivo>            # re-add sem secrets"
    echo "  4. git commit                   # tente novamente"
    echo ""
    echo "Se for uma chave legítima do projeto (ex: .env.example):"
    echo "  - Renomeie para .env.example ou .env.sample"
    echo "  - Use placeholders em vez de valores reais"
    echo "  - Adicione ao .gitignore: '$(basename $file)'"
    echo ""
    exit 1
fi

# Avisos para arquivos .env (mesmo que em exemplo)
while IFS= read -r file; do
    if [[ "$file" == *.env* ]] && [[ "$file" != *.env.example* ]]; then
        echo -e "${YELLOW}⚠️  AVISO: Arquivo .env detectado!${NC}"
        echo -e "   Arquivo: $file"
        echo "   Certifique-se de que não contém valores reais de secrets."
    fi
done < <(git diff --cached --name-only)

echo -e "${GREEN}✅ Nenhum secret detectado — commit pode prosseguir${NC}"
exit 0
