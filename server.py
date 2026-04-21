import requests
import json
import unicodedata
from mcp.server.fastmcp import FastMCP
from rapidfuzz import process, fuzz
from typing import Optional
from client import InfolegClient, BASE_URL
from cache import PageCache, NormaCache
from datetime import date
from models import *
from sessmanager import SessionManager
from parsers import NormaNotFoundError


PATH_DEPENDENCIAS = "./data/dependencias.json"
PATH_TIPOS_NORMA = "./data/tipos_norma.json"

# Configuración de paginación y límites
INFOLEG_PAGE_SIZE = 50  # Resultados que devuelve InfoLeg por página real
MCP_PAGE_SIZE = 5       # Resultados que entrega el MCP por página virtual
TEXT_CHUNK_SIZE = 500   # Tamaño por defecto de los fragmentos de texto


mcp = FastMCP("InfoLeg MCP", json_response=True)
page_cache = PageCache()
norma_cache = NormaCache()
session_manager = SessionManager()



def normalize(text: str) -> str:
    text = text.lower()
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")


@mcp.resource("file://tipos-norma")
def get_tipos_norma() -> str:
    """Devuelve el catálogo de tipos de norma con su ID y nombre.
    SIEMPRE llamar esta tool antes de usar tipo_norma en buscar_normas()."""
    with open(PATH_TIPOS_NORMA) as f:
        return f.read()

@mcp.tool()
def get_dependencia_by_id(id: int) -> dict:
    """
    Obtiene los datos de una dependencia por su ID exacto.

    CUÁNDO USARLA: Cuando ya se conoce el ID de la dependencia y se quieren ver sus datos.
    Si no se conoce el ID, usar buscar_dependencias() primero.

    PARÁMETROS:
    - id: ID numérico exacto de la dependencia.

    DEVUELVE: Datos de la dependencia (id, nombre, etc.).
    """
    with open(PATH_DEPENDENCIAS) as f:
        deps = json.load(f)

    result = next((d for d in deps if d["id"] == id), None)

    if not result:
        raise ValueError(f"No se encontró dependencia con ID {id}")

    return result

@mcp.tool()
def buscar_dependencias(query: str, limit: int = 10) -> list:
    """
     Busca organismos/dependencias por nombre usando fuzzy search.

     CUÁNDO USARLA: Antes de llamar a buscar_normas() con el parámetro `dependencia`,
     para obtener el ID numérico del organismo emisor.

     PARÁMETROS:
     - query: Nombre o parte del nombre del organismo. Ej: "ministerio de salud", "AFIP", "ANSES".
     - limit: Cantidad máxima de resultados (default: 10).

     DEVUELVE: Lista de dependencias con su ID y nombre. Usar el campo `id` en buscar_normas().

     NOTA: La búsqueda es tolerante a errores tipográficos y variaciones menores.
     """
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
    """
    Obtiene los metadatos de una norma por su ID de Infoleg.

    CUÁNDO USARLA: Cuando se conoce el ID de la norma (obtenido de buscar_normas()).
    Para buscar normas sin ID, usar buscar_normas() primero.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.

    DEVUELVE: Metadatos de la norma.
    """
    # Intentar obtener de la caché
    cached_norma = norma_cache.get(id)
    if cached_norma:
        return cached_norma.model_dump_json(indent=2)

    session = session_manager.get_session()
    client = InfolegClient()
    params = ParamsVerNorma(id=id)
    try:
        result = client.ver_norma(session, params)
        
        # Guardar en caché
        norma_cache.set(id, result)
        
        return result.model_dump_json(indent=2)
    except NormaNotFoundError:
        raise


def recortar_texto(texto: str, inicio: int = 0, fin: Optional[int] = None) -> str:
    total = len(texto)
    
    if inicio < 0:
        inicio = 0
    
    if fin is None:
        fin = inicio + TEXT_CHUNK_SIZE
        
    if fin > total:
        fin = total
    
    # Asegurarnos de no devolver textos vacíos si se equivocan en los índices
    if inicio >= total:
        return f"[Error: El índice de inicio ({inicio}) es mayor o igual al total de caracteres ({total}).]"
        
    fragmento = texto[inicio:fin]
    
    # Agregar encabezado informativo
    encabezado = f"[Mostrando caracteres {inicio} a {fin} de un total de {total} caracteres.]\n"
    if fin < total:
        encabezado += f"[Para seguir leyendo, vuelve a llamar a la herramienta usando inicio={fin} y fin={fin + TEXT_CHUNK_SIZE} (o más)]\n"
    encabezado += "-" * 50 + "\n\n"
    
    return encabezado + fragmento


