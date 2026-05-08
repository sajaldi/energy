import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def send_to_power_automate(payload):
    """
    Envía un payload JSON a un flujo de Power Automate.
    La URL debe estar configurada en el .env como POWER_AUTOMATE_SYNC_URL.
    """
    webhook_url = os.getenv("POWER_AUTOMATE_SYNC_URL")
    
    if not webhook_url:
        logger.error("POWER_AUTOMATE_SYNC_URL no configurada en el .env")
        return False

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Datos enviados a Power Automate exitosamente. Status: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Error enviando datos a Power Automate: {str(e)}")
        return False
