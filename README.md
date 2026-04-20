# InfoLeg MCP Server

Servidor basado en Python que utiliza el Model Context Protocol (MCP) para proveer una inteface para interactuar con [InfoLeg](https://servicios.infoleg.gob.ar/).

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