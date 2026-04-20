import requests
import uuid
import time
from models import BusquedaNormaRequest, BusquedaNormaResponse, PaginacionRequest \
                   , BusquedaBoletinRequest, BusquedaBoletinResponse \
                   , ParamsVerNorma, VerNormaResponse \
                   , ParamsVerVinculos, VerVinculosResponse, ModoVinculo \
                   , BusquedaConfig, TipoNorma, Dependencia

from requests.exceptions import RequestException, Timeout
from parsers import *

BASE_URL = "https://servicios.infoleg.gob.ar/infolegInternet"

class InfolegClient:

    DEFAULT_TIMEOUT = 20
    MAX_RETRIES = 5
    BACKOFF_FACTOR = 1 

    def _request(self, session: requests.Session, method: str, url: str, **kwargs):
        for attempt in range(self.MAX_RETRIES):
            try:
                response = session.request(method, url, timeout=self.DEFAULT_TIMEOUT, **kwargs)
                response.raise_for_status()
                return response

            except (Timeout, ConnectionError) as e:
                # Si es el último intento, lanzamos la excepción
                if attempt == self.MAX_RETRIES - 1:
                    raise
                # Tiempo de espera exponencial: 1s, 2s, 4s...
                wait_time = self.BACKOFF_FACTOR * (2 ** attempt)
                time.sleep(wait_time)

    def consultar_anexo(self, session: requests.Session, url_relativa : str):

        from markdownify import markdownify as md
        if url_relativa.startswith(".."):
            base_parts = BASE_URL.split("/")
            if base_parts[-1] == "infolegInternet":
                 url_absoluta = "/".join(base_parts[:-1]) + "/" + url_relativa.replace("../", "")
            else:
                 url_absoluta = BASE_URL + "/" + url_relativa
        else:
            url_absoluta = BASE_URL + "/" + url_relativa

        response = self._request(session, 'GET', url_absoluta)
        
        if response.encoding == 'ISO-8859-1':
            response.encoding = 'latin-1'

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav"]):
            tag.decompose()

        return md(str(soup), heading_style="ATX")


    def mostrar_opciones_busqueda_de_normas(self, session: requests.Session) -> BusquedaConfig:
        url = f"{BASE_URL}/mostrarBusquedaNormas.do"
        r = self._request(session, 'GET', url_absoluta)
        return InfoLegConfigParser().parse(r.text)


    def ver_vinculos(self, session: requests.Session, params: ParamsVerVinculos) -> VerVinculosResponse:
        url = f"{BASE_URL}/verVinculos.do"
        r = self._request(session, 'GET', url,
            params=params.model_dump(exclude_none=True))
        return VerVinculosParser(r.text, params.id).parse()

    def ver_norma(self, session: requests.Session, params: ParamsVerNorma) -> VerNormaResponse:
        url = f"{BASE_URL}/verNorma.do"
        r = self._request(session, 'GET', url, params=params.model_dump(exclude_none=True))
        return InfolegNormaParser(params.id).parse(r.text)

    def buscar_boletin(self, session: requests.Session, request: BusquedaBoletinRequest) -> BusquedaBoletinResponse:
        raise NotImplemented()

    def buscar_normas(self, session: requests.Session, request: BusquedaNormaRequest) -> BusquedaNormaResponse:
        """
        Realiza la petición POST inicial de búsqueda.
        """
        payload = request.model_dump(exclude_none=True)
        url = f"{BASE_URL}/buscarNormas.do"
        r = self._request(session, 'POST', url, data=payload)
        return InfoLegBusquedasParser().parse(r.text)

    def navegar_normas(self, session: requests.Session, request: PaginacionRequest) -> BusquedaNormaResponse:
        """
        Realiza la petición POST de paginación.
        """
        payload = request.model_dump(exclude_none=True)
        url = f"{BASE_URL}/buscarNormas.do"
        r = self._request(session, 'POST', url, data=payload)
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

    response = client.mostrar_opciones_busqueda_de_normas(session)
    print(response)
    
    # response = client.buscar_normas(session, test_request)
    # print(f"\nResultados encontrados: {response.total}")
    # print(response.model_dump_json(indent=2))
    # test_params = ParamsVerNorma(id=274045) 
    # response = client.ver_norma(session, test_params)
    # print(response.model_dump_json(indent=2))
    test_params = ParamsVerVinculos(id=274045, modo=ModoVinculo.MODIFICADA_POR) 
    response = client.ver_vinculos(session, test_params)
    print(response.model_dump_json(indent=2))
