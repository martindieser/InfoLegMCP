# InfoLeg MCP Server

Servidor basado en Python que utiliza el Model Context Protocol (MCP) para proveer una inteface para interactuar con [InfoLeg](https://servicios.infoleg.gob.ar/).


## Capacidades del Agente

Este servidor MCP expone diversas herramientas y recursos para interactuar con la base de datos de InfoLeg:

### Recursos 
| Nombre | Propósito |
| :--- | :--- |
| `tipos-norma` | Devuelve el catálogo de tipos de norma (ej. Leyes, Decretos) con su ID y nombre. Ideal para consultar antes de realizar búsquedas. |

### Herramientas 
| Nombre | Propósito |
| :--- | :--- |
| `buscar_normas` | Búsqueda avanzada de normas jurídicas usando múltiples filtros (texto libre, número, tipo, dependencias, fechas). Soporta paginación. |
| `ver_norma` | Obtiene los metadatos completos y sumario de una norma a partir de su ID único de InfoLeg. |
| `obtener_texto_actualizado` | Retorna el texto VIGENTE de una norma (con modificaciones aplicadas) de forma paginada para no saturar el contexto. |
| `obtener_texto_original` | Retorna el texto ORIGINAL de una norma tal cual fue sancionada, de forma paginada. |
| `ver_normas_que_modifica` | Rastrea el impacto de una norma indicando qué otras normas anteriores modificó, derogó o complementó. |
| `ver_normas_que_la_modifican` | Muestra el historial de modificaciones y alteraciones que recibió una norma por parte de normas posteriores. |
| `buscar_dependencias` | Búsqueda por nombre (fuzzy search tolerante a errores) para encontrar el ID de organismos emisores (ej. AFIP, Ministerios). |
| `get_dependencia_by_id` | Obtiene los datos exactos de una dependencia a partir de un ID conocido. |

## Instalación y Uso Local

Este proyecto utiliza [uv](https://github.com/astral-sh/uv) para la gestión de dependencias.

1. Instalar dependencias:
   ```bash
   uv sync
   ```

2. Ejecutar el servidor:
   ```bash
   uv run python server.py
   ```

## Docker

Para ejecutar el servidor en un contenedor:

1. Construir la imagen:
   ```bash
   docker build -t infoleg-mcp .
   ```

2. Ejecutar el contenedor:
   ```bash
   docker run -p 8000:8000 infoleg-mcp
   ```

El servidor estará disponible en `http://localhost:8000`.

## Conectar MCP

Para usarlo como conector el servidor debe ser accesible vía HTTPS. Podes desplegar la imagen de Docker en un servicio de nube (GCP, AWS, etc) o exponerlo en un servidor local usando una herramienta como `ngrok`.

### Pasos para agregarlo en Claude

1. En Claude.ai **Configuración** > **Conectores** > **Agregar Conector Personalizado**.
2. Pega la URL HTTPS de tu servidor desplegado.
3. Verifica que el agente tenga acceso a las tools para interactuar con InfoLeg

