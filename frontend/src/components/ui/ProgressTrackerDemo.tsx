"use client";

import { useState } from 'react';
import { ProgressTracker } from './ProgressTracker';

/**
 * Demo component to test ProgressTracker with a task ID
 * Usage: Add this to any page to test SSE progress tracking
 */
export function ProgressTrackerDemo() {
  const [taskId, setTaskId] = useState<string>('');
  const [inputTaskId, setInputTaskId] = useState<string>('');
  const [isTracking, setIsTracking] = useState(false);

  const handleStartTracking = () => {
    if (inputTaskId.trim()) {
      setTaskId(inputTaskId.trim());
      setIsTracking(true);
    }
  };

  const handleStopTracking = () => {
    setTaskId('');
    setIsTracking(false);
  };

  return (
    <div className="card space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">
        Progress Tracker Demo
      </h3>
      
      <div className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Task ID
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={inputTaskId}
              onChange={(e) => setInputTaskId(e.target.value)}
              placeholder="Enter task ID to track"
              className="input-field flex-1"
              disabled={isTracking}
            />
            {!isTracking ? (
              <button
                onClick={handleStartTracking}
                className="btn-primary"
                disabled={!inputTaskId.trim()}
              >
                Start Tracking
              </button>
            ) : (
              <button
                onClick={handleStopTracking}
                className="btn-secondary"
              >
                Stop
              </button>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Enter a task ID from bot creation or document upload to track its progress
          </p>
        </div>

        {isTracking && taskId && (
          <ProgressTracker
            taskId={taskId}
            title="Task Progress"
            onComplete={(data) => {
              console.log('Task completed:', data);
              setTimeout(() => {
                setIsTracking(false);
                setTaskId('');
              }, 3000);
            }}
            onError={(error) => {
              console.error('Task error:', error);
            }}
            showDetails={true}
          />
        )}
      </div>
    </div>
  );
}

