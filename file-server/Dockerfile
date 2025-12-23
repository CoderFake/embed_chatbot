FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV OMP_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV OPENBLAS_NUM_THREADS=4

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    gnupg \
    build-essential \
    rabbitmq-server \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN echo "loopback_users = none" > /etc/rabbitmq/rabbitmq.conf
RUN rabbitmq-plugins enable rabbitmq_management

COPY requirements.txt .

RUN pip install --no-cache-dir torch==2.9.0 --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY app/ ./app/
COPY main.py .
COPY start.sh .

RUN chmod +x start.sh
RUN mkdir -p /tmp/uploads /tmp/crawl logs

EXPOSE 5672 15672

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD rabbitmqctl status && pgrep -f "python.*main.py" || exit 1

CMD ["./start.sh"]
