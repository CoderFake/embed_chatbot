"use client";

import { useSSE, SSEProgressData } from '@/hooks/useSSE';
import { CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';

interface ProgressTrackerProps {
  taskId: string | null;
  title?: string;
  onComplete?: (data: SSEProgressData) => void;
  onError?: (error: string) => void;
  autoConnect?: boolean;
  showDetails?: boolean;
}

export function ProgressTracker({
  taskId,
  title = 'Processing',
  onComplete,
  onError,
  autoConnect = true,
  showDetails = true
}: ProgressTrackerProps) {
  const {
    isConnected,
    progress,
    status,
    message,
    error,
  } = useSSE(taskId, {
    onProgress: (data) => {
      console.log('Progress update:', data);
    },
    onComplete: (data) => {
      console.log('Task completed:', data);
      if (onComplete) {
        onComplete(data);
      }
    },
    onError: (err) => {
      console.error('Task error:', err);
      if (onError) {
        onError(err);
      }
    },
    autoConnect
  });

  if (!taskId) {
    return null;
  }

  const getStatusIcon = () => {
    if (error || status === 'failed' || status === 'error') {
      return <XCircle className="w-5 h-5 text-red-500" />;
    }
    if (status === 'completed' || status === 'success' || progress >= 100) {
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    if (status === 'processing' || status === 'PENDING') {
      return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
    }
    return <AlertCircle className="w-5 h-5 text-gray-400" />;
  };

  const getStatusColor = () => {
    if (error || status === 'failed' || status === 'error') {
      return 'bg-red-500';
    }
    if (status === 'completed' || status === 'success' || progress >= 100) {
      return 'bg-green-500';
    }
    return 'bg-blue-500';
  };

  const getStatusText = () => {
    if (error) return 'Failed';
    if (status === 'completed' || status === 'success' || progress >= 100) return 'Completed';
    if (status === 'processing') return 'Processing';
    if (status === 'PENDING') return 'Pending';
    return status || 'Initializing';
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {getStatusIcon()}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-gray-900">{title}</h4>
            <span className="text-xs font-medium text-gray-500">
              {Math.round(progress)}%
            </span>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${getStatusColor()}`}
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>

          {/* Status and Message */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-700">
                Status:
              </span>
              <span className={`text-xs font-medium ${
                error ? 'text-red-600' : 
                (status === 'completed' || progress >= 100) ? 'text-green-600' : 
                'text-blue-600'
              }`}>
                {getStatusText()}
              </span>
              {!isConnected && status !== 'completed' && !error && (
                <span className="text-xs text-orange-500">(Reconnecting...)</span>
              )}
            </div>

            {showDetails && message && (
              <p className="text-xs text-gray-600">
                {message}
              </p>
            )}

            {error && (
              <div className="flex items-start gap-1 mt-2 p-2 bg-red-50 rounded border border-red-200">
                <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-red-700">{error}</p>
              </div>
            )}
          </div>

          {showDetails && taskId && (
            <p className="text-xs text-gray-400 mt-2">
              Task ID: {taskId}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

