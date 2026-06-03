FROM python:3.13-slim

# HuggingFace Spaces はコンテナを uid 1000 で実行するため uid 1000 で作成
RUN useradd -m -u 1000 autoticket

ENV HOME=/home/autoticket \
    PATH=/home/autoticket/.local/bin:$PATH

WORKDIR $HOME/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=autoticket src/ src/
COPY --chown=autoticket alembic/ alembic/
COPY --chown=autoticket alembic.ini .
COPY --chown=autoticket entrypoint.sh .

# SQLite 処理済みID用（テスト環境では再起動でリセット許容）
RUN mkdir -p data && chown autoticket data

RUN chmod +x entrypoint.sh

USER autoticket

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["./entrypoint.sh"]
