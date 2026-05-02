FROM python:3.13-slim

WORKDIR /app

# 非rootユーザー作成（セキュリティ）
RUN adduser --disabled-password --gecos "" --uid 1001 autoticket

# 依存パッケージインストール（コードより先にコピーしてキャッシュ活用）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY src/ src/

# SQLite データ保存先を作成してオーナー変更
RUN mkdir -p data && chown autoticket data

USER autoticket

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
