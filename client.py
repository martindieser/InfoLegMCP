import requests
import uuid
from models import BusquedaNormaRequest, BusquedaNormaResponse, PaginacionRequest \
                   , BusquedaBoletinRequest, BusquedaBoletinResponse \
                   , ParamsVerNorma, VerNormaResponse \
                   , ParamsVerVinculos, VerVinculosResponse, ModoVinculo \
                   , BusquedaConfig, TipoNorma, Dependencia

from parsers import *

BASE_URL = "https://servicios.infoleg.gob.ar/infolegInternet"

class InfolegClient:

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

        response = session.get(url_absoluta)
        response.raise_for_status()
        
        if response.encoding == 'ISO-8859-1':
            response.encoding = 'latin-1'

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav"]):
            tag.decompose()

        return md(str(soup), heading_style="ATX")


    def mostrar_opciones_busqueda_de_normas(self, session: requests.Session) -> BusquedaConfig:
        r = session.get(f"{BASE_URL}/mostrarBusquedaNormas.do")
        r.raise_for_status()
        return InfoLegConfigParser().parse(r.text)


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
