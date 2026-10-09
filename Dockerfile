FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/app
RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml requirements.txt ./
COPY app ./app
RUN pip install --upgrade pip && pip install -e ".[dev]"
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY tests ./tests
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
