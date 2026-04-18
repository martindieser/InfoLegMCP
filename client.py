import requests
import uuid
from models import BusquedaNormaRequest, BusquedaNormaResponse, PaginacionRequest
from parsers import InfoLegParser

BASE_URL = "https://servicios.infoleg.gob.ar/infolegInternet"

class SearchSession:
    """Encapsula el estado de una búsqueda activa y su sesión HTTP."""
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.session = requests.Session()
        self.pagina_actual = 1

    def siguiente(self) -> PaginacionRequest:
        self.pagina_actual += 1
        return PaginacionRequest(desplazamiento="AP", irAPagina=self.pagina_actual)

    def anterior(self) -> PaginacionRequest:
        if self.pagina_actual > 1:
            self.pagina_actual -= 1
        return PaginacionRequest(desplazamiento="RP", irAPagina=self.pagina_actual)

class InfolegClient:
    def buscar_normas(self, session: requests.Session, request: BusquedaNormaRequest) -> BusquedaNormaResponse:
        """
        Realiza la petición POST inicial de búsqueda.
        """
        payload = request.model_dump(exclude_none=True)
        r = session.post(f"{BASE_URL}/buscarNormas.do", data=payload)
        r.raise_for_status()
        
        return InfoLegParser.parse_busqueda_resultados(r.text)

    def navegar_normas(self, session: requests.Session, request: PaginacionRequest) -> BusquedaNormaResponse:
        """
        Realiza la petición POST de paginación.
        """
        payload = request.model_dump(exclude_none=True)
        r = session.post(f"{BASE_URL}/buscarNormas.do", data=payload)
        r.raise_for_status()
        
        return InfoLegParser.parse_busqueda_resultados(r.text)

if __name__ == "__main__":
    # Prueba rápida: Ley 27430
    import json
    
    session_manager = SearchSession()
    client = InfolegClient()
    test_request = BusquedaNormaRequest(
        tipoNorma=1, # Ley
        texto="apuestas",
    )
    
    print(f"Buscando Ley 27430...")
    response = client.buscar_normas(session_manager.session, test_request)
    
    print(f"\nResultados encontrados: {response.total}")
    print(response.model_dump_json(indent=2))
