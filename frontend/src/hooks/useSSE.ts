import { useEffect, useRef, useState, useCallback } from 'react';
import globalConfig from '@/configs';
import { getAccessToken } from '@/lib/auth';

export interface SSEProgressData {
  task_id: string;
  bot_id?: string;
  progress: number;
  status: string;
  message: string;
  timestamp?: string;
  error?: string;
}

interface UseSSEOptions {
  onProgress?: (data: SSEProgressData) => void;
  onComplete?: (data: SSEProgressData) => void;
  onError?: (error: string) => void;
  autoConnect?: boolean;
}

export function useSSE(taskId: string | null, options: UseSSEOptions = {}) {
  const {
    onProgress,
    onComplete,
    onError,
    autoConnect = true
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const onProgressRef = useRef(onProgress);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onProgressRef.current = onProgress;
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
  }, [onProgress, onComplete, onError]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!taskId) {
      console.warn('Cannot connect SSE: taskId is null');
      return;
    }

    disconnect();

    try {
      const token = getAccessToken();
      if (!token) {
        console.error('Cannot connect SSE: No access token');
        setError('Authentication required');
        return;
      }

      const url = `${globalConfig.apiUrl}/tasks/${taskId}/progress?token=${encodeURIComponent(token)}`;
      console.log('Connecting to SSE:', url);

      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('SSE connection opened');
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      eventSource.addEventListener('connected', (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('SSE connected:', data);
        } catch (err) {
          console.error('Error parsing connected event:', err);
        }
      });

      eventSource.addEventListener('restore', (event) => {
        try {
          const data: SSEProgressData = JSON.parse(event.data);
          console.log('SSE restore state:', data);

          setProgress(data.progress);
          setStatus(data.status);
          setMessage(data.message);

          onProgressRef.current?.(data);
        } catch (err) {
          console.error('Error parsing restore event:', err);
        }
      });

      eventSource.addEventListener('progress', (event) => {
        try {
          const data: SSEProgressData = JSON.parse(event.data);
          console.log('SSE progress:', data);

          setProgress(data.progress);
          setStatus(data.status);
          setMessage(data.message);

          onProgressRef.current?.(data);
        } catch (err) {
          console.error('Error parsing progress event:', err);
        }
      });

      eventSource.addEventListener('done', (event) => {
        try {
          const data: SSEProgressData = JSON.parse(event.data);
          console.log('SSE done:', data);

          setProgress(data.progress);
          setStatus(data.status);
          setMessage(data.message);

          if (data.status === 'completed' || data.status === 'success' || data.progress >= 100) {
            onCompleteRef.current?.(data);
          } else if (data.status === 'failed' || data.status === 'error') {
            const errorMsg = data.error || data.message || 'Task failed';
            setError(errorMsg);
            onErrorRef.current?.(errorMsg);
          }

          setTimeout(() => disconnect(), 1000);
        } catch (err) {
          console.error('Error parsing done event:', err);
        }
      });

      eventSource.onerror = (err) => {
        console.error('SSE error:', err);
        setIsConnected(false);

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else {
          const errorMsg = 'Failed to connect to progress stream after multiple attempts';
          setError(errorMsg);
          onErrorRef.current?.(errorMsg);
          disconnect();
        }
      };
    } catch (err) {
      console.error('Error creating EventSource:', err);
      const errorMsg = 'Failed to create SSE connection';
      setError(errorMsg);
      onErrorRef.current?.(errorMsg);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  useEffect(() => {
    if (autoConnect && taskId) {
      connect();
    }

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, autoConnect]);

  return {
    isConnected,
    progress,
    status,
    message,
    error,
    connect,
    disconnect
  };
}

