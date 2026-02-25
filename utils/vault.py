"""
utils/vault.py
──────────────
Cofre de credenciais criptografado para o SentinelNet_FLS (Task 07).

Responsabilidades:
    - Criptografar/descriptografar credenciais de dispositivos usando Fernet
      (AES-128-CBC com HMAC-SHA256).
    - Armazenar o payload criptografado em disco (``inventory/vault.enc``).
    - Ler a Master Key **exclusivamente** da variável de ambiente
      ``SENTINEL_MASTER_KEY`` — nunca de arquivo.

Design Decisions
────────────────
1. Criptografia em Repouso (At Rest):
   Mesmo com acesso físico ao servidor/laptop, as senhas dos clientes estão
   protegidas por AES. O arquivo ``.enc`` pode existir no disco, mas sem a
   Master Key é inútil.

2. Separação de Privilégios:
   A Master Key vive no ambiente de execução (variável de ambiente). O arquivo
   ``.env`` com essa variável está no ``.gitignore`` — nunca versionado.

3. Estrutura do payload (plaintext JSON):
   {
       "customer_id": {
           "device_id": {
               "host": "192.168.1.1",
               "username": "admin",
               "password": "s3cret",
               "port": 22
           }
       }
   }

4. Prevenção de Data Leakage:
   A classe nunca loga conteúdo de credenciais. Apenas ``customer_id``,
   ``device_id`` e tipos de operação são registrados nos logs.

5. Resiliência:
   O código trata cofre corrompido (``InvalidToken``), chave incorreta,
   variável de ambiente ausente e cofre inexistente com exceções
   descritivas e logging contextualizado.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

from internalloggin.logger import setup_logger

logger = setup_logger("VaultManager")

# Caminho padrão do cofre criptografado
_DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "inventory" / "vault.enc"

# Nome da variável de ambiente que contém a Master Key
_ENV_MASTER_KEY = "SENTINEL_MASTER_KEY"


class VaultError(Exception):
    """Exceção base para erros do cofre de credenciais."""


class MasterKeyNotFoundError(VaultError):
    """Variável de ambiente SENTINEL_MASTER_KEY não está configurada."""


class VaultCorruptedError(VaultError):
    """O arquivo do cofre está corrompido ou a Master Key está incorreta."""


class CredentialNotFoundError(VaultError):
    """Credencial solicitada não existe no cofre."""


class VaultManager:
    """
    Gerenciador de cofre de credenciais criptografado.

    Uso típico::

        vault = VaultManager()

        # Salvar credenciais
        vault.encrypt_payload({
            "cliente_a": {
                "borda-01": {
                    "host": "192.168.1.1",
                    "username": "admin",
                    "password": "s3cret",
                    "port": 22
                }
            }
        })

        # Recuperar credenciais
        creds = vault.get_credentials("cliente_a", "borda-01")
        # creds → {"host": "192.168.1.1", "username": "admin", "password": "s3cret", "port": 22}

    A Master Key deve estar na variável de ambiente ``SENTINEL_MASTER_KEY``.
    Gere uma nova chave com::

        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    Ou use o script utilitário::

        python -m utils.vault_setup generate-key
    """

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        """
        Inicializa o VaultManager.

        Args:
            vault_path: Caminho do arquivo ``.enc``. Default: ``inventory/vault.enc``.

        Raises:
            MasterKeyNotFoundError: Se ``SENTINEL_MASTER_KEY`` não estiver definida.
        """
        self._vault_path = vault_path or _DEFAULT_VAULT_PATH
        self._fernet = self._load_fernet()
        logger.info(
            "VaultManager inicializado. Cofre: %s", self._vault_path,
        )

    # ── API Pública ───────────────────────────────────────────────────────────

    def encrypt_payload(self, data: dict[str, Any]) -> None:
        """
        Criptografa um dicionário de credenciais e salva no cofre em disco.

        O payload é serializado para JSON, codificado em UTF-8 e criptografado
        com Fernet (AES-128-CBC + HMAC-SHA256). O arquivo anterior, se existir,
        é sobrescrito.

        Args:
            data: Dicionário hierárquico ``{customer_id: {device_id: {creds}}}``.

        Raises:
            VaultError: Se houver erro ao serializar ou gravar o cofre.
        """
        try:
            plaintext = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            encrypted = self._fernet.encrypt(plaintext)

            # Garante que o diretório pai existe
            self._vault_path.parent.mkdir(parents=True, exist_ok=True)

            self._vault_path.write_bytes(encrypted)
            # Restringe permissões: apenas o dono pode ler/escrever (Unix)
            try:
                self._vault_path.chmod(0o600)
            except OSError:
                # Windows não suporta chmod Unix — apenas loga
                logger.debug("chmod 600 não suportado neste SO; ignorando.")

            logger.info(
                "Cofre atualizado com sucesso (%d bytes criptografados). "
                "Customers: %s",
                len(encrypted), list(data.keys()),
            )
        except (TypeError, ValueError) as exc:
            logger.error("Falha ao serializar payload para o cofre: %s", exc)
            raise VaultError(f"Payload inválido para criptografia: {exc}") from exc

    def get_credentials(
        self, customer_id: str, device_id: str
    ) -> dict[str, Any]:
        """
        Descriptografa o cofre e retorna as credenciais de um dispositivo.

        O cofre é descriptografado em memória a cada chamada — as credenciais
        nunca ficam em disco em texto claro.

        Args:
            customer_id: Identificador do cliente (ex: ``"cliente_a"``).
            device_id:   Identificador do dispositivo (ex: ``"borda-01"``).

        Returns:
            Dicionário com ``host``, ``username``, ``password``, ``port``.

        Raises:
            VaultCorruptedError: Cofre corrompido ou Master Key incorreta.
            CredentialNotFoundError: Customer/device não encontrado.
            VaultError: Cofre não existe em disco.
        """
        logger.debug(
            "Buscando credenciais: customer='%s', device='%s'.",
            customer_id, device_id,
        )
        vault_data = self._decrypt_vault()

        # Busca hierárquica: customer → device
        customer_data = vault_data.get(customer_id)
        if customer_data is None:
            logger.error(
                "Customer '%s' não encontrado no cofre. "
                "Customers disponíveis: %s",
                customer_id, list(vault_data.keys()),
            )
            raise CredentialNotFoundError(
                f"Customer '{customer_id}' não encontrado no cofre."
            )

        device_data = customer_data.get(device_id)
        if device_data is None:
            logger.error(
                "Device '%s' não encontrado para customer '%s'. "
                "Devices disponíveis: %s",
                device_id, customer_id, list(customer_data.keys()),
            )
            raise CredentialNotFoundError(
                f"Device '{device_id}' não encontrado para customer '{customer_id}'."
            )

        logger.info(
            "Credenciais recuperadas com sucesso: customer='%s', device='%s'.",
            customer_id, device_id,
        )
        return device_data

    def list_customers(self) -> list[str]:
        """Retorna a lista de customer_ids no cofre."""
        return list(self._decrypt_vault().keys())

    def list_devices(self, customer_id: str) -> list[str]:
        """Retorna a lista de device_ids para um customer."""
        vault_data = self._decrypt_vault()
        customer_data = vault_data.get(customer_id, {})
        return list(customer_data.keys())

    def vault_exists(self) -> bool:
        """Verifica se o arquivo do cofre existe em disco."""
        return self._vault_path.is_file()

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _load_fernet() -> Fernet:
        """
        Carrega a Master Key da variável de ambiente e retorna um objeto Fernet.

        Raises:
            MasterKeyNotFoundError: Se ``SENTINEL_MASTER_KEY`` não estiver definida
                                    ou estiver vazia.
        """
        master_key = os.environ.get(_ENV_MASTER_KEY)

        if not master_key:
            logger.critical(
                "Variável de ambiente '%s' não está configurada! "
                "O cofre de credenciais não pode operar sem a Master Key.",
                _ENV_MASTER_KEY,
            )
            raise MasterKeyNotFoundError(
                f"Variável de ambiente '{_ENV_MASTER_KEY}' não está definida. "
                "Configure-a com uma chave Fernet válida antes de usar o VaultManager.\n"
                "Gere uma nova chave com: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        try:
            fernet = Fernet(master_key.encode("utf-8"))
        except (ValueError, Exception) as exc:
            logger.critical(
                "Master Key inválida na variável '%s': %s", _ENV_MASTER_KEY, exc,
            )
            raise VaultError(
                f"A Master Key em '{_ENV_MASTER_KEY}' não é uma chave Fernet válida. "
                "Gere uma nova chave com: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from exc

        logger.debug("Master Key carregada com sucesso da variável '%s'.", _ENV_MASTER_KEY)
        return fernet

    def _decrypt_vault(self) -> dict[str, Any]:
        """
        Lê e descriptografa o cofre do disco, retornando o payload como dict.

        Raises:
            VaultError: Se o cofre não existir.
            VaultCorruptedError: Se a descriptografia falhar (chave errada ou
                                  arquivo corrompido).
        """
        if not self._vault_path.is_file():
            logger.error("Arquivo do cofre não encontrado: %s", self._vault_path)
            raise VaultError(
                f"Cofre não encontrado em '{self._vault_path}'. "
                "Execute o setup para criar o cofre: python -m utils.vault_setup"
            )

        encrypted = self._vault_path.read_bytes()

        try:
            decrypted = self._fernet.decrypt(encrypted)
        except InvalidToken:
            logger.critical(
                "Falha ao descriptografar o cofre! "
                "A Master Key pode estar incorreta ou o arquivo está corrompido. "
                "Cofre: %s", self._vault_path,
            )
            raise VaultCorruptedError(
                "Impossível descriptografar o cofre. Verifique se a "
                f"variável '{_ENV_MASTER_KEY}' contém a chave correta para "
                f"o arquivo '{self._vault_path}'."
            )

        try:
            payload = json.loads(decrypted.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.critical(
                "Cofre descriptografado mas conteúdo JSON inválido: %s", exc,
            )
            raise VaultCorruptedError(
                "O cofre foi descriptografado com sucesso, mas o conteúdo "
                "JSON interno está corrompido."
            ) from exc

        return payload
