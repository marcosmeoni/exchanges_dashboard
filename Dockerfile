# syntax=docker/dockerfile:1
FROM python:3.8-slim

RUN apt-get update && \
    apt-get install -y default-libmysqlclient-dev gcc pkg-config libssl-dev && \
    pip install mysqlclient
RUN apt-get update && \
     apt-get install -y gcc libc6-dev libffi-dev g++
RUN pip install --upgrade\
# Instala mysqlclient
COPY scraper_root /scraper/scraper_root
RUN pip install -r /scraper/scraper_root/requirements.txt
COPY config*.json /scraper/
WORKDIR /scraper
ENV PYTHONPATH "${PYTHONPATH}:/scraper"
CMD ["python3", "scraper_root/scraper.py"]