from pydantic import BaseModel, computed_field, ConfigDict
from typing import Optional, List
from datetime import date
from enum import IntEnum, Enum


class TipoNorma(BaseModel):
    id: int
    nombre: str

class Dependencia(BaseModel):
    id: int
    nombre: str


class BusquedaConfig(BaseModel):
    tipos_norma: List[TipoNorma] 
    dependencias: List[Dependencia]


# BuscarNormas.do
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
    total_pags: int
    total: int
    @computed_field
    @property
    def cant_resultados(self) -> int:
        return len(self.resultados)



# BuscarBoletin.do
class BusquedaBoletinRequest(BaseModel):
    diaPub: Optional[int] = None
    mesPub: Optional[int] = None
    anioPub: Optional[int] = None
    buscarPorNro: bool
    nro: Optional[int] = None


class BusquedaBoletinResponse(BaseModel):
    id : int


# VerNorma.do
class ParamsVerNorma(BaseModel):
    id : int
    resaltar: Optional[bool] = None


class VerNormaResponse(BaseModel):
    summary: NormaSummary
    fecha_emision: Optional[date] = None
    pagina_boletin: Optional[int] = None
    url_texto_completo: Optional[str] = None
    url_texto_actualizado: Optional[str] = None
    normas_que_modifica : Optional[int] = None
    normas_que_modifican_esta: Optional[int] = None


# VerVinculos.do
class ModoVinculo(IntEnum):
    MODIFICA_A = 1      # normas que esta norma modifica o complementa
    MODIFICADA_POR = 2  # normas por las que esta norma es modificada o complementada

class ParamsVerVinculos(BaseModel):
    id: int
    modo: ModoVinculo
    model_config = ConfigDict(use_enum_values=True)

class VinculoNormaSummary(BaseModel):
    id: int
    identidad_norma : str
    organismo_emisor: str
    fecha_publicacion: Optional[date] = None
    organismo_padre: str
    tema : str

class VerVinculosResponse(BaseModel):
    id : int 
    vinculos: List[VinculoNormaSummary]   # normas que la modifican/complementan

class ModoDesplazamiento(str, Enum):
    # 'AP' para avanzar, 'RP' para retroceder
    RETROCEDER = "RP"
    AVANZAR = "AP"

class PaginacionRequest(BaseModel):
    desplazamiento: ModoDesplazamiento
    irAPagina: int