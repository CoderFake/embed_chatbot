#!/bin/bash
set -e

# Display environment info
echo "========================================="
echo "File Server"
echo "Environment: ${ENV:-dev}"
echo "========================================="

echo "Configuring RabbitMQ to allow remote guest access..."
echo "loopback_users = none" > /etc/rabbitmq/rabbitmq.conf

echo "Starting RabbitMQ server..."
service rabbitmq-server start

# Wait for RabbitMQ to be ready
echo "Waiting for RabbitMQ to be ready..."
timeout 60 bash -c 'until rabbitmqctl status > /dev/null 2>&1; do sleep 1; done'

echo "RabbitMQ is ready"

echo "Configuring RabbitMQ permissions..."
rabbitmqctl set_permissions -p / guest ".*" ".*" ".*"
echo "RabbitMQ permissions configured"

# Create queue with DLQ configuration
echo "Setting up RabbitMQ queue..."
python -c "
import pika
import time
import os

# Wait a bit more to ensure management API is ready
time.sleep(2)

queue_name = os.getenv('RABBITMQ_QUEUE_NAME', 'file_processing_queue')

try:
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    
    # Declare DLQ
    channel.queue_declare(
        queue=f'{queue_name}_dlq',
        durable=True
    )
    
    # Declare main queue with DLQ binding and priority support
    channel.queue_declare(
        queue=queue_name,
        durable=True,
        arguments={
            'x-dead-letter-exchange': '',
            'x-dead-letter-routing-key': f'{queue_name}_dlq',
            'x-max-priority': 10
        }
    )
    
    connection.close()
    print(f'Queue setup completed: {queue_name}')
except Exception as e:
    print(f'Queue setup failed: {e}')
    exit(1)
"

echo "========================================="
echo "Starting File Server Worker Pool..."
echo "========================================="

case "${ENV}" in
    prod|production)
        echo "Starting in PRODUCTION mode with Gunicorn..."
        exec gunicorn main:app \
            --bind=0.0.0.0:${PORT:-8003} \
            --workers=${WORKERS:-4} \
            --worker-class=uvicorn.workers.UvicornWorker \
            --max-requests=${MAX_REQUESTS:-1000} \
            --max-requests-jitter=${MAX_REQUESTS_JITTER:-100} \
            --timeout=${TIMEOUT:-120} \
            --graceful-timeout=${GRACEFUL_TIMEOUT:-60} \
            --keep-alive=${KEEP_ALIVE:-5} \
            --log-level=${LOG_LEVEL:-info} \
            --access-logfile=- \
            --error-logfile=-
        ;;
        
    stg|staging)
        echo "Starting in STAGING mode with Gunicorn..."
        exec gunicorn main:app \
            --bind=0.0.0.0:${PORT:-8003} \
            --workers=${WORKERS:-2} \
            --worker-class=uvicorn.workers.UvicornWorker \
            --max-requests=${MAX_REQUESTS:-500} \
            --max-requests-jitter=${MAX_REQUESTS_JITTER:-50} \
            --timeout=${TIMEOUT:-120} \
            --graceful-timeout=${GRACEFUL_TIMEOUT:-30} \
            --keep-alive=${KEEP_ALIVE:-5} \
            --log-level=${LOG_LEVEL:-debug} \
            --access-logfile=- \
            --error-logfile=- \
            --reload
        ;;
        
    dev|development|*)
        echo "Starting in DEVELOPMENT mode with Uvicorn..."
        exec uvicorn main:app \
            --host=0.0.0.0 \
            --port=${PORT:-8003} \
            --reload \
            --log-level=warning \
            --use-colors
        ;;
esac
