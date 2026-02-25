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

import logging
import sys


def setup_logging() -> None:
    """Configura o logger raiz para saída formatada no console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("SentinelNet_FLS iniciado.")
    # TODO (Task 03+): Integrar driver MikroTik, Diff Engine e Relatório.
    logger.info("Nenhum driver configurado ainda. Implementar Tasks 03–06.")


if __name__ == "__main__":
    main()
