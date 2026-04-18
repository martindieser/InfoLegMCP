from models import BusquedaNormaResponse, NormaSummary, VerNormaResponse
from typing import Optional, List, Dict, Any, Tuple
from datetime import date
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup, Tag

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

class InfoLegBusquedasParser:
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
        
        d, m, y = fecha_str.split("-")
        return datetime(int(y), MESES[m.lower()], int(d))

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
    def parse(html: str) -> BusquedaNormaResponse:
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


class InfolegNormaParser:
    def parse(self, html: str) -> VerNormaResponse:
        soup = BeautifulSoup(html, "html.parser")
        textos = soup.find("div", id="Textos_Completos")

        identidad_norma, organismo_emisor = self._parse_identidad(textos)
        fecha_emision = self._parse_fecha_emision(textos)
        organismo_padre = textos.find("span", class_="destacado").get_text(strip=True)
        tema = textos.find("h1").get_text(strip=True)
        id_boletin, fecha_publicacion, pagina_boletin = self._parse_boletin(textos)
        sumario = self._parse_sumario(textos)
        url_completo, url_actualizado = self._parse_urls(textos)
        norma_id = self._parse_id_from_url(url_completo or url_actualizado or "")
        normas_modifica, normas_modifican = self._parse_vinculos(textos)

        return VerNormaResponse(
            summary=NormaSummary(
                id=norma_id,
                identidad_norma=identidad_norma,
                organismo_emisor=organismo_emisor,
                id_boletin=id_boletin,
                fecha_publicacion=fecha_publicacion,
                organismo_padre=organismo_padre,
                tema=tema,
                sumario=sumario,
            ),
            fecha_emision=fecha_emision,
            pagina_boletin=pagina_boletin,
            url_texto_completo=url_completo,
            url_texto_actualizado=url_actualizado,
            normas_que_modifica=normas_modifica,
            normas_que_modifican_esta=normas_modifican,
        )

    def _parse_identidad(self, textos) -> Tuple[str, str]:
        strong = textos.find("p").find("strong")
        lines = [l.strip() for l in strong.get_text("\n").splitlines() if l.strip()]
        return " ".join(lines[:-1]), lines[-1]

    def _parse_fecha_emision(self, textos) -> Optional[date]:
        span = textos.find("p").find("span", class_="vr_azul11")
        return self._parse_fecha(span.get_text(strip=True))

    def _parse_boletin(self, textos) -> Tuple[Optional[int], Optional[date], Optional[int]]:
        p = next(p for p in textos.find_all("p") if "Publicada" in p.get_text())
        links = p.find_all("a")
        id_boletin = int(links[0]["href"].split("id=")[-1]) if links else None
        fecha = self._parse_fecha(links[0].get_text(strip=True)) if links else None
        match = re.search(r"P[aá]gina:\s*(\d+)", p.get_text())
        pagina = int(match.group(1)) if match else None
        return id_boletin, fecha, pagina

    def _parse_sumario(self, textos) -> str:
        p = next(p for p in textos.find_all("p") if "Resumen" in p.get_text())
        return re.sub(r"Resumen\s*:", "", p.get_text(separator=" ", strip=True)).strip()

    def _parse_urls(self, textos) -> Tuple[Optional[str], Optional[str]]:
        url_completo = url_actualizado = None
        for a in textos.find_all("a"):
            href = a.get("href", "")
            if "norma.htm" in href:
                url_completo = href
            elif "texact.htm" in href:
                url_actualizado = href
        return url_completo, url_actualizado

    def _parse_vinculos(self, textos) -> Tuple[Optional[int], Optional[int]]:
        modifica = modifican = None
        for a in textos.find_all("a"):
            match = re.search(r"(\d+)\s+norma", a.get_text(strip=True))
            if match:
                cantidad = int(match.group(1))
                if "modo=1" in a.get("href", ""):
                    modifica = cantidad
                elif "modo=2" in a.get("href", ""):
                    modifican = cantidad
        return modifica, modifican

    def _parse_id_from_url(self, url: str) -> Optional[int]:
        match = re.search(r"/(\d+)/(?:norma|texact)\.htm", url)
        return int(match.group(1)) if match else None

    def _parse_fecha(self, texto: str) -> Optional[date]:
        match = re.match(r"(\d{1,2})-([a-z]{3})-(\d{4})", texto.strip().lower())
        if match:
            day, mes_str, year = match.groups()
            mes = MESES.get(mes_str)
            if mes:
                return date(int(year), mes, int(day))
        return None