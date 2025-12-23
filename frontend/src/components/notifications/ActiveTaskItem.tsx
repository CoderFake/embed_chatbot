"use client";

import { useSSE } from "@/hooks/useSSE";
import { useLanguage } from "@/contexts/language-context";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useState, useMemo } from "react";

interface ActiveTaskItemProps {
  taskId: string;
  title: string;
  initialProgress?: number;
  initialStatus?: string;
  onComplete?: () => void;
}

export function ActiveTaskItem({
  taskId: initialTaskId,
  title,
  initialProgress = 0,
  initialStatus = "processing",
  onComplete,
}: ActiveTaskItemProps) {
  const { t } = useLanguage();
  const [currentProgress, setCurrentProgress] = useState(initialProgress);
  const [currentStatus, setCurrentStatus] = useState(initialStatus);
  const [isTaskCompleted, setIsTaskCompleted] = useState(false);

  const taskId = useMemo(() => {
    if (isTaskCompleted) return null;
    if (currentStatus === "completed" || currentStatus === "failed") return null;
    return initialTaskId;
  }, [isTaskCompleted, currentStatus, initialTaskId]);

  const { progress, status } = useSSE(taskId, {
    onProgress: (progressData) => {
      setCurrentProgress(progressData.progress);
      setCurrentStatus(progressData.status);
    },
    onComplete: () => {
      setCurrentProgress(100);
      setCurrentStatus("completed");
      setIsTaskCompleted(true);
      if (onComplete) {
        onComplete();
      }
    },
    onError: () => {
      setCurrentStatus("failed");
      setIsTaskCompleted(true);
    },
    autoConnect: !!taskId,
  });

  const displayProgress = progress || currentProgress;
  const displayStatus = status || currentStatus;

  const getStatusIcon = () => {
    if (displayStatus === "completed" || displayStatus === "success") {
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    }
    if (displayStatus === "failed" || displayStatus === "error") {
      return <XCircle className="w-4 h-4 text-red-500" />;
    }
    return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
  };

  const getStatusText = () => {
    if (displayStatus === "completed" || displayStatus === "success") {
      return t("progress.completed");
    }
    if (displayStatus === "failed" || displayStatus === "error") {
      return t("progress.failed");
    }
    return t("progress.processing");
  };

  const isProcessing = displayStatus === "processing" || displayStatus === "pending";

  return (
    <div className="px-4 py-3 hover:bg-gray-50 border-b border-gray-100">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">{getStatusIcon()}</div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{title}</p>
          <p className="text-xs text-gray-500 mt-0.5">{getStatusText()}</p>
          {isProcessing && (
            <div className="mt-2">
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-blue-600 h-full transition-all duration-300 ease-out"
                    style={{ width: `${displayProgress}%` }}
                  />
                </div>
                <span className="text-xs text-gray-600 font-medium min-w-[2.5rem] text-right">
                  {Math.round(displayProgress)}%
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

