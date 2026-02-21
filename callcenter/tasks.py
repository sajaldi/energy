import os
from celery import shared_task
from django.conf import settings
from .scraper import download_tickets_excel
from .utils import import_tickets_from_df
import pandas as pd
import logging

logger = logging.getLogger(__name__)

@shared_task(name='callcenter.tasks.sync_tickets_task')
def sync_tickets_task(days=2):
    """
    Tarea de Celery para sincronizar tickets desde SIG GIA.
    """
    # Estas credenciales deberían estar en variables de entorno o settings por seguridad
    username = os.environ.get('CALLCENTER_USER', 'saul.alvarado')
    password = os.environ.get('CALLCENTER_PASS', 'S@4l2689*')
    company = "Centro Cívico Gubernamental de Honduras"
    
    logger.info(f"Iniciando sincronización de tickets de los últimos {days} días...")
    
    try:
        download_dir = os.path.join(settings.BASE_DIR, 'downloads')
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        file_path = download_tickets_excel(
            username=username,
            password=password,
            company_name=company,
            days=days,
            download_dir=download_dir
        )
        
        if not file_path or not os.path.exists(file_path):
            error_msg = "No se pudo descargar el archivo de tickets."
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        from django.db import connection, close_old_connections
        # Asegurar conexión limpia para el worker tras el scraping largo
        close_old_connections()
        if connection.connection:
            connection.close() 
            
        df = pd.read_excel(file_path)
        creados, actualizados = import_tickets_from_df(df)
        
        result_msg = f"Sincronización finalizada. Nuevos: {creados}, Actualizados: {actualizados}"
        logger.info(result_msg)
        
        # El archivo queda en downloads para trazabilidad si se desea
        # if os.path.exists(file_path):
        #     os.remove(file_path)
            
        return {"status": "success", "creados": creados, "actualizados": actualizados}
        
    except Exception as e:
        logger.error(f"Error en sync_tickets_task: {e}")
        return {"status": "error", "message": str(e)}
