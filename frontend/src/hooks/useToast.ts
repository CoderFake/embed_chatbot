/**
 * Hook for managing toast notifications
 */
import { useState, useCallback } from "react";
import { ToastType } from "@/components/ui/Toast";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((type: ToastType, message: string) => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, type, message }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const success = useCallback((message: string) => showToast("success", message), [showToast]);
  const error = useCallback((message: string) => showToast("error", message), [showToast]);
  const warning = useCallback((message: string) => showToast("warning", message), [showToast]);
  const info = useCallback((message: string) => showToast("info", message), [showToast]);

  return {
    toasts,
    success,
    error,
    warning,
    info,
    removeToast,
  };
}