@mcp.tool()
def obtener_texto_actualizado(id: int, inicio: int = 0, fin: int = TEXT_CHUNK_SIZE) -> str:
    """
    Obtiene el texto VIGENTE de una norma (con todas sus modificaciones aplicadas).

    CUÁNDO USARLA: Es la opción preferida para conocer la ley tal cual rige hoy.
    Si no existe una versión actualizada, intentará devolver la original avisando al usuario.

    Para evitar abrumar el contexto, el texto se devuelve paginado. 
    Por defecto, devuelve fragmentos de 500 caracteres. Usa 'inicio' y 'fin' para iterar.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.
    - inicio: Índice del carácter desde donde empezar a leer (por defecto 0).
    - fin: Índice del carácter donde terminar de leer (por defecto 500).
    """
    # Intentar obtener de caché
    cached_texto = norma_cache.get_texto_actualizado(id)
    if cached_texto:
        return recortar_texto(cached_texto, inicio, fin)

    session = session_manager.get_session()
    try:
        norma_data = VerNormaResponse.model_validate_json(ver_norma(id))
    except NormaNotFoundError:
        return f"No se encontró una norma con el id incluido en la petición."
        
    client = InfolegClient()
    
    if norma_data.url_texto_actualizado:
        texto = client.consultar_anexo(session, norma_data.url_texto_actualizado)
        # Guardar en caché si se obtuvo algo
        if texto and not texto.startswith("No se encontró"):
             norma_cache.set_texto_actualizado(id, texto)
        return recortar_texto(texto, inicio, fin)
    return f"No se encontró texto disponible para la norma {id}."



@mcp.tool()
def obtener_texto_original(id: int, inicio: int = 0, fin: int = TEXT_CHUNK_SIZE) -> str:
    """
    Obtiene el texto ORIGINAL de una norma tal cual fue sancionada.

    CUÁNDO USARLA: Para investigación histórica o para ver la redacción inicial de una ley
    antes de cualquier reforma. No refleja necesariamente la ley vigente.

    Para evitar abrumar el contexto, el texto se devuelve paginado. 
    Por defecto, devuelve fragmentos de 500 caracteres. Usa 'inicio' y 'fin' para iterar.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.
    - inicio: Índice del carácter desde donde empezar a leer (por defecto 0).
    - fin: Índice del carácter donde terminar de leer (por defecto 500).
    """
    # Intentar obtener de caché
    cached_texto = norma_cache.get_texto_original(id)
    if cached_texto:
        return recortar_texto(cached_texto, inicio, fin)

    try:
        norma_data = VerNormaResponse.model_validate_json(ver_norma(id))
    except NormaNotFoundError:
        return f"No se encontró una norma con el id incluido en la petición."

    client = InfolegClient()
    session = session_manager.get_session()
    
    if not norma_data.url_texto_completo:
        return f"No se encontró el texto original para la norma {id}."
        
    texto = client.consultar_anexo(session, norma_data.url_texto_completo)
    
    # Guardar en caché si se obtuvo algo
    if texto and not texto.startswith("No se encontró"):
        norma_cache.set_texto_original(id, texto)
        
    return recortar_texto(texto, inicio, fin)


@mcp.tool()
def ver_normas_que_modifica(id: int) -> dict:
    """
    Devuelve las normas que esta norma modifica, deroga o complementa.

    CUÁNDO USARLA: Para rastrear el impacto de una norma sobre otras normas anteriores.
    Es la dirección ACTIVA: "esta norma actuó sobre cuáles otras".

    NO CONFUNDIR con ver_normas_que_la_modifican(), que es la dirección inversa.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.

    DEVUELVE: Lista de normas que fueron modificadas/derogadas/complementadas por esta norma.
    """
    # Intentar obtener de caché
    cached_vinculos = norma_cache.get_vinculos_modifica_a(id)
    if cached_vinculos:
        return cached_vinculos

    session = session_manager.get_session()
    client = InfolegClient()
    params = ParamsVerVinculos(id=id, modo=ModoVinculo.MODIFICA_A)
    
    result_json = client.ver_vinculos(session, params).model_dump_json(indent=2)
    
    # Guardar en caché
    norma_cache.set_vinculos_modifica_a(id, result_json)
    
    return result_json


