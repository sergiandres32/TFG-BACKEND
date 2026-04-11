FROM python:3.12-slim

# Instalar compiladores y herramientas necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /judge

# Copiar código del juez y dependencias
COPY src/ /judge/src/
COPY *.py /judge/
COPY requirements-api.txt /judge/

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements-api.txt

# Crear directorios para entrada/salida
RUN mkdir -p /submissions /test_cases /results

# Por defecto, ejecutar API (se puede sobrescribir con command en docker-compose)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
