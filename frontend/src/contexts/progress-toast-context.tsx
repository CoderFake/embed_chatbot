"use client";

import React, { createContext, useContext, ReactNode } from "react";
import { useProgressToast } from "@/hooks/useProgressToast";
import { ProgressToastContainer } from "@/components/ui/ProgressToast";
import { SSEProgressToast } from "@/components/ui/SSEProgressToast";
import { ProgressToastType } from "@/components/ui/ProgressToast";

interface ProgressToastContextType {
  addToast: (
    type: ProgressToastType,
    title: string,
    message?: string,
    progress?: number
  ) => string;
  addSSEToast: (taskId: string, title: string) => string;
  updateToast: (
    id: string,
    updates: {
      type?: ProgressToastType;
      title?: string;
      message?: string;
      progress?: number;
    }
  ) => void;
  removeToast: (id: string) => void;
  clearAll: () => void;
}

const ProgressToastContext = createContext<
  ProgressToastContextType | undefined
>(undefined);

export function ProgressToastProvider({ children }: { children: ReactNode }) {
  const {
    toasts,
    addToast,
    addSSEToast,
    updateToast,
    removeToast,
    clearAll,
  } = useProgressToast();

  return (
    <ProgressToastContext.Provider
      value={{
        addToast,
        addSSEToast,
        updateToast,
        removeToast,
        clearAll,
      }}
    >
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) =>
          toast.taskId ? (
            <SSEProgressToast
              key={toast.id}
              taskId={toast.taskId}
              title={toast.title}
              onClose={() => removeToast(toast.id)}
            />
          ) : (
            <ProgressToastContainer
              key={toast.id}
              toasts={[toast]}
              onClose={removeToast}
            />
          )
        )}
      </div>
    </ProgressToastContext.Provider>
  );
}

export function useProgressToastContext() {
  const context = useContext(ProgressToastContext);
  if (!context) {
    throw new Error(
      "useProgressToastContext must be used within ProgressToastProvider"
    );
  }
  return context;
}

