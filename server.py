import requests
import json
import unicodedata
from mcp.server.fastmcp import FastMCP
from rapidfuzz import process, fuzz
from typing import Optional
from client import InfolegClient, BASE_URL
from cache import SessionCache, PageCache, SearchSessionState, NormaCache
from datetime import date
from models import *

mcp = FastMCP("InfoLeg MCP", json_response=True)
session_cache = SessionCache()
page_cache = PageCache()
norma_cache = NormaCache()

PATH_DEPENDENCIAS = "./data/dependencias.json"
PATH_TIPOS_NORMA = "./data/tipos_norma.json"


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
    Obtiene el texto completo y metadatos de una norma por su ID de Infoleg.

    CUÁNDO USARLA: Cuando se conoce el ID de la norma (obtenido de buscar_normas()).
    Para buscar normas sin ID, usar buscar_normas() primero.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.

    DEVUELVE: Texto completo (si disponible) y metadatos de la norma.
    NOTA: Las normas anteriores a 1997 o de carácter particular pueden no tener texto completo,
    pero sí sus vínculos y referencias.
    """
    # Intentar obtener de la caché
    cached_norma = norma_cache.get(id)
    if cached_norma:
        return cached_norma.model_dump_json(indent=2)

    session = requests.Session()
    client = InfolegClient()
    params = ParamsVerNorma(id=id)
    result = client.ver_norma(session, params)
    
    # Guardar en caché
    norma_cache.set(id, result)
    
    return result.model_dump_json(indent=2)


@mcp.tool()
def obtener_texto_actualizado(id: int) -> str:
    """
    Obtiene el texto VIGENTE de una norma (con todas sus modificaciones aplicadas).

    CUÁNDO USARLA: Es la opción preferida para conocer la ley tal cual rige hoy.
    Si no existe una versión actualizada, intentará devolver la original avisando al usuario.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.
    """
    session = requests.Session()
    norma_data = VerNormaResponse.model_validate_json(ver_norma(id))
    client = InfolegClient()
    
    if norma_data.url_texto_actualizado:
        return client.consultar_anexo(session, norma_data.url_texto_actualizado)

    return f"No se encontró texto disponible para la norma {id}."


@mcp.tool()
def obtener_texto_original(id: int) -> str:
    """
    Obtiene el texto ORIGINAL de una norma tal cual fue sancionada.

    CUÁNDO USARLA: Para investigación histórica o para ver la redacción inicial de una ley
    antes de cualquier reforma. No refleja necesariamente la ley vigente.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.
    """
    session = requests.Session()
    norma_data = VerNormaResponse.model_validate_json(ver_norma(id))
    client = InfolegClient()
    
    if not norma_data.url_texto_completo:
        return f"No se encontró el texto original para la norma {id}."
        
    return client.consultar_anexo(norma_data.url_texto_completo)


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
    session = requests.Session()
    client = InfolegClient()
    params = ParamsVerVinculos(id=id, modo=ModoVinculo.MODIFICA_A)
    return client.ver_vinculos(session, params).model_dump_json(indent=2)


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
    """
    Busca normas jurídicas en Infoleg (Leyes, Decretos, Resoluciones, Disposiciones, etc.).
    Los resultados se ordenan por fecha de publicación, del más reciente al más antiguo.

    CUÁNDO USARLA: Cuando no se conoce el ID de la norma. Si ya tenés el ID, usá ver_norma().

    RESTRICCIONES:
    - Se requieren al menos 2 parámetros, EXCEPTO si se usa `texto` (que puede usarse solo).
    - Para Leyes (tipo_norma=1), NO ingresar anio_sancion (no es necesario).
    - Los números de norma deben ingresarse SIN puntos. Ej: 27275, no 27.275.

    PAGINACIÓN:
    - Primera llamada: no incluir nro_pag.
    - El resultado incluye `pagina_actual` y `total_pags`.
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

    DEVUELVE: Lista de normas con metadatos (tipo, número, título, fecha, dependencia) + pagina_actual + total_pags.
    """

    
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
