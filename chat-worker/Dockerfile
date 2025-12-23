FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install --no-install-recommends -y build-essential gcc g++ python3-dev curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir torch==2.9.0 --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get purge -y build-essential gcc g++ python3-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY main.py .
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
