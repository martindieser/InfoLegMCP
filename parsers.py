from models import NormaSummary \
                , BusquedaNormaResponse \
                , VerNormaResponse \
                , VerVinculosResponse \
                , VinculoNormaSummary

from typing import Optional, List, Dict, Any, Tuple
from datetime import date
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup, Tag

import re

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

class NotFindingPageNumeration(Exception):
    pass

class BaseParser:
    """Clase base con utilidades comunes para los parsers de InfoLeg."""
    
    def _get_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def _clean_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        
        text = text.replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _parse_date(self, texto: str) -> Optional[date]:
        """Convierte una fecha en formato 'dd-mes-yyyy' a date."""
        if not texto:
            return None
        match = re.search(r"(\d{1,2})-([a-z]{3})-(\d{4})", texto.strip().lower())
        if match:
            day, mes_str, year = match.groups()
            mes = MESES.get(mes_str)
            if mes:
                return date(int(year), mes, int(day))
        return None

    def _extract_id(self, source: str) -> Optional[int]:
        """Extrae un ID numérico de una URL o un string de parámetros."""
        if not source:
            return None
        # Intenta parsear como query param 'id='
        if "id=" in source:
            try:
                # Caso URL completa o query string
                parsed = parse_qs(urlparse(source).query)
                if "id" in parsed:
                    return int(parsed["id"][0])
                # Caso string simple 'id=123'
                match = re.search(r"id=(\d+)", source)
                if match:
                    return int(match.group(1))
            except (ValueError, IndexError):
                pass
        
        # Intenta parsear de path tipo /12345/norma.htm
        match = re.search(r"/(\d+)/(?:norma|texact)\.htm", source)
        if match:
            return int(match.group(1))
            
        return None

