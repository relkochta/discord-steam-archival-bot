FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app

env UV_PYTHON_INSTALL_DIR=/opt/python
ENV UV_NO_DEV=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN uv sync --locked

ENV SERV_DIR=/clips
ENV SQLITE_DB_URL=/db/sqlite.db

ENV HOME=/tmp

CMD ["uv", "run", "main.py"]
