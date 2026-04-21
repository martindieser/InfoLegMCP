import json
import unicodedata
from rapidfuzz import process, fuzz
from typing import Optional, TypeVar, Callable, List, Tuple
from datetime import date
from models import *
from client import InfolegClient
from sessmanager import SessionManager
from parsers import NormaNotFoundError



class Paginator:
    def __init__(self, virtual_page_size: int, real_page_size: int):
        self.virtual_page_size = virtual_page_size
        self.real_page_size = real_page_size

    def get_page_dict(self, virtual_page: int, fetch_real_page: Callable[[int], Tuple[List[T], int]]) -> dict:
        """
        Obtiene una página virtual y devuelve el diccionario de respuesta estandarizado.
        """
        real_page = ((virtual_page - 1) * self.virtual_page_size) // self.real_page_size + 1
        offset_in_real = ((virtual_page - 1) * self.virtual_page_size) % self.real_page_size

        real_items, total_items = fetch_real_page(real_page)

        total_virtual_pages = (total_items + self.virtual_page_size - 1) // self.virtual_page_size
        virtual_items = real_items[offset_in_real : offset_in_real + self.virtual_page_size]

        return {
            "resultados": [r.model_dump() if hasattr(r, 'model_dump') else r for r in virtual_items],
            "pagina_actual": virtual_page,
            "total_pags": total_virtual_pages,
            "total_resultados": total_items
        }

class DependenciaService:
    """Servicio para el dominio de Dependencias y Catálogos."""
    def __init__(self, path_dependencias: str = "./data/dependencias.json", path_tipos_norma: str = "./data/tipos_norma.json"):
        self.path_dependencias = path_dependencias
        self.path_tipos_norma = path_tipos_norma

    def get_tipos_norma(self) -> str:
        with open(self.path_tipos_norma) as f:
            return f.read()

    def get_by_id(self, id: int) -> dict:
        with open(self.path_dependencias) as f:
            deps = json.load(f)
        result = next((d for d in deps if d["id"] == id), None)
        if not result:
            raise ValueError(f"No se encontró dependencia con ID {id}")
        return result

    def normalize(self, text: str) -> str:
        text = text.lower()
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")

    def buscar(self, query: str, limit: int = 10) -> list:
        with open(self.path_dependencias) as f:
            deps = json.load(f)
        choices = {i: self.normalize(d["nombre"]) for i, d in enumerate(deps)}
        matches = process.extract(
            self.normalize(query),
            choices,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=70
        )
        return [deps[i] for _, _, i in matches]