class InfoLegBusquedasParser(BaseParser):

    def _parse_total_y_pagina(self, html: str) -> Dict[str, int]:
        """Extrae el total de normas y el número de página del HTML."""
        match = re.search(r"Cantidad de Normas Encontradas:\s*(\d+)[\s\S]*?en\s*(\d+)", html)
        if not match:
            return {} 
        return {"total": int(match.group(1)), "nro_pag": int(match.group(2))}

    def _parse_tabla_resultados(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Extrae la tabla de resultados del soup."""
        try:
            return soup.find("div", id="resultados_caja").find("table")
        except AttributeError:
            return None

    def _parse_td_norma(self, td: Tag) -> Dict[str, Any]:
        """Parsea el primer td de una fila de resultados."""
        a_norma = td.find("a")
        if not a_norma:
            return {}
            
        id_norma = self._extract_id(a_norma.get("href", ""))
        textos = list(td.stripped_strings)
        identidad_norma = self._clean_text(textos[0]) if len(textos) > 0 else ""
        organismo_emisor = textos[1] if len(textos) > 1 else None
        
        return {
            "id": id_norma, 
            "identidad_norma": identidad_norma, 
            "organismo_emisor": organismo_emisor,
            "organismo_padre": organismo_emisor
        }

    def _parse_td_boletin(self, td: Tag) -> Dict[str, Any]:
        """Parsea el segundo td de una fila de resultados."""
        a_boletin = td.find("a")
        if not a_boletin:
            return {}
            
        id_boletin = self._extract_id(a_boletin.get("href", ""))
        fecha_publicacion = self._parse_date(a_boletin.get_text(strip=True))
        
        return {
            "id_boletin": id_boletin, 
            "fecha_publicacion": fecha_publicacion
        }

    def _parse_td_tema(self, td: Tag) -> Dict[str, str]:
        """Parsea el tercer td de una fila de resultados."""
        b_tag = td.find("b")
        span_tag = td.find("span")
        
        if not b_tag or not span_tag:
            return {}
            
        return {
            "tema": b_tag.get_text(strip=True), 
            "sumario": span_tag.get_text(strip=True)
        }

    def _es_fila_datos(self, tds: List[Tag]) -> bool:
        if len(tds) < 3:
            return False
        if "titulos_columnas" in tds[0].get("class", []):
            return False
        return True

    def parse(self, html: str) -> BusquedaNormaResponse:
        paginacion = self._parse_total_y_pagina(html)
        total = paginacion.get("total", 0)
        pagina = paginacion.get("nro_pag", 1)

        soup = self._get_soup(html)
        tabla = self._parse_tabla_resultados(soup)
        if tabla is None:
            return BusquedaNormaResponse(resultados=[], nro_pag=pagina, total=total)

        resultados = []
        for tr in tabla.find_all("tr"):
            tds = tr.find_all("td")
            if not self._es_fila_datos(tds):
                continue

            datos_norma = self._parse_td_norma(tds[0])
            datos_boletin = self._parse_td_boletin(tds[1])
            datos_tema = self._parse_td_tema(tds[2])

            if (not datos_norma) or (not datos_tema):
                continue

            resultados.append(NormaSummary(
                **datos_norma,
                **datos_boletin,
                **datos_tema
            ))

        return BusquedaNormaResponse(resultados=resultados, nro_pag=pagina, total=total)


class InfolegNormaParser(BaseParser):
    def parse(self, html: str) -> VerNormaResponse:
        soup = self._get_soup(html)
        textos = soup.find("div", id="Textos_Completos")

        identidad_norma, organismo_emisor = self._parse_identidad(textos)
        fecha_emision = self._parse_fecha_emision(textos)
        organismo_padre = textos.find("span", class_="destacado").get_text(strip=True)
        tema = textos.find("h1").get_text(strip=True)
        id_boletin, fecha_publicacion, pagina_boletin = self._parse_boletin(textos)
        sumario = self._parse_sumario(textos)
        url_completo, url_actualizado = self._parse_urls(textos)
        norma_id = self._extract_id(url_completo or url_actualizado or "")
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
        return self._parse_date(span.get_text(strip=True))

    def _parse_boletin(self, textos) -> Tuple[Optional[int], Optional[date], Optional[int]]:
        p = next(p for p in textos.find_all("p") if "Publicada" in p.get_text())
        links = p.find_all("a")
        id_boletin = self._extract_id(links[0]["href"]) if links else None
        fecha = self._parse_date(links[0].get_text(strip=True)) if links else None
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


class VerVinculosParser(BaseParser):

    def __init__(self, html: str, id_norma: int):
        self._soup = self._get_soup(html)
        self._id_norma = id_norma

    def parse(self) -> VerVinculosResponse:
        vinculos: list[NormaSummary] = []
        celdas = self._soup.select("td.vr_azul11")

        i = 0
        while i < len(celdas) - 2:
            norma = self._parse_norma(celdas[i], celdas[i + 1], celdas[i + 2])
            if norma:
                vinculos.append(norma)
                i += 3
            else:
                i += 1

        return VerVinculosResponse(id=self._id_norma, vinculos=vinculos)

    def _parse_norma(self, celda_norma, celda_fecha, celda_desc) -> Optional[VinculoNormaSummary]:
        link = celda_norma.find("a")
        if not link:
            return None

        id_vinculo = self._extract_id(link.get("href", ""))
        if not id_vinculo:
            return None

        textos = list(celda_norma.stripped_strings)

        identidad = self._clean_text(textos[0]) if textos else None
        organismo_emisor = self._clean_text(textos[1]) if len(textos) > 1 else None
        fecha_pub = self._parse_date(celda_fecha.get_text())
        organismo_padre_tag = celda_desc.find("b")
        organismo_padre = self._clean_text(organismo_padre_tag.get_text()) if organismo_padre_tag else ""
        br = celda_desc.find("br")
        tema = self._clean_text(str(br.next_sibling)) if br and br.next_sibling else ""

        return VinculoNormaSummary(
            id=id_vinculo,
            identidad_norma=identidad,
            organismo_emisor=organismo_emisor,
            fecha_publicacion=fecha_pub,
            organismo_padre=organismo_padre,
            tema=tema,
        )
