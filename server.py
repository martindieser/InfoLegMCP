import requests
import json
import unicodedata
from mcp.server.fastmcp import FastMCP
from rapidfuzz import process, fuzz
from typing import Optional
from client import InfolegClient
from cache import SessionCache, PageCache, SearchSessionState
from datetime import date
from models import *

mcp = FastMCP("InfoLeg MCP", json_response=True)
session_cache = SessionCache()
page_cache = PageCache()

PATH_DEPENDENCIAS = "./data/dependencias.json"
PATH_TIPOS_NORMA = "./data/tipos_norma.json"


def normalize(text: str) -> str:
    text = text.lower()
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")


@mcp.resource("file://tipos-norma")
def get_tipos_norma() -> str:
    """Catálogo completo de tipos de norma disponibles."""
    with open(PATH_TIPOS_NORMA) as f:
        return f.read()

@mcp.tool()
def get_dependencia_by_id(id: int) -> dict:
    """Obtiene una dependencia por su ID exacto."""
    with open(PATH_DEPENDENCIAS) as f:
        deps = json.load(f)

    result = next((d for d in deps if d["id"] == id), None)

    if not result:
        raise ValueError(f"No se encontró dependencia con ID {id}")

    return result

@mcp.tool()
def buscar_dependencias(query: str, limit: int = 10) -> list:
    """Busca dependencias por nombre usando fuzzy search."""
    with open(PATH_DEPENDENCIAS) as f:
        deps = json.load(f)

    choices = {i: normalize(d["nombre"]) for i, d in enumerate(deps)}
    matches = process.extract(
        normalize(query),
        choices,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=70
    )

    return [deps[i] for _, _, i in matches]

@mcp.tool()
def ver_norma(id: int) -> dict:
    """Obtiene el texto y metadatos completos de una norma por ID."""
    session = requests.Session()
    client = InfolegClient()
    params = ParamsVerNorma(id=id)
    return client.ver_norma(session, params).model_dump_json(indent=2)


@mcp.tool()
def ver_normas_que_modifica(id: int) -> dict:
    """Devuelve las normas que esta norma modifica o complementa."""
    session = requests.Session()
    client = InfolegClient()
    params = ParamsVerVinculos(id=id, modo=ModoVinculo.MODIFICA_A)
    return client.ver_vinculos(session, params).model_dump_json(indent=2)


@mcp.tool()
def ver_normas_que_la_modifican(id: int) -> dict:
    """Devuelve las normas por las que esta norma fue modificada o complementada."""
    session = requests.Session()
    client = InfolegClient()
    params = ParamsVerVinculos(id=id, modo=ModoVinculo.MODIFICADA_POR)
    return client.ver_vinculos(session, params).model_dump_json(indent=2)

@mcp.tool()
def buscar_normas(
    tipo_norma: Optional[int] = None,
    numero: Optional[int] = None,
    anio_sancion: Optional[int] = None,
    texto: Optional[str] = None,
    dependencia: Optional[int] = None,
    publicado_desde: Optional[date] = None,
    publicado_hasta: Optional[date] = None,
    nro_pag: Optional[int] = None,
) -> dict:
    """Busca normas en Infoleg por texto, tipo, número, dependencia o rango de fechas de publicación."""
    
    # Validar que se ingresen suficientes parámetros para evitar búsquedas demasiado amplias
    search_params = [tipo_norma, numero, anio_sancion, dependencia, publicado_desde, publicado_hasta]
    provided_params = sum(1 for p in search_params if p is not None)
    
    if not texto and provided_params < 2:
        raise ValueError(
            "Debe ingresar al menos 2 parámetros de búsqueda (por ejemplo: tipo_norma y numero) "
            "a menos que realice una búsqueda por texto."
        )

    if tipo_norma == 1 and anio_sancion is not None:
        raise ValueError("No se debe ingresar el año (anio_sancion) cuando se busca por tipo de norma Ley (tipo_norma=1).")

    request = BusquedaNormaRequest(
        tipoNorma=tipo_norma,
        numero=numero,
        anio_sancion=anio_sancion,
        texto=texto,
        dependencia=dependencia,
        diaPubDesde=publicado_desde.day if publicado_desde else None,
        mesPubDesde=publicado_desde.month if publicado_desde else None,
        anioPubDesde=publicado_desde.year if publicado_desde else None,
        diaPubHasta=publicado_hasta.day if publicado_hasta else None,
        mesPubHasta=publicado_hasta.month if publicado_hasta else None,
        anioPubHasta=publicado_hasta.year if publicado_hasta else None,
    )

    client = InfolegClient()
    session = requests.Session()
    
    # Check for existing session
    session_state = session_cache.get(request)
    target_page = nro_pag if nro_pag and nro_pag > 0 else 1

    if not session_state:
        # No session exists, start from page 1
        result = client.buscar_normas(session, request)
        session_state = SearchSessionState(
            cookies=session.cookies.get_dict(),
            total_pags=result.total_pags
        )
        session_cache.set(request, session_state)
        page_cache.set(request, 1, result)
        
        if target_page == 1:
            result_dict = result.model_dump()
            result_dict["pagina_actual"] = 1
            result_dict["total_pags"] = session_state.total_pags
            return json.dumps(result_dict, indent=2, default=str)

    # We have a session, validate bounds
    if target_page > session_state.total_pags:
        target_page = session_state.total_pags

    # Check for cached page results
    cached_page = page_cache.get(request, target_page)
    if cached_page:
        result_dict = cached_page.model_dump()
        result_dict["pagina_actual"] = target_page
        result_dict["total_pags"] = session_state.total_pags
        return json.dumps(result_dict, indent=2, default=str)

    # Page not in cache, fetch it using existing session
    session.cookies.update(session_state.cookies)
    pag_request = PaginacionRequest(irAPagina=target_page, desplazamiento=ModoDesplazamiento.AVANZAR)
    result = client.navegar_normas(session, pag_request)
    
    # Update cache
    page_cache.set(request, target_page, result)
    session_state.cookies = session.cookies.get_dict() # Update cookies in case they changed
    session_cache.set(request, session_state)
    
    result_dict = result.model_dump()
    result_dict["pagina_actual"] = target_page
    result_dict["total_pags"] = session_state.total_pags
    return json.dumps(result_dict, indent=2, default=str)



if __name__ == "__main__":
    mcp.run(transport="streamable-http")
