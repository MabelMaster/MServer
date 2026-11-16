FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY sim ./sim
COPY server ./server
COPY web ./web

RUN pip install --no-cache-dir .

EXPOSE 4433/udp 50000/udp

CMD ["python", "-m", "server.http3", \
     "--cert", "/certs/cert.pem", \
     "--key", "/certs/key.pem", \
     "--host", "0.0.0.0", \
     "--advertise", "127.0.0.1", \
     "--ice-port", "50000"]
