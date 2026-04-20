# Usar una imagen base de Python ligera
FROM python:3.13-slim

# Instalar uv desde la imagen oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY pyproject.toml uv.lock ./

# Instalar dependencias sin instalar el proyecto (mejor para la caché)
RUN uv sync --frozen --no-cache --no-install-project

# Copiar el resto de la aplicación
COPY . .

# Sincronizar el proyecto
RUN uv sync --frozen --no-cache

# Exponer el puerto por defecto de FastMCP (8000)
EXPOSE 8000

# Comando para ejecutar el servidor
CMD ["uv", "run", "python", "server.py"]
