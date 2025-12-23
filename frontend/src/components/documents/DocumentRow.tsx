"use client";

import { useState, useMemo } from "react";
import { FileText, Trash2 } from "lucide-react";
import { useLanguage } from "@/contexts/language-context";
import { useSSE } from "@/hooks/useSSE";
import type { Document } from "@/services/document";

interface DocumentRowProps {
  document: Document;
  onDelete: (doc: Document) => void;
}

type DocumentStatus = "pending" | "processing" | "completed" | "failed";

export function DocumentRow({ document, onDelete }: DocumentRowProps) {
  const { t } = useLanguage();
  const [currentProgress, setCurrentProgress] = useState(0);
  const [currentStatus, setCurrentStatus] = useState<DocumentStatus>(document.status);
  const [isTaskCompleted, setIsTaskCompleted] = useState(false);

  const taskId = useMemo(() => {
    if (isTaskCompleted) return null;
    if (currentStatus !== "processing") return null;
    return document.task_id || null;
  }, [isTaskCompleted, currentStatus, document.task_id]);

  const { progress, status } = useSSE(taskId, {
    onProgress: (progressData) => {
      setCurrentProgress(progressData.progress);
      setCurrentStatus(progressData.status as DocumentStatus);
    },
    onComplete: () => {
      setCurrentProgress(100);
      setCurrentStatus("completed");
      setIsTaskCompleted(true);
    },
    onError: () => {
      setCurrentStatus("failed");
      setIsTaskCompleted(true);
    },
    autoConnect: !!taskId,
  });

  const displayProgress = progress || currentProgress;
  const displayStatus = status || currentStatus;

  const getStatusBadge = (status: string) => {
    const badges = {
      completed: "badge-success",
      processing: "badge-info",
      pending: "badge-warning",
      failed: "badge-error",
    };
    return badges[status as keyof typeof badges] || "badge-info";
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "-";
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  const isProcessing = displayStatus === "processing";

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-gray-400" />
          <div className="flex-1">
            <div className="text-sm font-medium text-gray-900">
              {document.title}
            </div>
            {document.web_url && (
              <div className="text-xs text-gray-500 truncate max-w-xs">
                {document.web_url}
              </div>
            )}
            {isProcessing && (
              <div className="mt-2">
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-blue-600 h-full transition-all duration-300 ease-out"
                      style={{ width: `${displayProgress}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-600 font-medium min-w-[3rem] text-right">
                    {Math.round(displayProgress)}%
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
        {t(`documents.${document.source_type}`)}
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <span className={`badge ${getStatusBadge(displayStatus)}`}>
          {t(`documents.${displayStatus}`)}
        </span>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
        {document.uploaded_by || "-"}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
        {formatFileSize(document.file_size)}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
        {new Date(document.created_at).toLocaleDateString()}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
        <button
          onClick={() => onDelete(document)}
          className="text-red-600 hover:text-red-700"
          title={t("common.delete")}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </td>
    </tr>
  );
}

