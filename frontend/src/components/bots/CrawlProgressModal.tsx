/**
 * SSE Progress Modal for bot crawling
 */
"use client";

import { useLanguage } from "@/contexts/language-context";
import { useSSE } from "@/hooks/useSSE";
import { Modal } from "@/components/ui/Modal";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { CheckCircle, XCircle, AlertCircle } from "lucide-react";

interface CrawlProgressModalProps {
  taskId: string;
  onComplete: () => void;
  onClose: () => void;
}

export function CrawlProgressModal({
  taskId,
  onComplete,
  onClose,
}: CrawlProgressModalProps) {
  const { t } = useLanguage();

  const {
    isConnected,
    progress,
    status,
    message,
    error,
  } = useSSE(taskId, {
    onComplete: (data) => {
      console.log("Crawl completed:", data);
      setTimeout(() => {
        onComplete();
      }, 2000);
    },
    onError: (err) => {
      console.error("Crawl error:", err);
    },
    autoConnect: true
  });

  const isCompleted = status === "completed" || status === "success" || progress >= 100;
  const isFailed = status === "failed" || status === "error" || !!error;

  return (
    <Modal
      isOpen={true}
      onClose={isCompleted || isFailed ? onClose : () => {}}
      title={t("bots.crawlProgress")}
      size="md"
    >
      <div className="space-y-6">
        {/* Connection Status */}
        {!isConnected && !isCompleted && !isFailed && (
          <div className="flex items-center gap-2 text-sm text-orange-600 bg-orange-50 p-3 rounded-lg">
            <AlertCircle className="w-4 h-4" />
            <span>Connecting to progress stream...</span>
          </div>
        )}

        {/* Progress Bar */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-700">{message || "Initializing..."}</span>
            <span className="font-semibold text-gray-900">{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all duration-300 ${
                isFailed
                  ? "bg-red-600"
                  : isCompleted
                  ? "bg-green-600"
                  : "bg-[var(--color-primary)]"
              }`}
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        </div>

        {/* Status Icon */}
        <div className="flex items-center justify-center">
          {isFailed ? (
            <div className="text-center">
              <XCircle className="w-16 h-16 text-red-600 mx-auto mb-2" />
              <p className="text-red-600 font-medium">Crawl Failed</p>
              {error && (
                <p className="text-sm text-red-500 mt-2">{error}</p>
              )}
            </div>
          ) : isCompleted ? (
            <div className="text-center">
              <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-2" />
              <p className="text-green-600 font-medium">Crawl Completed!</p>
            </div>
          ) : (
            <div className="text-center">
              <LoadingSpinner size="lg" />
              <p className="text-sm text-gray-600 mt-4">
                {status === "PENDING" ? "Waiting to start..." : "Processing..."}
              </p>
            </div>
          )}
        </div>

        {/* Action Button */}
        {(isCompleted || isFailed) && (
          <div className="flex justify-end">
            <button onClick={onClose} className="btn-primary">
              {t("common.close")}
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}

