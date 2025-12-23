/**
 * Bot action buttons component (Activate, Deactivate, Recrawl)
 */
"use client";

import { useState } from "react";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { apiClient } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/error-utils";
import { RecrawlConfirmDialog } from "@/components/bots/RecrawlConfirmDialog";
import { PlayCircle, PauseCircle, RefreshCw } from "lucide-react";

interface BotActionsProps {
  botId: string;
  botName: string;
  status: "active" | "inactive" | "draft";
  onStatusChange: () => void;
}

export function BotActions({ botId, botName, status, onStatusChange }: BotActionsProps) {
  const { t } = useLanguage();
  const toast = useToast();

  const [confirmAction, setConfirmAction] = useState<"activate" | "deactivate" | null>(
    null
  );
  const [showRecrawlDialog, setShowRecrawlDialog] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleActivate = async () => {
    setLoading(true);
    try {
      await apiClient.post(`/bots/${botId}/activate`);
      toast.success(t("bots.botActivated"));
      onStatusChange();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivate = async () => {
    setLoading(true);
    try {
      await apiClient.post(`/bots/${botId}/deactivate`);
      toast.success(t("bots.botDeactivated"));
      onStatusChange();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    } finally {
      setLoading(false);
    }
  };



  const handleConfirm = () => {
    if (confirmAction === "activate") {
      handleActivate();
    } else if (confirmAction === "deactivate") {
      handleDeactivate();
    }
    setConfirmAction(null);
  };

  return (
    <>
      <div className="flex gap-2">
        {/* Activate/Deactivate */}
        {status === "active" ? (
          <button
            onClick={() => setConfirmAction("deactivate")}
            className="btn-outline flex items-center gap-2"
            disabled={loading}
          >
            {loading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <PauseCircle className="w-4 h-4" />
            )}
            {t("bots.deactivate")}
          </button>
        ) : (
          <button
            onClick={() => setConfirmAction("activate")}
            className="btn-primary flex items-center gap-2"
            disabled={loading}
          >
            {loading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <PlayCircle className="w-4 h-4" />
            )}
            {t("bots.activate")}
          </button>
        )}

        {/* Recrawl */}
        <button
          onClick={() => setShowRecrawlDialog(true)}
          className="btn-outline flex items-center gap-2"
          disabled={loading}
        >
          {loading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          {t("bots.recrawl")}
        </button>
      </div>

      {/* Confirm Dialogs */}
      <ConfirmDialog
        isOpen={confirmAction === "activate"}
        onClose={() => setConfirmAction(null)}
        onConfirm={handleConfirm}
        title={t("bots.activate")}
        message={t("bots.confirmActivate")}
        confirmText={t("common.confirm")}
        cancelText={t("common.cancel")}
        type="info"
      />

      <ConfirmDialog
        isOpen={confirmAction === "deactivate"}
        onClose={() => setConfirmAction(null)}
        onConfirm={handleConfirm}
        title={t("bots.deactivate")}
        message={t("bots.confirmDeactivate")}
        confirmText={t("common.confirm")}
        cancelText={t("common.cancel")}
        type="warning"
      />

      {/* Recrawl Confirmation */}
      <RecrawlConfirmDialog
        botId={botId}
        botName={botName}
        isOpen={showRecrawlDialog}
        onClose={() => setShowRecrawlDialog(false)}
        onSuccess={onStatusChange}
      />
    </>
  );
}

