/**
 * Confirmation dialog component
 */
"use client";

import { AlertTriangle } from "lucide-react";
import { Modal } from "./Modal";

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  type?: "danger" | "warning" | "info";
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = "Confirm",
  cancelText = "Cancel",
  type = "danger",
}: ConfirmDialogProps) {
  const iconColors = {
    danger: "text-red-600",
    warning: "text-red-600",
    info: "text-red-600",
  };

  const buttonColors = {
    danger: "bg-red-600 hover:bg-red-700",
    warning: "bg-red-600 hover:bg-red-700",
    info: "bg-red-600 hover:bg-red-700",
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <AlertTriangle className={`w-20 h-20 ${iconColors[type]}`} />
          <p className="text-gray-700">{message}</p>
        </div>

        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="btn-outline">
            {cancelText}
          </button>
          <button
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className={`${buttonColors[type]} text-white font-semibold py-2 px-4 rounded-lg transition-colors`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </Modal>
  );
}

