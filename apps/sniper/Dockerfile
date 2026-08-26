# Sniper hot-path worker
FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY apps/sniper/pyproject.toml ./
COPY apps/sniper/sniper ./sniper
RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "sniper.main"]
