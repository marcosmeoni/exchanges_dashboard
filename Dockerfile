# syntax=docker/dockerfile:1
FROM python:3.8.7-alpine
RUN apk add --no-cache gcc musl-dev linux-headers libffi-dev g++
# Instala paquetes necesarios
# Agrega el repositorio edge y actualiza
RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories && \
    apk update --allow-untrusted \
    apk update

# Instala paquetes necesarios
RUN apk add --no-cache mariadb-connector-c-dev mariadb-dev build-base pkg-config && \
    export MYSQLCLIENT_CFLAGS="-I/usr/include/mysql" && \
    export MYSQLCLIENT_LDFLAGS="-L/usr/lib/mysql -lmariadb" && \
    pip install mysqlclient
RUN pip install --upgrade pip
# Instala mysqlclient
COPY scraper_root /scraper/scraper_root
RUN pip install -r /scraper/scraper_root/requirements.txt
COPY config*.json /scraper/
WORKDIR /scraper
ENV PYTHONPATH "${PYTHONPATH}:/scraper"
CMD ["python3", "scraper_root/scraper.py"]