class NormaService:
    """Servicio para el dominio de Normas Jurídicas."""
    def __init__(
        self, 
        client: InfolegClient, 
        session_manager: SessionManager,
        infoleg_page_size: int = 50,
        mcp_page_size: int = 5,
        text_chunk_size: int = 500
    ):
        self.client = client
        self.session_manager = session_manager
        self.infoleg_page_size = infoleg_page_size
        self.mcp_page_size = mcp_page_size
        self.text_chunk_size = text_chunk_size
        self.paginator = Paginator(virtual_page_size=mcp_page_size, real_page_size=infoleg_page_size)

    def ver_norma(self, id: int) -> str:
        session = self.session_manager.get_session()
        params = ParamsVerNorma(id=id)
        try:
            result = self.client.ver_norma(session, params)
            return result.model_dump_json(indent=2)
        except NormaNotFoundError:
            raise

    def recortar_texto(self, texto: str, inicio: int = 0, fin: Optional[int] = None) -> str:
        total = len(texto)
        if inicio < 0: inicio = 0
        if fin is None: fin = inicio + self.text_chunk_size
        if fin > total: fin = total
        if inicio >= total:
            return f"[Error: El índice de inicio ({inicio}) es mayor o igual al total de caracteres ({total}).]"
        fragmento = texto[inicio:fin]
        encabezado = f"[Mostrando caracteres {inicio} a {fin} de un total de {total} caracteres.]\n"
        if fin < total:
            encabezado += f"[Para seguir leyendo, vuelve a llamar a la herramienta usando inicio={fin} y fin={fin + self.text_chunk_size} (o más)]\n"
        encabezado += "-" * 50 + "\n\n"
        return encabezado + fragmento


    def obtener_texto(self, id: int, tipo: TipoTexto, inicio: int = 0, fin: Optional[int] = None) -> str:
        if fin is None:
            fin = inicio + self.text_chunk_size
            
        session = self.session_manager.get_session()
        try:
            norma_data = VerNormaResponse.model_validate_json(self.ver_norma(id))
        except NormaNotFoundError:
            return f"No se encontró una norma con el id incluido en la petición."
        
        url = norma_data.url_texto_actualizado if tipo == TipoTexto.ACTUALIZADO else norma_data.url_texto_completo
        
        if url:
            if tipo == TipoTexto.ACTUALIZADO:
                texto = self.client.consultar_texto_actualizado(session, id, url)
            else:
                texto = self.client.consultar_texto_original(session, id, url)
            return self.recortar_texto(texto, inicio, fin)
            
        return f"No se encontró el texto {tipo.value} para la norma {id}."

    def ver_vinculos(self, id: int, modo: ModoVinculo, nro_pag: Optional[int] = None) -> str:
        session = self.session_manager.get_session()
        params = ParamsVerVinculos(id=id, modo=modo)
        result = self.client.ver_vinculos(session, params)
        
        mcp_page = nro_pag if nro_pag and nro_pag > 0 else 1
        
        total_items = len(result.vinculos)
        paginator = Paginator(virtual_page_size=self.mcp_page_size, real_page_size=max(total_items, 1))
        
        def fetch_memory_page(real_page_num: int):
            return result.vinculos, total_items
            
        result_dict = paginator.get_page_dict(mcp_page, fetch_memory_page)
        return json.dumps(result_dict, indent=2, default=str)

    def _build_search_request(
        self,
        tipo_norma: Optional[int] = None,
        numero: Optional[int] = None,
        anio_sancion: Optional[int] = None,
        texto: Optional[str] = None,
        dependencia: Optional[int] = None,
        publicado_desde: Optional[date] = None,
        publicado_hasta: Optional[date] = None,
    ) -> BusquedaNormaRequest:
        search_params = [tipo_norma, numero, anio_sancion, dependencia, publicado_desde, publicado_hasta]
        provided_params = sum(1 for p in search_params if p is not None)
        
        if not texto and provided_params < 2:
            raise ValueError("Debe ingresar al menos 2 parámetros de búsqueda.")
        if tipo_norma == 1 and anio_sancion is not None:
            raise ValueError("No se debe ingresar el año para tipo de norma Ley (tipo_norma=1).")
            
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

    def buscar_normas(
        self,
        tipo_norma: Optional[int] = None,
        numero: Optional[int] = None,
        anio_sancion: Optional[int] = None,
        texto: Optional[str] = None,
        dependencia: Optional[int] = None,
        publicado_desde: Optional[date] = None,
        publicado_hasta: Optional[date] = None,
        nro_pag: Optional[int] = None,
    ) -> str:
        request = self._build_search_request(
            tipo_norma=tipo_norma,
            numero=numero,
            anio_sancion=anio_sancion,
            texto=texto,
            dependencia=dependencia,
            publicado_desde=publicado_desde,
            publicado_hasta=publicado_hasta
        )
        mcp_page = nro_pag if nro_pag and nro_pag > 0 else 1

        def fetch_page(real_page_num: int) -> Tuple[List[NormaSummary], int]:
            session_state = self.session_manager.get_search_session(request)
            session = session_state.session
            
            if session_state.first_request:
                result = self.client.buscar_normas(session, request)
                self.session_manager.put_pages_count(request, result.total_pags)
                session_state = self.session_manager.get_search_session(request)
                if real_page_num == 1:
                    return result.resultados, result.total
            
            if real_page_num > 1:
                p_req = PaginacionRequest(
                    irAPagina=min(real_page_num, session_state.total_pags), 
                    desplazamiento=ModoDesplazamiento.AVANZAR
                )
                res = self.client.navegar_normas(session, p_req)
            else:
                res = self.client.buscar_normas(session, request)
                
            return res.resultados, res.total

        result_dict = self.paginator.get_page_dict(mcp_page, fetch_page)
        return json.dumps(result_dict, indent=2, default=str)
