import requests
import json
import unicodedata
from mcp.server.fastmcp import FastMCP
from rapidfuzz import process, fuzz
from typing import Optional
from client import InfolegClient
from cache import SearchCache, CachedSearch
from datetime import date
from models import *

mcp = FastMCP("InfoLeg MCP", json_response=True)
search_cache = SearchCache(ttl=300, max_size=100)
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
    offset: Optional[int] = None,
) -> dict:
    """Busca normas en Infoleg por texto, tipo, número, dependencia o rango de fechas de publicación."""
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
    cached = search_cache.get(request)

    if not cached:
        result = client.buscar_normas(session, request)
        search_cache.set(request, CachedSearch(session=session, 
                        result=result, current_page=1, total_pags=result.total_pags))

        cached = search_cache.get(request)
        result_dict = cached.result.model_dump()
        result_dict["pagina_actual"] = 1
        result_dict["total_pags"] = result.total_pags
        return json.dumps(result_dict, indent=2, default=str)

    if ((offset is None) or (offset == 0)) and cached:
        result_dict = cached.result.model_dump()
        result_dict["pagina_actual"] = 1
        result_dict["total_pags"] = cached.total_pags
        return json.dumps(result_dict, indent=2, default=str)
     
    # (offset is not None -> (offset > 0) or (offset < 0)) and cached exists...
    max_page = cached.total_pags
    current_page = cached.current_page
    # health checks
    target_page = current_page + offset
    if target_page > max_page: # se pasa en la cota superior
        offset = max_page - current_page

    if target_page <= 0: # se pasa en la cota inferior
        offset = 1 - current_page 

    # si después del clampeo no hay movimiento, devolvemos lo que hay
    if offset == 0:
        return cached.result.model_dump_json(indent=2)

    # recalculamos con el nuevo offset
    target_page = current_page + offset
    accion = ModoDesplazamiento.AVANZAR if offset > 0 else ModoDesplazamiento.RETROCEDER

    pag_request = PaginacionRequest(irAPagina=offset, desplazamiento=accion)
    result = client.navegar_normas(cached.session, pag_request)
    search_cache.set(request, CachedSearch(session=cached.session, 
                        result=result, current_page=target_page, total_pags=result.total_pags))
    result_dict = result.model_dump()
    result_dict["pagina_actual"] = target_page
    result_dict["total_pags"] = cached.total_pags
    return json.dumps(result_dict, indent=2, default=str)



if __name__ == "__main__":
    mcp.run(transport="streamable-http")