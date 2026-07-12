FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Expor porta do Streamlit
EXPOSE 8501

# Comando padrão: roda o pipeline (extract -> transform) e sobe o dashboard.
# Se o XLSX não estiver em data/raw/, o pipeline é pulado e o painel exibe instruções.
CMD ["sh", "-c", "python src/extract.py && python src/transform.py || echo '⚠️  Pipeline não executado (XLSX ausente em data/raw/?) — o painel exibirá as instruções.'; exec streamlit run dashboard/app.py --server.address=0.0.0.0"]