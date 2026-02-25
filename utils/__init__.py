"""
utils/
Utilitários transversais ao projeto.

Módulos:
- vault.py        : Cofre de credenciais criptografado (Task 07 ✅).
- vault_setup.py  : CLI para gerar Master Key e gerenciar credenciais (Task 07 ✅).
- network.py      : (futuro) Helpers de validação de endereços IP e conectividade.
"""

from .vault import (
    CredentialNotFoundError,
    MasterKeyNotFoundError,
    VaultCorruptedError,
    VaultError,
    VaultManager,
)

__all__ = [
    "CredentialNotFoundError",
    "MasterKeyNotFoundError",
    "VaultCorruptedError",
    "VaultError",
    "VaultManager",
]
