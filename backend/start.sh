#!/bin/bash
set -e

# Display environment info
echo "========================================="
echo "Environment: ${ENV:-dev}"
echo "========================================="

# Ensure upload directory exists with correct permissions
echo "Setting up upload directory..."
mkdir -p /tmp/uploads 2>/dev/null || true
chmod 777 /tmp/uploads 2>/dev/null || true

# Initialize database and create root user
echo "Initializing database..."
python -m app.init_db

# Start email worker in background
echo "Starting email worker..."
python -m app.workers.email_worker &
EMAIL_WORKER_PID=$!
echo "Email worker started with PID: $EMAIL_WORKER_PID"

echo "========================================="
echo "Starting application..."
echo "========================================="

case "${ENV}" in
	prod|production)
		echo "Starting in PRODUCTION mode with Gunicorn..."
		exec gunicorn main:app \
			--bind=0.0.0.0:${PORT:-8000} \
			--workers=${WORKERS:-4} \
			--worker-class=uvicorn.workers.UvicornWorker \
			--max-requests=${MAX_REQUESTS:-1000} \
			--max-requests-jitter=${MAX_REQUESTS_JITTER:-100} \
			--timeout=${TIMEOUT:-300} \
			--graceful-timeout=${GRACEFUL_TIMEOUT:-60} \
			--keep-alive=${KEEP_ALIVE:-75} \
			--log-level=${LOG_LEVEL:-info} \
			--access-logfile=- \
			--error-logfile=- \
			--access-logformat='%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
		;;
		
	stg|staging)
		echo "Starting in STAGING mode with Gunicorn..."
		exec gunicorn main:app \
			--bind=0.0.0.0:${PORT:-8000} \
			--workers=${WORKERS:-2} \
			--worker-class=uvicorn.workers.UvicornWorker \
			--max-requests=${MAX_REQUESTS:-500} \
			--max-requests-jitter=${MAX_REQUESTS_JITTER:-50} \
			--timeout=${TIMEOUT:-300} \
			--graceful-timeout=${GRACEFUL_TIMEOUT:-30} \
			--keep-alive=${KEEP_ALIVE:-75} \
			--log-level=${LOG_LEVEL:-debug} \
			--access-logfile=- \
			--error-logfile=- \
			--reload
		;;
		
	dev|development|*)
		echo "Starting in DEVELOPMENT mode with Uvicorn..."
		exec uvicorn main:app \
			--host=0.0.0.0 \
			--port=${PORT:-8000} \
			--reload \
			--log-level=debug \
			--use-colors
		;;
esac 