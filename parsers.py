import re
from bs4 import BeautifulSoup
from typing import List
from models import BusquedaNormaResponse, NormaSummary
from urllib.parse import urlparse, parse_qs
from datetime import datetime


class InfoLegParser:
    @staticmethod
    def parse_busqueda_resultados(html: str) -> BusquedaNormaResponse:
        """
        Parsea el HTML de la página de resultados de InfoLeg.
        """
        match = re.search(r"Cantidad de Normas Encontradas:\s*(\d+)[\s\S]*?en\s*(\d+)", html)
        if not match:
            return BusquedaNormaResponse(resultados=[], nro_pag=1, total=0)

        total = int(match.group(1))
        pagina = int(match.group(2))

        soup = BeautifulSoup(html, "html.parser")
        
        try: 
            caja = soup.find("div", id="resultados_caja")
            tabla = caja.find("table")
        except Exception:
            return BusquedaNormaResponse(resultados=[], nro_pag=pagina, total=total)

        resultados = []
        for tr in tabla.find_all("tr"):
            tds = tr.find_all("td")

            # Saltar filas que no tienen las columnas de datos
            if len(tds) < 3:
                continue

            # Saltar el header de la tabla
            if "titulos_columnas" in tds[0].get("class", []):
                continue

            # --- td[0]
            td0 = tds[0]
            a_norma = td0.find("a")
            href_norma = a_norma["href"]

            # id de la norma
            id_norma = int(parse_qs(urlparse(href_norma).query)["id"][0])

            # textos limpios dentro del td
            textos = list(td0.stripped_strings)

            # identidad y organismo
            identidad_norma = textos[0] if len(textos) > 0 else None
            organismo_emisor = textos[1] if len(textos) > 1 else None

            # limpiar mal formato en html
            identidad_norma = " ".join(identidad_norma.split())

            # --- td[1]
            a_boletin = tds[1].find("a")
            href_boletin = a_boletin["href"]
            id_boletin = int(parse_qs(urlparse(href_boletin).query)["id"][0])
            fecha_str = a_boletin.get_text(strip=True)


            meses_num = {
                "ene": 1, "feb": 2, "mar": 3, "abr": 4,
                "may": 5, "jun": 6, "jul": 7, "ago": 8,
                "sep": 9, "oct": 10, "nov": 11, "dic": 12
            }
            d, m, y = fecha_str.split("-")
            fecha_publicacion = datetime(int(y), meses_num[m.lower()], int(d))


            # --- td[2]
            organismo_padre = organismo_emisor
            tema = tds[2].find("b").get_text(strip=True)
            sumario = tds[2].find("span").get_text(strip=True)
            resultados.append(
                NormaSummary(
                    id = id_norma,
                    identidad_norma = identidad_norma,
                    organismo_emisor = organismo_emisor,
                    id_boletin = id_boletin,
                    fecha_publicacion = fecha_publicacion,
                    organismo_padre = organismo_padre,
                    tema = tema,
                    sumario = sumario,
                )
            )
        return BusquedaNormaResponse(resultados=resultados, nro_pag=pagina, total=total)
