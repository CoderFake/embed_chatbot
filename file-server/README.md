# File Server

Independent file processing service for handling file uploads and crawl data without blocking the main backend.

## Architecture

The file-server is a standalone Docker container that:
- Runs its own internal RabbitMQ server
- Processes file uploads and crawl data asynchronously
- Publishes real-time progress updates via Redis PubSub
- Sends completion webhooks back to the backend
- Handles embedding generation and storage in Milvus

## Configuration

**IMPORTANT**: File-server shares the same `.env` file with the backend service at the project root. All configuration is managed through Docker Compose environment variables.

### Environment Variables

All variables are defined in the root `.env` file and passed to the file-server container via `docker-compose.yml`.

#### RabbitMQ (Internal)
```bash
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_QUEUE_NAME=file_processing_queue
RABBITMQ_PREFETCH_COUNT=1
```

#### Shared Services (Redis, Milvus, MinIO)
These are shared with the backend and use the same configuration:
```bash
REDIS_HOST=redis
REDIS_PORT=6379
MILVUS_HOST=milvus
MILVUS_PORT=19530
MINIO_ENDPOINT=minio:9000
```

#### File-Server Specific
```bash
# Webhook
BACKEND_WEBHOOK_URL=http://backend:8000/api/v1/webhooks/file-processing
BACKEND_WEBHOOK_SECRET=change-this-webhook-secret

# Workers (prefixed with FILE_SERVER_ to avoid conflicts)
FILE_SERVER_WORKER_POOL_SIZE=4
FILE_SERVER_WORKER_MAX_RETRIES=3
FILE_SERVER_WORKER_RETRY_DELAY=5

# Batch Processing
FILE_SERVER_MINIO_BATCH_SIZE=100
FILE_SERVER_MILVUS_BATCH_SIZE=1000

# Progress
FILE_SERVER_PROGRESS_MIN_DELTA=5.0
FILE_SERVER_PROGRESS_MIN_INTERVAL=3.0
FILE_SERVER_PROGRESS_STATE_TTL=3600

# Logging
FILE_SERVER_LOG_LEVEL=INFO
```

#### Shared ML Config
```bash
# These are shared with backend for consistency
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
EMBEDDING_BATCH_SIZE=32
CHUNK_SIZE=512
CHUNK_OVERLAP=128
```

### Environment Types

Supports the same environment modes as backend:
- `ENV=dev` - Development mode
- `ENV=stg` - Staging mode  
- `ENV=prod` - Production mode

## Task Format

### File Upload Task
```json
{
  "task_id": "uuid",
  "task_type": "file_upload",
  "bot_id": "bot_123",
  "data": {
    "files": [
      {
        "path": "/tmp/uploads/file1.pdf",
        "document_id": "doc_123",
        "metadata": {"source": "upload"}
      }
    ]
  }
}
```

### Crawl Task
```json
{
  "task_id": "uuid",
  "task_type": "crawl",
  "bot_id": "bot_123",
  "data": {
    "crawl_files": [
      {
        "path": "/tmp/crawl/crawl_123.json",
        "crawl_id": "crawl_123"
      }
    ]
  }
}
```

## Progress Updates

Published to Redis channel `progress:{task_id}`:

```json
{
  "task_id": "uuid",
  "bot_id": "bot_123",
  "progress": 45.5,
  "status": "processing",
  "message": "Processed 45/100 files",
  "timestamp": "2024-01-01T00:00:00Z",
  "metadata": {
    "task_type": "file_upload",
    "total_items": 100
  }
}
```

## Webhook Notification

Sent to backend on completion:

```json
{
  "task_id": "uuid",
  "bot_id": "bot_123",
  "success": true,
  "task_type": "file_upload",
  "timestamp": "2024-01-01T00:00:00Z",
  "metadata": {
    "total_files": 10,
    "successful_files": 10,
    "failed_files": 0,
    "total_chunks": 523
  }
}
```

Headers:
- `X-Webhook-Signature`: HMAC-SHA256 signature
- `X-Task-ID`: Task ID

## Development

### Local Development
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
vim .env

# Build and run
docker-compose up file-server
```

### Testing
```bash
# Send test task to RabbitMQ
docker exec -it embed_chatbot_file_server python -c "
import pika
import json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

task = {
    'task_id': 'test_123',
    'task_type': 'file_upload',
    'bot_id': 'bot_123',
    'data': {
        'files': [{
            'path': '/tmp/uploads/test.pdf',
            'document_id': 'doc_123'
        }]
    }
}

channel.basic_publish(
    exchange='',
    routing_key='file_processing_queue',
    body=json.dumps(task)
)

print('Task published')
connection.close()
"
```

### Monitor Progress
```bash
# Subscribe to Redis progress channel
docker exec -it embed_chatbot_redis redis-cli
> SUBSCRIBE progress:test_123
```

### Check Logs
```bash
# View logs
docker logs -f embed_chatbot_file_server

# View structured logs
docker exec -it embed_chatbot_file_server tail -f logs/file_server.log
```

## Diagnostic Tools

### RabbitMQ Diagnostics
```bash
# Run RabbitMQ diagnostics script
docker exec -it embed_chatbot_file_server python /app/scripts/rabbitmq_diagnostics.py
```

This script will check:
- RabbitMQ server status
- Queue status
- Listener status
- Network connectivity

### Manual RabbitMQ Checks
```bash
# Check RabbitMQ status
docker exec -it embed_chatbot_file_server rabbitmqctl status

# List queues
docker exec -it embed_chatbot_file_server rabbitmqctl list_queues

# Check listeners
docker exec -it embed_chatbot_file_server rabbitmqctl listeners
```

## Production Considerations

1. **Worker Pool Size**: Adjust based on CPU cores and workload
2. **Memory**: Monitor memory usage for embedding model (BGE M3 ~2GB)
3. **RabbitMQ**: Configure message TTL and DLQ policy
4. **Redis**: Ensure sufficient memory for progress state
5. **Volumes**: Use persistent volumes for logs and temporary files
6. **Monitoring**: Integrate with Sentry or Prometheus
7. **Scaling**: Can run multiple file-server instances with shared RabbitMQ

## Troubleshooting

### RabbitMQ Not Starting
- Check logs: `docker exec embed_chatbot_file_server rabbitmqctl status`
- Increase startup timeout in healthcheck

### Workers Not Processing
- Verify RabbitMQ connection: Check `RABBITMQ_URL`
- Check queue: `docker exec embed_chatbot_file_server rabbitmqctl list_queues`
- Verify worker pool size: `WORKER_POOL_SIZE`

### Progress Not Updating
- Check Redis connection: `REDIS_HOST` and `REDIS_PORT`
- Verify progress throttle settings
- Monitor Redis channel: `SUBSCRIBE progress:*`

### Webhook Failures
- Verify `BACKEND_WEBHOOK_URL` is accessible
- Check HMAC secret matches backend
- Review backend logs for webhook endpoint

## License

MIT