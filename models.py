from pydantic import BaseModel, computed_field 
from typing import Optional, List
from datetime import date

class TipoNorma(BaseModel):
    id: int
    nombre: str

class Dependencia(BaseModel):
    id: int
    nombre: str

class BusquedaNorma(BaseModel):
    tipo_norma: Optional[TipoNorma] = None
    numero: Optional[int] = None
    anio_sancion: Optional[int] = None
    texto: Optional[str] = None
    dependencia: Optional[Dependencia] = None
    fecha_pub_desde: Optional[date] = None
    fecha_pub_hasta: Optional[date] = None

class BusquedaNormaRequest(BaseModel):
    # Nombres exactos de los parámetros del formulario POST de InfoLeg
    tipoNorma: Optional[int] = None
    numero: Optional[int] = None
    anio_sancion: Optional[int] = None
    texto: Optional[str] = None
    dependencia: Optional[int] = None
    diaPubDesde: Optional[int] = None
    mesPubDesde: Optional[int] = None
    anioPubDesde: Optional[int] = None
    diaPubHasta: Optional[int] = None
    mesPubHasta: Optional[int] = None
    anioPubHasta: Optional[int] = None

class PaginacionRequest(BaseModel):
    desplazamiento: str  # 'AP' para avanzar, 'RP' para retroceder
    irAPagina: int

class NormaSummary(BaseModel):
    id: int
    identidad_norma : str
    organismo_emisor: str

    id_boletin: Optional[int] = None
    fecha_publicacion: Optional[date] = None

    organismo_padre: str
    tema : str
    sumario: str

class BusquedaNormaResponse(BaseModel):
    resultados: List[NormaSummary]
    nro_pag: int
    total: int
    @computed_field
    @property
    def cant_resultados(self) -> int:
        return len(self.resultados)
