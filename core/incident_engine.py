import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from internalloggin import logger as system_logger

# Definição do caminho do banco de dados no inventário
DB_PATH = Path(__file__).parent.parent / "inventory" / "sentinel_data.db"

class IncidentEngine:
    """
    Motor de persistência de incidentes e eventos operacionais.
    Transforma desvios detectados em registros consultáveis no banco de dados.
    """

    def __init__(self):
        self._init_db()

    def _init_db(self):
        """Inicializa a estrutura do banco de dados caso não exista."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS incidents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        customer_id TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        category TEXT NOT NULL,
                        description TEXT,
                        payload_json TEXT,
                        status TEXT DEFAULT 'new'
                    )
                """)
                conn.commit()
                system_logger.debug("Banco de dados de incidentes inicializado com sucesso.")
        except sqlite3.Error as e:
            system_logger.critical(f"Falha ao inicializar o banco de dados: {e}")

    def push_incident(
        self, 
        customer_id: str, 
        device_id: str, 
        severity: str, 
        category: str, 
        description: str, 
        payload: Dict[str, Any]
    ) -> Optional[int]:
        """
        Insere um novo incidente no banco de dados.
        O payload (diff) é convertido para JSON para persistência.
        """
        try:
            # Serialização do payload para string JSON
            json_payload = json.dumps(payload)
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO incidents (customer_id, device_id, severity, category, description, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (customer_id, device_id, severity, category, description, json_payload))
                
                incident_id = cursor.lastrowid
                conn.commit()
                
                system_logger.info(f"Incidente {incident_id} registrado: {severity} - {device_id} ({category})")
                return incident_id
                
        except (sqlite3.Error, TypeError) as e:
            system_logger.error(f"Erro ao salvar incidente no banco: {e}")
            return None

# Instância única para uso no sistema
incident_engine = IncidentEngine()