@mcp.tool()
def ver_normas_que_la_modifican(id: int) -> dict:
    """
    Devuelve las normas que modificaron, derogaron o complementaron a esta norma.

    CUÁNDO USARLA: Para conocer el historial de modificaciones que recibió una norma,
    es decir, si está vigente o fue alterada. 
    Es la dirección PASIVA: "quién actuó sobre esta norma".

    NO CONFUNDIR con ver_normas_que_modifica(), que es la dirección inversa.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.

    DEVUELVE: Lista de normas que modificaron/derogaron/complementaron a esta norma.
    """
    # Intentar obtener de caché
    cached_vinculos = norma_cache.get_vinculos_modificada_por(id)
    if cached_vinculos:
        return cached_vinculos

    session = session_manager.get_session()
    client = InfolegClient()
    params = ParamsVerVinculos(id=id, modo=ModoVinculo.MODIFICADA_POR)
    
    result_json = client.ver_vinculos(session, params).model_dump_json(indent=2)
    
    # Guardar en caché
    norma_cache.set_vinculos_modificada_por(id, result_json)
    
    return result_json

def _build_search_request(
    tipo_norma: Optional[int],
    numero: Optional[int],
    anio_sancion: Optional[int],
    texto: Optional[str],
    dependencia: Optional[int],
    publicado_desde: Optional[date],
    publicado_hasta: Optional[date],
) -> BusquedaNormaRequest:
    """Valida los parámetros de entrada y construye el request para InfoLeg."""
    search_params = [tipo_norma, numero, anio_sancion, dependencia, publicado_desde, publicado_hasta]
    provided_params = sum(1 for p in search_params if p is not None)
    
    if not texto and provided_params < 2:
        raise ValueError(
            "Debe ingresar al menos 2 parámetros de búsqueda (por ejemplo: tipo_norma y numero) "
            "a menos que realice una búsqueda por texto."
        )

    if tipo_norma == 1 and anio_sancion is not None:
        raise ValueError("No se debe ingresar el año (anio_sancion) cuando se busca por tipo de norma Ley (tipo_norma=1).")

    return BusquedaNormaRequest(
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

def _fetch_infoleg_page(request: BusquedaNormaRequest, infoleg_page: int) -> BusquedaNormaResponse:
    """Maneja la sesión, la caché y la petición de una página específica a InfoLeg (INFOLEG_PAGE_SIZE resultados)."""
    client = InfolegClient()
    session_state = session_manager.get_search_session(request)
    session = session_state.session

    if session_state.first_request:
        result = client.buscar_normas(session, request)
        session_manager.put_pages_count(request, result.total_pags)
        session_state = session_manager.get_search_session(request)
        page_cache.set(request, 1, result)
        if infoleg_page == 1:
            return result

    if infoleg_page > session_state.total_pags:
        infoleg_page = session_state.total_pags

    cached_page = page_cache.get(request, infoleg_page)
    if cached_page:
        return cached_page

    pag_request = PaginacionRequest(irAPagina=infoleg_page, desplazamiento=ModoDesplazamiento.AVANZAR)
    result = client.navegar_normas(session, pag_request)
    page_cache.set(request, infoleg_page, result)
    return result

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
    """
    Busca normas jurídicas en Infoleg (Leyes, Decretos, Resoluciones, Disposiciones, etc.).
    Los resultados se ordenan por fecha de publicación, del más reciente al más antiguo.

    CUÁNDO USARLA: Cuando no se conoce el ID de la norma. Si ya tenés el ID, usá ver_norma().

    RESTRICCIONES:
    - Se requieren al menos 2 parámetros, EXCEPTO si se usa `texto` (que puede usarse solo).
    - Para Leyes (tipo_norma=1), NO ingresar anio_sancion (no es necesario).
    - Los números de norma deben ingresarse SIN puntos. Ej: 27275, no 27.275.

    PAGINACIÓN:
    - Primera llamada: no incluir nro_pag (devuelve los primeros resultados).
    - El resultado incluye `pagina_actual` y `total_pags` (basado en páginas virtuales del MCP).
    - Para páginas siguientes, repetir la misma llamada agregando nro_pag=2, 3, etc.

    PARÁMETROS:
    - tipo_norma: ID numérico del tipo de norma (consultar recurso `tipos-norma`).
                  Ej: 1=Ley, 2=Decreto.
    - numero: Número de la norma sin puntos. Si no se ingresa año, trae ese número de todos los años.
    - anio_sancion: Año de sanción en 4 dígitos. Acota resultados cuando se usa con `numero`.
                    NO usar si tipo_norma=1 (Ley).
    - dependencia: ID del organismo emisor. Usar buscar_dependencias() para obtener el ID.
    - publicado_desde / publicado_hasta: Rango de fechas de publicación en el Boletín Oficial.
                                         OJO: es fecha de publicación, NO de sanción. 
                                         Una norma sancionada a fin de año puede publicarse el año siguiente.
    - texto: Búsqueda por palabras clave. Puede usarse solo sin otros parámetros.
             El sistema busca por RAÍZ de palabra, por lo que se recomienda usar el comodín * .
             
             OPERADORES DISPONIBLES:
             - Y / AND         → ambas palabras. Ej: "aranceles Y aduaneros"
             - O / OR          → cualquiera. Ej: "aranceles O aduaneros" (operador por defecto)
             - NO / NOT        → excluye. Ej: "energía NOT eólica"
             - + palabra       → la palabra DEBE estar presente
             - - palabra       → la palabra NO debe estar presente
             - (...)           → agrupa términos, se evalúan primero
             - "frase exacta"  → busca la frase literal (NO se puede combinar con *)
             - * (comodín)     → reemplaza varios caracteres al final. Ej: "recurs*" encuentra recurso/recursos/recursivo
             - ? (comodín)     → reemplaza un solo carácter. Ej: "INT?" encuentra INTI o INTA

             EJEMPLOS DE TEXTO:
             - residu*                                      → residuo, residuos, residual...
             - "transporte de carga"                        → frase exacta
             - transporte Y (terrestre O marítimo)          → transporte terrestre o marítimo
             - exporta* AND bienes AND servicio*            → combina raíces
             - "plan nacional" NOT "política económica"     → incluye una frase, excluye otra

    DEVUELVE: Lista de normas con metadatos + pagina_actual + total_pags.
    """

    request = _build_search_request(
        tipo_norma, numero, anio_sancion, texto, dependencia, publicado_desde, publicado_hasta
    )

    mcp_page = nro_pag if nro_pag and nro_pag > 0 else 1
    
    # Cálculos para paginación interna (MCP=5 resultados, InfoLeg=50 resultados)
    infoleg_page = ((mcp_page - 1) * MCP_PAGE_SIZE) // INFOLEG_PAGE_SIZE + 1
    offset_in_infoleg = ((mcp_page - 1) * MCP_PAGE_SIZE) % INFOLEG_PAGE_SIZE
    
    infoleg_result = _fetch_infoleg_page(request, infoleg_page)
    
    # Recalcular total de páginas para el MCP
    total_mcp_pages = (infoleg_result.total + MCP_PAGE_SIZE - 1) // MCP_PAGE_SIZE
    
    # Obtener el slice de resultados
    mcp_resultados = infoleg_result.resultados[offset_in_infoleg : offset_in_infoleg + MCP_PAGE_SIZE]
    
    result_dict = {
        "resultados": [r.model_dump() for r in mcp_resultados],
        "pagina_actual": mcp_page,
        "total_pags": total_mcp_pages,
        # "infoleg_page" : infoleg_page,
        "total_resultados": infoleg_result.total
    }
    
    return json.dumps(result_dict, indent=2, default=str)





if __name__ == "__main__":
    mcp.run(transport="sse")
