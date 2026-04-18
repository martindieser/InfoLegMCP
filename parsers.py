from models import BusquedaNormaResponse, NormaSummary
from typing import Optional, List, Dict, Any
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup, Tag

class InfoLegParser:

    @staticmethod
    def _parse_total_y_pagina(html: str) -> Dict[str, int]:
        """Extrae el total de normas y el número de página del HTML."""
        match = re.search(r"Cantidad de Normas Encontradas:\s*(\d+)[\s\S]*?en\s*(\d+)", html)
        if not match:
            return {} # Retorna dict vacío en vez de None
        return {"total": int(match.group(1)), "nro_pag": int(match.group(2))}

    @staticmethod
    def _parse_tabla_resultados(soup: BeautifulSoup) -> Optional[Tag]:
        """Extrae la tabla de resultados del soup."""
        try:
            return soup.find("div", id="resultados_caja").find("table")
        except AttributeError:
            return None

    @staticmethod
    def _parse_td_norma(td: Tag) -> Dict[str, Any]:
        """Parsea el primer td de una fila de resultados."""
        a_norma = td.find("a")
        if not a_norma:
            return {}
            
        id_norma = int(parse_qs(urlparse(a_norma["href"]).query)["id"][0])
        textos = list(td.stripped_strings)
        identidad_norma = " ".join(textos[0].split()) if len(textos) > 0 else ""
        organismo_emisor = textos[1] if len(textos) > 1 else None
        
        return {
            "id": id_norma, 
            "identidad_norma": identidad_norma, 
            "organismo_emisor": organismo_emisor,
            "organismo_padre": organismo_emisor # Reutilizamos el valor aquí
        }

    @staticmethod
    def _parse_fecha_boletin(fecha_str: str) -> datetime:
        """Convierte una fecha en formato 'dd-mes-yyyy' a datetime."""
        meses_num = {
            "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, 
            "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12
        }
        d, m, y = fecha_str.split("-")
        return datetime(int(y), meses_num[m.lower()], int(d))

    @staticmethod
    def _parse_td_boletin(td: Tag) -> Dict[str, Any]:
        """Parsea el segundo td de una fila de resultados."""
        a_boletin = td.find("a")
        if not a_boletin:
            return {}
            
        id_boletin = int(parse_qs(urlparse(a_boletin["href"]).query)["id"][0])
        fecha_publicacion = InfoLegParser._parse_fecha_boletin(a_boletin.get_text(strip=True))
        
        return {
            "id_boletin": id_boletin, 
            "fecha_publicacion": fecha_publicacion
        }

    @staticmethod
    def _parse_td_tema(td: Tag) -> Dict[str, str]:
        """Parsea el tercer td de una fila de resultados."""
        b_tag = td.find("b")
        span_tag = td.find("span")
        
        if not b_tag or not span_tag:
            return {}
            
        return {
            "tema": b_tag.get_text(strip=True), 
            "sumario": span_tag.get_text(strip=True)
        }

    @staticmethod
    def _es_fila_datos(tds: List[Tag]) -> bool:
        if len(tds) < 3:
            return False
        if "titulos_columnas" in tds[0].get("class", []):
            return False
        return True

    @staticmethod
    def parse_busqueda_resultados(html: str) -> BusquedaNormaResponse:
        paginacion = InfoLegParser._parse_total_y_pagina(html)
        # Si no hay datos, paginacion es {}, usamos .get() con valores default
        total = paginacion.get("total", 0)
        pagina = paginacion.get("nro_pag", 1)

        soup = BeautifulSoup(html, "html.parser")
        tabla = InfoLegParser._parse_tabla_resultados(soup)

        if tabla is None:
            return BusquedaNormaResponse(resultados=[], nro_pag=pagina, total=total)

        resultados = []
        for tr in tabla.find_all("tr"):
            tds = tr.find_all("td")
            if not InfoLegParser._es_fila_datos(tds):
                continue

            datos_norma = InfoLegParser._parse_td_norma(tds[0])
           
            datos_boletin = InfoLegParser._parse_td_boletin(tds[1])
            datos_tema = InfoLegParser._parse_td_tema(tds[2])

            if (not datos_norma) or (not datos_tema):
                continue
 

            # Construcción ultra limpia
            resultados.append(NormaSummary(
                **datos_norma,
                **datos_boletin,
                **datos_tema
            ))

        return BusquedaNormaResponse(resultados=resultados, nro_pag=pagina, total=total)