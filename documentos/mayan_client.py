import requests
from django.conf import settings

class MayanEDMSClient:
    """Cliente para interactuar con la API de Mayan EDMS"""
    
    def __init__(self):
        self.base_url = settings.MAYAN_EDMS_API_URL
        self.session = requests.Session()
        
        # Autenticación con token o usuario/contraseña
        if settings.MAYAN_EDMS_TOKEN:
            self.session.headers.update({
                'Authorization': f'Token {settings.MAYAN_EDMS_TOKEN}'
            })
        elif settings.MAYAN_EDMS_USERNAME and settings.MAYAN_EDMS_PASSWORD:
            self.session.auth = (
                settings.MAYAN_EDMS_USERNAME,
                settings.MAYAN_EDMS_PASSWORD
            )
    
    def upload_document(self, file, document_type_id, description='', metadata=None):
        """
        Sube un documento a Mayan EDMS
        
        Args:
            file: Archivo a subir (FileField o path)
            document_type_id: ID del tipo de documento en Mayan
            description: Descripción del documento
            metadata: Dict con metadatos adicionales
        
        Returns:
            dict: Respuesta de Mayan con ID del documento creado
        """
        url = f'{self.base_url}documents/'
        
        files = {'file': file}
        data = {
            'document_type_id': document_type_id,
            'description': description
        }
        
        response = self.session.post(url, files=files, data=data)
        response.raise_for_status()
        
        document = response.json()
        
        # Agregar metadatos si se proporcionan
        if metadata and document.get('id'):
            self.add_metadata(document['id'], metadata)
        
        return document
    
    def get_document(self, document_id):
        """Obtiene información de un documento"""
        url = f'{self.base_url}documents/{document_id}/'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_document_file_url(self, document_id, version='latest'):
        """Retorna URL para descargar el archivo del documento"""
        return f'{self.base_url}documents/{document_id}/versions/{version}/file/'
    
    def add_metadata(self, document_id, metadata):
        """Agrega metadatos a un documento"""
        url = f'{self.base_url}documents/{document_id}/metadata/'
        
        for key, value in metadata.items():
            data = {
                'metadata_type': key,
                'value': value
            }
            self.session.post(url, json=data)
    
    def search_documents(self, query):
        """Busca documentos por texto"""
        url = f'{self.base_url}documents/search/'
        params = {'q': query}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_document_types(self):
        """Lista los tipos de documentos disponibles"""
        url = f'{self.base_url}document_types/'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_document_ocr_content(self, document_id):
        """Obtiene el contenido de texto (OCR) de un documento en Mayan"""
        url = f'{self.base_url}documents/{document_id}/content/'
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            # Mayan retorna una lista de páginas, unimos el contenido
            full_text = ""
            if 'results' in data:
                for page in data['results']:
                    full_text += page.get('content', '') + "\n"
            return full_text.strip()
        except Exception as e:
            print(f"Error al obtener OCR de Mayan: {e}")
            return ""

    def delete_document(self, document_id):
        """Elimina un documento de Mayan"""
        url = f'{self.base_url}documents/{document_id}/'
        try:
            self.session.delete(url)
        except:
            pass
