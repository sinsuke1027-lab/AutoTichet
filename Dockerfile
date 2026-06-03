FROM python:3.13-slim

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 1001 autoticket

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# SQLite 処理済みID用（テスト環境では再起動でリセット許容）
RUN mkdir -p data && chown autoticket data

USER autoticket

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
