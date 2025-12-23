/**
 * Recrawl confirmation dialog component
 * Reusable across bot list and detail pages
 */
"use client";

import { useState } from "react";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { apiClient } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/error-utils";

interface RecrawlConfirmDialogProps {
  botId: string | null;
  botName: string | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function RecrawlConfirmDialog({
  botId,
  botName,
  isOpen,
  onClose,
  onSuccess,
}: RecrawlConfirmDialogProps) {
  const { t } = useLanguage();
  const toast = useToast();

  const handleConfirm = async () => {
    if (!botId) return;

    try {
      await apiClient.post(`/bots/${botId}/recrawl`);
      toast.success(t("bots.recrawlStarted"));
      onSuccess?.();
      onClose();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    }
  };

  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={handleConfirm}
      title={t("bots.recrawl")}
      message={`${t("bots.confirmRecrawl")} "${botName}"?`}
      confirmText={t("common.confirm")}
      cancelText={t("common.cancel")}
      type="warning"
    />
  );
}

