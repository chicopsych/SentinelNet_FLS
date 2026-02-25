# Filosofia: "O que não está no log, não aconteceu."

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Definindo o caminho para a pasta de logs internos do sistema
LOG_DIR = Path(__file__).parent / "internallogs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def setup_logger(name: str = "SentinelNet_FLS") -> logging.Logger:
    """
    Configura o logger para o SentinelNet_FLS.
    
    Args:
        name (str): O nome do logger. Default é "SentinelNet_FLS".
    
    Returns:
        logging.Logger: O logger configurado.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Evita duplicidade de log se o logger for inicializado mais de uma vez
    if not logger.handlers:
        # Formato do log: Timestamp - Nível de Log - Modulo - Mensagem
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        # Handler para console (Saida padrão)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)  # Log de INFO para console
        logger.addHandler(console_handler)

        # Handler para arquivo (Rotativo)
        file_path = LOG_DIR / f"{name}.log"
        file_handler = RotatingFileHandler(
            filename=file_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=13,  # Mantém os últimos 13 arquivos de log
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # Log de DEBUG para arquivo
        logger.addHandler(file_handler)
    return logger

# Instância única para ser importada em outros módulos
logger = setup_logger()