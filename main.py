"""
main.py
────────
Ponto de entrada do SentinelNet_FLS.

Fluxo esperado (a implementar nas Tasks seguintes):
    1. Carregar inventário (lista de dispositivos e credenciais).
    2. Para cada dispositivo, instanciar o driver correspondente.
    3. Coletar o snapshot de configuração atual via driver.
    4. Carregar a baseline JSON do inventário/.
    5. Comparar snapshot × baseline com o Diff Engine (Task 05).
    6. Persistir relatório de desvios (Task 06).
"""

from internalloggin.logger import setup_logger


logger = setup_logger(__name__)


def main() -> None:
    logger.info("SentinelNet_FLS iniciado.")
    # TODO (Task 03+): Integrar driver MikroTik, Diff Engine e Relatório.
    logger.info("Nenhum driver configurado ainda. Implementar Tasks 03–06.")


if __name__ == "__main__":
    main()
