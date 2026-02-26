from __future__ import annotations

from pathlib import Path

from utils.vault import MasterKeyNotFoundError, VaultError, VaultManager

_VAULT_PATH = Path(__file__).resolve().parent.parent.parent / "inventory" / "vault.enc"


def save_device_credentials(
    *,
    customer_id: str,
    device_id: str,
    host: str,
    username: str,
    password: str,
    port: int,
    token: str | None = None,
) -> tuple[bool, str]:
    if not username.strip() or not password:
        return False, "Informe credenciais válidas (username e password)."

    try:
        vault = VaultManager(vault_path=_VAULT_PATH)
        vault.upsert_credentials(
            customer_id=customer_id,
            device_id=device_id,
            host=host,
            username=username,
            password=password,
            port=port,
            token=token.strip() if token else None,
        )
    except MasterKeyNotFoundError:
        return (
            False,
            "Master key não configurada. Defina SENTINEL_MASTER_KEY antes de cadastrar credenciais.",
        )
    except VaultError:
        return False, "Falha ao gravar credenciais no cofre criptografado."

    return True, "Credenciais gravadas com segurança no cofre (vault.enc)."
