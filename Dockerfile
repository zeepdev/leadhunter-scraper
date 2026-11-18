FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# Instala dependências básicas do sistema (incluindo libatomic1 exigido pelo driver do Playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala o navegador Chromium e todas as dependências de sistema
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8501

# Inicia o Streamlit escutando na porta definida pelo Render ($PORT) ou 8501 como fallback
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
