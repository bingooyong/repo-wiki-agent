FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
