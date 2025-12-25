#!/bin/bash
set -e

# Display environment info
echo "========================================="
echo "Service: Visitor Grader"
echo "Environment: ${ENV:-dev}"
echo "========================================="

case "${ENV}" in
	prod|production)
		echo "Starting in PRODUCTION mode with Gunicorn..."
		exec gunicorn main:app \
			--bind=0.0.0.0:${PORT:-8002} \
			--workers=1 \
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
			--bind=0.0.0.0:${PORT:-8002} \
			--workers=1 \
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
			--port=${PORT:-8002} \
			--reload \
			--log-level=debug \
			--use-colors
		;;
esac
