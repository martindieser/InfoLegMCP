import json
from mcp.server.fastmcp import FastMCP
from typing import Optional
from datetime import date
from client import InfolegClient
from models import ModoVinculo, TipoTexto
from sessmanager import SessionManager
from services import (
    DependenciaService,
    NormaService,
)

mcp = FastMCP("InfoLeg MCP", json_response=True)
session_manager = SessionManager()
client = InfolegClient()

# Instanciar servicios por dominio con su configuración
dependencia_svc = DependenciaService(
    path_dependencias="./data/dependencias.json",
    path_tipos_norma="./data/tipos_norma.json"
)
norma_svc = NormaService(
    client, 
    session_manager,
    infoleg_page_size=50,
    mcp_page_size=5,
    text_chunk_size=500
)

@mcp.resource("file://tipos-norma")
def get_tipos_norma() -> str:
    """Devuelve el catálogo de tipos de norma con su ID y nombre.
    SIEMPRE llamar esta tool antes de usar tipo_norma en buscar_normas()."""
    return dependencia_svc.get_tipos_norma()

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
    return dependencia_svc.get_by_id(id)

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
    return dependencia_svc.buscar(query, limit)

@mcp.tool()
def ver_norma(id: int) -> str:
    """
    Obtiene los metadatos de una norma por su ID de Infoleg.

    CUÁNDO USARLA: Cuando se conoce el ID de la norma (obtenido de buscar_normas()).
    Para buscar normas sin ID, usar buscar_normas() primero.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.

    DEVUELVE: Metadatos de la norma.
    """
    return norma_svc.ver_norma(id)

@mcp.tool()
def obtener_texto_actualizado(id: int, inicio: int = 0, fin: Optional[int] = None) -> str:
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
    return norma_svc.obtener_texto(id, TipoTexto.ACTUALIZADO, inicio, fin)

@mcp.tool()
def obtener_texto_original(id: int, inicio: int = 0, fin: Optional[int] = None) -> str:
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
    return norma_svc.obtener_texto(id, TipoTexto.ORIGINAL, inicio, fin)

@mcp.tool()
def ver_normas_que_modifica(id: int, nro_pag: Optional[int] = None) -> str:
    """
    Devuelve las normas que esta norma modifica, deroga o complementa.

    CUÁNDO USARLA: Para rastrear el impacto de una norma sobre otras normas anteriores.
    Es la dirección ACTIVA: "esta norma actuó sobre cuáles otras".

    NO CONFUNDIR con ver_normas_que_la_modifican(), que es la dirección inversa.

    PAGINACIÓN:
    - Primera llamada: no incluir nro_pag (devuelve los primeros resultados).
    - El resultado incluye `pagina_actual` y `total_pags` (basado en páginas virtuales del MCP).
    - Para páginas siguientes, repetir la misma llamada agregando nro_pag=2, 3, etc.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.
    - nro_pag: Número de página virtual (MCP).

    DEVUELVE: Lista de normas que fueron modificadas/derogadas/complementadas por esta norma.
    """
    return norma_svc.ver_vinculos(id, ModoVinculo.MODIFICA_A, nro_pag)

@mcp.tool()
def ver_normas_que_la_modifican(id: int, nro_pag: Optional[int] = None) -> str:
    """
    Devuelve las normas que modificaron, derogaron o complementaron a esta norma.

    CUÁNDO USARLA: Para conocer el historial de modificaciones que recibió una norma,
    es decir, si está vigente o fue alterada. 
    Es la dirección PASIVA: "quién actuó sobre esta norma".

    NO CONFUNDIR con ver_normas_que_modifica(), que es la dirección inversa.

    PAGINACIÓN:
    - Primera llamada: no incluir nro_pag (devuelve los primeros resultados).
    - El resultado incluye `pagina_actual` y `total_pags` (basado en páginas virtuales del MCP).
    - Para páginas siguientes, repetir la misma llamada agregando nro_pag=2, 3, etc.

    PARÁMETROS:
    - id: ID numérico de la norma en Infoleg.
    - nro_pag: Número de página virtual (MCP).

    DEVUELVE: Lista de normas que modificaron/derogaron/complementaron a esta norma.
    """
    return norma_svc.ver_vinculos(id, ModoVinculo.MODIFICADA_POR, nro_pag)

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
) -> str:
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
    return norma_svc.buscar_normas(
        tipo_norma=tipo_norma,
        numero=numero,
        anio_sancion=anio_sancion,
        texto=texto,
        dependencia=dependencia,
        publicado_desde=publicado_desde,
        publicado_hasta=publicado_hasta,
        nro_pag=nro_pag
    )

if __name__ == "__main__":
    mcp.run(transport="sse")
