FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Usuário sem privilégios, dono só da pasta de dados (onde o pipeline grava)
RUN useradd --create-home --uid 1000 app && chown -R app:app /app/data
USER app

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')"

# Roda o pipeline sobre o que houver em data/raw/ e sobe o painel. Sem nenhuma fonte,
# o painel gera a base fictícia sozinho no primeiro acesso.
CMD ["sh", "-c", "python src/extract.py && python src/transform.py || echo 'Sem dados em data/raw/: o painel vai gerar a base fictícia.'; exec streamlit run dashboard/app.py --server.address=0.0.0.0 --server.headless=true"]
