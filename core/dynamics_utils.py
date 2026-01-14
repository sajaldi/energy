import os
import msal
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Dynamics365Client:
    """
    Cliente para interactuar con la Web API de Dynamics 365 / Dataverse.
    Requiere una App Registration en Azure AD con permisos de 'user_impersonation' o 'Application' en Dynamics.
    """

    def __init__(self):
        self.tenant_id = os.getenv("DYNAMICS_TENANT_ID")
        self.client_id = os.getenv("DYNAMICS_CLIENT_ID")
        self.client_secret = os.getenv("DYNAMICS_CLIENT_SECRET")
        self.resource_url = os.getenv("DYNAMICS_RESOURCE_URL")
        
        # URL de la API (generalmente termina en /api/data/v9.2/)
        self.api_url = f"{self.resource_url.rstrip('/')}/api/data/v9.2/"
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = [f"{self.resource_url}/.default"]
        
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )
        self._token = None

    def get_token(self):
        """Obtiene un token de acceso usando Client Credentials."""
        result = self.app.acquire_token_silent(self.scope, account=None)
        if not result:
            logger.info("Token no encontrado en cache, solicitando uno nuevo.")
            result = self.app.acquire_token_for_client(scopes=self.scope)

        if "access_token" in result:
            return result["access_token"]
        else:
            error_msg = f"Error al obtener token: {result.get('error_description', result.get('error'))}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "odata.include-annotations=\"*\""
        }

    def get(self, endpoint, params=None):
        """Realiza una petición GET a la API."""
        url = f"{self.api_url}{endpoint}"
        response = requests.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint, data):
        """Realiza una petición POST (Crear registro)."""
        url = f"{self.api_url}{endpoint}"
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        if response.status_code == 204:
            return True
        return response.json()

    def patch(self, endpoint, data):
        """Realiza una petición PATCH (Actualizar registro)."""
        url = f"{self.api_url}{endpoint}"
        response = requests.patch(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return True

    def delete(self, endpoint):
        """Realiza una petición DELETE."""
        url = f"{self.api_url}{endpoint}"
        response = requests.delete(url, headers=self._get_headers())
        response.raise_for_status()
        return True

# Instancia global para uso simplificado
dynamics_client = Dynamics365Client()
