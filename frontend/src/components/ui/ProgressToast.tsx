"use client";

import { CheckCircle, XCircle, AlertCircle, Info, X, Loader2 } from "lucide-react";
import { useEffect } from "react";
import { useLanguage } from "@/contexts/language-context";

export type ProgressToastType = "success" | "error" | "warning" | "info" | "loading";

interface ProgressToastProps {
  type: ProgressToastType;
  title: string;
  message?: string;
  progress?: number;
  onClose: () => void;
  duration?: number;
}

export function ProgressToast({
  type,
  title,
  message,
  progress = 0,
  onClose,
  duration = 0,
}: ProgressToastProps) {
  const { t } = useLanguage();
  useEffect(() => {
    if (duration > 0 && type !== "loading") {
      const timer = setTimeout(onClose, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose, type]);

  const icons = {
    success: <CheckCircle className="w-5 h-5" />,
    error: <XCircle className="w-5 h-5" />,
    warning: <AlertCircle className="w-5 h-5" />,
    info: <Info className="w-5 h-5" />,
    loading: <Loader2 className="w-5 h-5 animate-spin" />,
  };

  const colors = {
    success: "bg-green-50 text-green-800 border-green-200",
    error: "bg-red-50 text-red-800 border-red-200",
    warning: "bg-yellow-50 text-yellow-800 border-yellow-200",
    info: "bg-blue-50 text-blue-800 border-blue-200",
    loading: "bg-blue-50 text-blue-800 border-blue-200",
  };

  const progressColors = {
    success: "bg-green-500",
    error: "bg-red-500",
    warning: "bg-yellow-500",
    info: "bg-blue-500",
    loading: "bg-blue-500",
  };

  return (
    <div
      className={`flex flex-col gap-2 p-4 rounded-lg border ${colors[type]} shadow-lg min-w-[320px] max-w-md animate-slide-in`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">{icons[type]}</div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">{title}</p>
          {message && <p className="text-xs mt-1 opacity-90">{message}</p>}
        </div>
        {type !== "loading" && (
          <button
            onClick={onClose}
            className="flex-shrink-0 text-current opacity-70 hover:opacity-100 transition-opacity"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {(type === "loading" || (progress !== undefined && progress > 0)) && (
        <div className="w-full">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="opacity-75">
              {type === "loading" ? t("progress.processing") : t("progress.label")}
            </span>
            <span className="font-medium">{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-white bg-opacity-50 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full ${progressColors[type]} transition-all duration-300 ease-out`}
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

interface ProgressToastContainerProps {
  toasts: Array<{
    id: string;
    type: ProgressToastType;
    title: string;
    message?: string;
    progress?: number;
  }>;
  onClose: (id: string) => void;
}

export function ProgressToastContainer({ toasts, onClose }: ProgressToastContainerProps) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ProgressToast
          key={toast.id}
          type={toast.type}
          title={toast.title}
          message={toast.message}
          progress={toast.progress}
          onClose={() => onClose(toast.id)}
          duration={toast.type !== "loading" ? 5000 : 0}
        />
      ))}
    </div>
  );
}

