"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useLanguage } from "@/contexts/language-context";
import { LogOut } from "lucide-react";

interface LogoutButtonProps {
  variant?: "button" | "menuItem";
  showConfirm?: boolean;
}

export function LogoutButton({ variant = "button", showConfirm = true }: LogoutButtonProps) {
  const router = useRouter();
  const { logout } = useAuth();
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [showDialog, setShowDialog] = useState(false);

  const handleLogout = async () => {
    setLoading(true);
    try {
      await logout();
      router.push("/login");
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      setLoading(false);
      setShowDialog(false);
    }
  };

  const onLogoutClick = () => {
    if (showConfirm) {
      setShowDialog(true);
    } else {
      handleLogout();
    }
  };

  if (variant === "menuItem") {
    return (
      <>
        <button
          onClick={onLogoutClick}
          disabled={loading}
          className="flex items-center gap-2 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
        >
          <LogOut className="w-4 h-4" />
          <span>{loading ? t("common.loggingOut") : t("common.logout")}</span>
        </button>

        {showDialog && (
          <ConfirmDialog
            title={t("logout.confirmTitle")}
            message={t("logout.confirmMessage")}
            onConfirm={handleLogout}
            onCancel={() => setShowDialog(false)}
          />
        )}
      </>
    );
  }

  return (
    <>
      <button
        onClick={onLogoutClick}
        disabled={loading}
        className="flex items-center gap-2 px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <LogOut className="w-4 h-4" />
        <span>{loading ? t("common.loggingOut") : t("common.logout")}</span>
      </button>

      {showDialog && (
        <ConfirmDialog
          title={t("logout.confirmTitle")}
          message={t("logout.confirmMessage")}
          onConfirm={handleLogout}
          onCancel={() => setShowDialog(false)}
        />
      )}
    </>
  );
}

interface ConfirmDialogProps {
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmDialog({ title, message, onConfirm, onCancel }: ConfirmDialogProps) {
  const { t } = useLanguage();

  return (
    <div 
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
    >
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
        <p className="text-gray-600 mb-6">{message}</p>
        
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            {t("common.cancel")}
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
          >
            {t("common.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

