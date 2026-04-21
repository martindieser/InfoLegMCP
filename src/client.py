from functools import wraps
from typing import Callable, Any
from models import BusquedaNormaRequest, BusquedaNormaResponse, PaginacionRequest \
                   , BusquedaBoletinRequest, BusquedaBoletinResponse \
                   , ParamsVerNorma, VerNormaResponse \
                   , ParamsVerVinculos, VerVinculosResponse, ModoVinculo \
                   , BusquedaConfig, TipoNorma, Dependencia

from requests.exceptions import RequestException, Timeout
from parsers import *
from cache import PageCache, NormaCache
import hashlib
import requests
import uuid
import time
import json

BASE_URL = "https://servicios.infoleg.gob.ar/infolegInternet"

# Instancias globales de caché
norma_cache = NormaCache()
page_cache = PageCache()

def cache_norma(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, session: requests.Session, params: ParamsVerNorma) -> VerNormaResponse:
        cached = norma_cache.get(params.id)
        if cached:
            return cached
        result = func(self, session, params)
        norma_cache.set(params.id, result)
        return result
    return wrapper

def cache_vinculos(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, session: requests.Session, params: ParamsVerVinculos) -> VerVinculosResponse:
        # Usamos el modo para diferenciar la caché
        if params.modo == ModoVinculo.MODIFICA_A:
            cached_json = norma_cache.get_vinculos_modifica_a(params.id)
        else:
            cached_json = norma_cache.get_vinculos_modificada_por(params.id)
            
        if cached_json:
            # Re-parsear el JSON guardado (norma_cache guarda strings de los vínculos actualmente)
            return VerVinculosResponse.model_validate_json(cached_json)
            
        result = func(self, session, params)
        result_json = result.model_dump_json(indent=2)
        
        if params.modo == ModoVinculo.MODIFICA_A:
            norma_cache.set_vinculos_modifica_a(params.id, result_json)
        else:
            norma_cache.set_vinculos_modificada_por(params.id, result_json)
            
        return result
    return wrapper

def cache_texto_actualizado(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, session: requests.Session, id: int, url_relativa: str) -> str:
        cached = norma_cache.get_texto_actualizado(id)
        if cached:
            return cached
        texto = func(self, session, id, url_relativa)
        if texto and not texto.startswith("No se encontró"):
            norma_cache.set_texto_actualizado(id, texto)
        return texto
    return wrapper

def cache_texto_original(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, session: requests.Session, id: int, url_relativa: str) -> str:
        cached = norma_cache.get_texto_original(id)
        if cached:
            return cached
        texto = func(self, session, id, url_relativa)
        if texto and not texto.startswith("No se encontró"):
            norma_cache.set_texto_original(id, texto)
        return texto
    return wrapper


def cache_busqueda(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, session: requests.Session, request: Any) -> BusquedaNormaResponse:
        # Extraer página del request
        page = 1
        if isinstance(request, PaginacionRequest):
            page = request.irAPagina
        
        # Generar hash de cookies para identificar la sesión de búsqueda en InfoLeg
        cookie_dict = session.cookies.get_dict()
        cookie_hash = hashlib.md5(json.dumps(cookie_dict, sort_keys=True).encode()).hexdigest()
        
        # Intentar obtener de la caché
        cached = page_cache.get(cookie_hash, page)
        if cached:
            return cached
            
        # Ejecutar petición
        result = func(self, session, request)
        
        # Si las cookies cambiaron (ej: después del primer request), 
        # actualizamos el hash para guardar el resultado correctamente
        new_cookie_dict = session.cookies.get_dict()
        new_cookie_hash = hashlib.md5(json.dumps(new_cookie_dict, sort_keys=True).encode()).hexdigest()
        
        page_cache.set(new_cookie_hash, page, result)
        return result
    return wrapper

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

    @cache_texto_actualizado
    def consultar_texto_actualizado(self, session: requests.Session, id: int, url_relativa: str) -> str:
        return self.consultar_anexo(session, url_relativa)

    @cache_texto_original
    def consultar_texto_original(self, session: requests.Session, id: int, url_relativa: str) -> str:
        return self.consultar_anexo(session, url_relativa)


    def mostrar_opciones_busqueda_de_normas(self, session: requests.Session) -> BusquedaConfig:
        url = f"{BASE_URL}/mostrarBusquedaNormas.do"
        r = self._request(session, 'GET', url)
        return InfoLegConfigParser().parse(r.text)

    @cache_vinculos
    def ver_vinculos(self, session: requests.Session, params: ParamsVerVinculos) -> VerVinculosResponse:
        url = f"{BASE_URL}/verVinculos.do"
        r = self._request(session, 'GET', url,
            params=params.model_dump(exclude_none=True))
        return VerVinculosParser(r.text, params.id).parse()

    @cache_norma
    def ver_norma(self, session: requests.Session, params: ParamsVerNorma) -> VerNormaResponse:
        url = f"{BASE_URL}/verNorma.do"
        r = self._request(session, 'GET', url, params=params.model_dump(exclude_none=True))
        return InfolegNormaParser(params.id).parse(r.text)

    def buscar_boletin(self, session: requests.Session, request: BusquedaBoletinRequest) -> BusquedaBoletinResponse:
        raise NotImplemented()

    @cache_busqueda
    def buscar_normas(self, session: requests.Session, request: BusquedaNormaRequest) -> BusquedaNormaResponse:
        """
        Realiza la petición POST inicial de búsqueda.
        """
        payload = request.model_dump(exclude_none=True)
        url = f"{BASE_URL}/buscarNormas.do"
        r = self._request(session, 'POST', url, data=payload)
        return InfoLegBusquedasParser().parse(r.text)

    @cache_busqueda
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
