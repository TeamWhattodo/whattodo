FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
COPY uv.lock* .

RUN uv sync --no-dev

COPY . .

EXPOSE 8501 8000

CMD ["sh", "-c", "uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 & uv run streamlit run app.py --server.port 8501 --server.address 0.0.0.0"]
