# InfoLeg MCP Server

Servidor basado en Python que implementa el Model Context Protocol (MCP) para proveer una interfaz de interacción directa con la base de datos de [InfoLeg](https://servicios.infoleg.gob.ar/) (Información Legislativa de la República Argentina).

Con este servidor, un agente de IA (como Claude) puede buscar normas, leer sus textos originales o actualizados, rastrear el historial de modificaciones de una ley y buscar organismos emisores, todo sin salir del contexto de la conversación.


## Capacidades y Herramientas

El servidor expone diversas herramientas estandarizadas para interactuar con InfoLeg:

### Búsqueda y Navegación
- **buscar_normas**: Búsqueda avanzada de normas jurídicas usando múltiples filtros (texto libre, número, tipo, dependencias, fechas). Soporta operadores lógicos (AND, OR, NOT, `*`).
- **ver_norma**: Obtiene los metadatos completos y sumario de una norma a partir de su ID único.

### Textos de Normas
- **obtener_texto_actualizado**: Retorna el texto VIGENTE de una norma (con modificaciones aplicadas). Se devuelve de forma paginada para optimizar el consumo de contexto.
- **obtener_texto_original**: Retorna el texto ORIGINAL de una norma tal cual fue sancionada.

### Trazabilidad y Modificaciones
- **ver_normas_que_modifica**: Rastrea el impacto de una norma indicando qué otras normas anteriores modificó, derogó o complementó.
- **ver_normas_que_la_modifican**: Muestra el historial de alteraciones que recibió una norma por parte de normas posteriores.

### Dependencias y Tipos
- **buscar_dependencias**: Búsqueda por nombre (fuzzy search) para encontrar el ID de organismos emisores (ej. AFIP, Ministerios).
- **get_dependencia_by_id**: Obtiene los datos exactos de una dependencia a partir de un ID conocido.
- **Recurso `tipos-norma`**: Catálogo de tipos de norma (Leyes, Decretos) con su ID y nombre. Ideal para consultar antes de realizar búsquedas.

## Instalación y Uso Local

Este proyecto utiliza [uv](https://github.com/astral-sh/uv) para la gestión de dependencias.

1. Instalar dependencias:
   ```bash
   uv sync
   ```

2. Ejecutar el servidor:
   ```bash
   uv run python ./src/server.py
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

El servidor estará disponible en `http://localhost:8000` y el endpoint de conexión MCP es `http://localhost:8000/sse`.

## Conectar MCP

Para usarlo como conector el servidor debe ser accesible vía HTTPS. Podes desplegar la imagen de Docker en un servicio de nube (GCP, AWS, etc) o exponerlo en un servidor local usando una herramienta como `ngrok`.

### Pasos para agregarlo en Claude

1. En Claude.ai **Configuración** > **Conectores** > **Agregar Conector Personalizado**.
2. Pega la URL HTTPS de tu servidor desplegado incluyendo el endpoint `/sse` (ej: `https://tu-dominio.com/sse`).
3. Verifica que el agente tenga acceso a las tools para interactuar con InfoLeg
