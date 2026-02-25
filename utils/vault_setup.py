"""
utils/vault_setup.py
────────────────────
Script utilitário CLI para gerenciar o cofre de credenciais do SentinelNet_FLS.

Uso:
    python -m utils.vault_setup generate-key
    python -m utils.vault_setup add --customer CUSTOMER_ID --device DEVICE_ID
    python -m utils.vault_setup list
    python -m utils.vault_setup list --customer CUSTOMER_ID

Exemplos:
    # 1. Gerar uma nova Master Key (copie para sua variável de ambiente)
    python -m utils.vault_setup generate-key

    # 2. Exportar a Master Key no ambiente (sessão atual)
    export SENTINEL_MASTER_KEY="sua-chave-aqui"

    # 3. Adicionar credenciais de um dispositivo
    python -m utils.vault_setup add --customer cliente_a --device borda-01

    # 4. Listar customers e devices no cofre
    python -m utils.vault_setup list

Segurança:
    - A senha é lida via getpass (não aparece no terminal).
    - A Master Key NUNCA é salva em arquivo pelo script.
    - O script NUNCA loga senhas — apenas customer_id e device_id.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import NoReturn

from cryptography.fernet import Fernet


def _cmd_generate_key(args: argparse.Namespace) -> None:
    """Gera e exibe uma nova Master Key Fernet."""
    key = Fernet.generate_key().decode("utf-8")
    print("\n" + "═" * 64)
    print("  NOVA MASTER KEY (Fernet / AES-128-CBC)")
    print("═" * 64)
    print(f"\n  {key}\n")
    print("  INSTRUÇÕES:")
    print("  1. Copie a chave acima.")
    print("  2. Configure a variável de ambiente:")
    print(f'     export SENTINEL_MASTER_KEY="{key}"')
    print("  3. Para persistir, adicione a linha acima ao seu ~/.bashrc")
    print("     ou ~/.zshrc (ou use um .env com dotenv).")
    print("  4. NUNCA versione esta chave no Git.")
    print("═" * 64 + "\n")


def _cmd_add(args: argparse.Namespace) -> None:
    """Adiciona ou atualiza credenciais de um dispositivo no cofre."""
    # Import aqui para evitar erro se SENTINEL_MASTER_KEY não estiver definida
    # ao rodar apenas 'generate-key'
    from utils.vault import VaultManager, VaultError, MasterKeyNotFoundError

    customer_id: str = args.customer
    device_id: str = args.device

    print(f"\n  Adicionando credenciais: customer='{customer_id}', device='{device_id}'")
    print("  (A senha NÃO será exibida no terminal)\n")

    host = input("  Host (IP ou hostname): ").strip()
    if not host:
        print("  ERRO: Host não pode ser vazio.", file=sys.stderr)
        sys.exit(1)

    username = input("  Username SSH: ").strip()
    if not username:
        print("  ERRO: Username não pode ser vazio.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("  Password SSH: ")
    if not password:
        print("  ERRO: Password não pode ser vazio.", file=sys.stderr)
        sys.exit(1)

    port_str = input("  Porta SSH [22]: ").strip()
    port = int(port_str) if port_str else 22

    try:
        vault = VaultManager()
    except MasterKeyNotFoundError as exc:
        print(f"\n  ERRO: {exc}", file=sys.stderr)
        sys.exit(1)

    # Carrega payload existente ou cria novo
    existing_data: dict = {}
    if vault.vault_exists():
        try:
            # Descriptografa o cofre inteiro para mesclar
            existing_data = vault._decrypt_vault()
        except VaultError as exc:
            print(f"\n  ERRO ao ler cofre existente: {exc}", file=sys.stderr)
            sys.exit(1)

    # Mescla novas credenciais
    if customer_id not in existing_data:
        existing_data[customer_id] = {}

    existing_data[customer_id][device_id] = {
        "host": host,
        "username": username,
        "password": password,
        "port": port,
    }

    # Salva de volta no cofre
    try:
        vault.encrypt_payload(existing_data)
    except VaultError as exc:
        print(f"\n  ERRO ao salvar cofre: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  ✓ Credenciais salvas para '{customer_id}/{device_id}'.")
    print(f"  Cofre: {vault._vault_path}\n")


def _cmd_list(args: argparse.Namespace) -> None:
    """Lista customers e devices no cofre (sem exibir senhas)."""
    from utils.vault import VaultManager, VaultError, MasterKeyNotFoundError

    try:
        vault = VaultManager()
    except MasterKeyNotFoundError as exc:
        print(f"\n  ERRO: {exc}", file=sys.stderr)
        sys.exit(1)

    if not vault.vault_exists():
        print("\n  Cofre não encontrado. Use 'add' para criar o primeiro registro.\n")
        sys.exit(0)

    try:
        customers = vault.list_customers()
    except VaultError as exc:
        print(f"\n  ERRO: {exc}", file=sys.stderr)
        sys.exit(1)

    if not customers:
        print("\n  Cofre vazio — nenhum customer cadastrado.\n")
        sys.exit(0)

    specific_customer: str | None = getattr(args, "customer", None)

    print("\n" + "═" * 50)
    print("  INVENTÁRIO DO COFRE (sem senhas)")
    print("═" * 50)

    for cid in sorted(customers):
        if specific_customer and cid != specific_customer:
            continue

        devices = vault.list_devices(cid)
        print(f"\n  Customer: {cid}")

        if not devices:
            print("    (nenhum device cadastrado)")
            continue

        for did in sorted(devices):
            creds = vault.get_credentials(cid, did)
            # Exibe host, username e porta — NUNCA a senha
            print(
                f"    ├─ {did}: "
                f"host={creds.get('host', '?')}, "
                f"user={creds.get('username', '?')}, "
                f"port={creds.get('port', 22)}"
            )

    print("\n" + "═" * 50 + "\n")


def main() -> None:
    """Ponto de entrada do CLI de gestão do cofre."""
    parser = argparse.ArgumentParser(
        prog="vault_setup",
        description="SentinelNet_FLS — Gestão do cofre de credenciais criptografado.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # ── generate-key ──────────────────────────────────────────────────────
    subparsers.add_parser(
        "generate-key",
        help="Gera uma nova Master Key Fernet (AES-128-CBC).",
    )

    # ── add ───────────────────────────────────────────────────────────────
    add_parser = subparsers.add_parser(
        "add",
        help="Adiciona ou atualiza credenciais de um dispositivo no cofre.",
    )
    add_parser.add_argument(
        "--customer", required=True, help="Identificador do cliente (ex: cliente_a)."
    )
    add_parser.add_argument(
        "--device", required=True, help="Identificador do dispositivo (ex: borda-01)."
    )

    # ── list ──────────────────────────────────────────────────────────────
    list_parser = subparsers.add_parser(
        "list",
        help="Lista customers e devices no cofre (sem exibir senhas).",
    )
    list_parser.add_argument(
        "--customer", required=False, default=None,
        help="Filtrar por um customer específico.",
    )

    args = parser.parse_args()

    if args.command == "generate-key":
        _cmd_generate_key(args)
    elif args.command == "add":
        _cmd_add(args)
    elif args.command == "list":
        _cmd_list(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
