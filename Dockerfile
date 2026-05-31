FROM python:3.12-slim

WORKDIR /app

COPY deploy/requirements-server.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ shared/
COPY server/ server/

ENV TRAXUS_HOST=0.0.0.0
ENV TRAXUS_PORT=8765
ENV TRAXUS_DB=/data/traxus.db

EXPOSE 8765

CMD ["python", "-m", "server.main"]
