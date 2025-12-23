import { useState, useCallback } from "react";
import { ProgressToastType } from "@/components/ui/ProgressToast";

interface ProgressToast {
  id: string;
  type: ProgressToastType;
  title: string;
  message?: string;
  progress?: number;
  taskId?: string;
  onComplete?: () => void;
}

export function useProgressToast() {
  const [toasts, setToasts] = useState<ProgressToast[]>([]);

  const addToast = useCallback(
    (
      type: ProgressToastType,
      title: string,
      message?: string,
      progress?: number
    ): string => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
      setToasts((prev) => [...prev, { id, type, title, message, progress }]);
      return id;
    },
    []
  );

  const addSSEToast = useCallback(
    (taskId: string, title: string, onComplete?: () => void): string => {
      const id = `sse-toast-${taskId}`;
      setToasts((prev) => {
        const existing = prev.find((t) => t.id === id);
        if (existing) {
          return prev;
        }
        return [...prev, { id, type: "loading", title, taskId, progress: 0, onComplete }];
      });
      return id;
    },
    []
  );

  const updateToast = useCallback(
    (
      id: string,
      updates: {
        type?: ProgressToastType;
        title?: string;
        message?: string;
        progress?: number;
      }
    ) => {
      setToasts((prev) =>
        prev.map((toast) =>
          toast.id === id ? { ...toast, ...updates } : toast
        )
      );
    },
    []
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setToasts([]);
  }, []);

  return {
    toasts,
    addToast,
    addSSEToast,
    updateToast,
    removeToast,
    clearAll,
  };
}

