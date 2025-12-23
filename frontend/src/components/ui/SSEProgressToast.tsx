"use client";

import { useSSE } from "@/hooks/useSSE";
import { ProgressToast, ProgressToastType } from "./ProgressToast";
import { useLanguage } from "@/contexts/language-context";

interface SSEProgressToastProps {
  taskId: string;
  title: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
  onClose: () => void;
}

export function SSEProgressToast({
  taskId,
  title,
  onComplete,
  onError,
  onClose,
}: SSEProgressToastProps) {
  const { t } = useLanguage();

  const { progress, status, message, error } = useSSE(taskId, {
    onComplete: (data) => {
      console.log("SSE task completed:", data);
      if (onComplete) {
        onComplete();
      }
      setTimeout(() => {
        onClose();
      }, 3000);
    },
    onError: (err) => {
      console.error("SSE task error:", err);
      if (onError) {
        onError(err);
      }
    },
    autoConnect: true,
  });

  const getToastType = (): ProgressToastType => {
    if (error || status === "failed" || status === "error") {
      return "error";
    }
    if (status === "completed" || status === "success" || progress >= 100) {
      return "success";
    }
    return "loading";
  };

  const getDisplayMessage = (): string => {
    if (error) {
      return error;
    }
    if (message) {
      return message;
    }
    if (status === "completed" || status === "success") {
      return t("progress.completed");
    }
    if (status === "failed" || status === "error") {
      return t("progress.failed");
    }
    return t("progress.processing");
  };

  return (
    <ProgressToast
      type={getToastType()}
      title={title}
      message={getDisplayMessage()}
      progress={progress}
      onClose={onClose}
      duration={0}
    />
  );
}

