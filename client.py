import requests
import uuid
from models import BusquedaNormaRequest, BusquedaNormaResponse, PaginacionRequest \
                   , BusquedaBoletinRequest, BusquedaBoletinResponse \
                   , ParamsVerNorma, VerNormaResponse \
                   , ParamsVerVinculos, VerVinculosResponse \
                   , ModoVinculo

from parsers import *

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

    def ver_vinculos(self, session: requests.Session, params: ParamsVerVinculos) -> VerVinculosResponse:
        r = session.get(f"{BASE_URL}/verVinculos.do", params=params.model_dump(exclude_none=True))
        r.raise_for_status()
        return VerVinculosParser(r.text, params.id).parse()

    def ver_norma(self, session: requests.Session, params: ParamsVerNorma) -> VerNormaResponse:
        params = params.model_dump(exclude_none=True)
        r = session.get(f"{BASE_URL}/verNorma.do", params=params)
        r.raise_for_status()
        return InfolegNormaParser().parse(r.text)

    def buscar_boletin(self, session: requests.Session, request: BusquedaBoletinRequest) -> BusquedaBoletinResponse:
        raise NotImplemented()

    def buscar_normas(self, session: requests.Session, request: BusquedaNormaRequest) -> BusquedaNormaResponse:
        """
        Realiza la petición POST inicial de búsqueda.
        """
        payload = request.model_dump(exclude_none=True)
        r = session.post(f"{BASE_URL}/buscarNormas.do", data=payload)
        r.raise_for_status()
        
        return InfoLegBusquedasParser().parse(r.text)

    def navegar_normas(self, session: requests.Session, request: PaginacionRequest) -> BusquedaNormaResponse:
        """
        Realiza la petición POST de paginación.
        """
        payload = request.model_dump(exclude_none=True)
        r = session.post(f"{BASE_URL}/buscarNormas.do", data=payload)
        r.raise_for_status()
        
        return InfoLegBusquedasParser().parse(r.text)

if __name__ == "__main__":
    # Prueba rápida: Ley 27430
    import json
    
    client = InfolegClient()
    session = requests.Session()
    test_request = BusquedaNormaRequest(
        tipoNorma=1, # Ley
        texto="apuestas",
    )
    
    # response = client.buscar_normas(session, test_request)
    # print(f"\nResultados encontrados: {response.total}")
    # print(response.model_dump_json(indent=2))
    # test_params = ParamsVerNorma(id=274045) 
    # response = client.ver_norma(session, test_params)
    # print(response.model_dump_json(indent=2))
    test_params = ParamsVerVinculos(id=274045, modo=ModoVinculo.MODIFICADA_POR) 
    response = client.ver_vinculos(session, test_params)
    print(response.model_dump_json(indent=2))
