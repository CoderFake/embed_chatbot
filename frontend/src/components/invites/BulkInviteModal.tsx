/**
 * Bulk Invite Modal Component
 */
"use client";

import { useState, useMemo, useEffect } from "react";
import { useLanguage } from "@/contexts/language-context";
import { useRoles } from "@/hooks/useRoles";
import { Modal } from "@/components/ui/Modal";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Plus, X } from "lucide-react";
import { apiClient } from "@/lib/auth-api";

interface InviteItem {
  email: string;
  role: string;
}

interface BulkInviteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (invites: InviteItem[]) => Promise<void>;
}

export function BulkInviteModal({ isOpen, onClose, onSubmit }: BulkInviteModalProps) {
  const { t } = useLanguage();
  const { roles, loading: rolesLoading } = useRoles();
  const [currentUserRole, setCurrentUserRole] = useState<string | null>(null);

  const [invites, setInvites] = useState<InviteItem[]>([{ email: "", role: "member" }]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const fetchCurrentUser = async () => {
      try {
        const response = await apiClient.get("/auth/me");
        setCurrentUserRole(response.data.role);
      } catch (error) {
        console.error("Failed to fetch current user:", error);
      }
    };
    fetchCurrentUser();
  }, []);

  const availableRoles = useMemo(() => {
    if (currentUserRole === "admin") {
      return roles.filter(role => role.value !== "root");
    }
    return roles;
  }, [roles, currentUserRole]);

  const addInvite = () => {
    if (invites.length >= 50) {
      return;
    }
    setInvites([...invites, { email: "", role: "member" }]);
  };

  const removeInvite = (index: number) => {
    if (invites.length === 1) return;
    setInvites(invites.filter((_, i) => i !== index));
  };

  const updateInvite = (index: number, field: keyof InviteItem, value: string) => {
    const newInvites = [...invites];
    newInvites[index][field] = value;
    setInvites(newInvites);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate
    const validInvites = invites.filter((inv) => inv.email.trim() && inv.role);
    if (validInvites.length === 0) {
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit(validInvites);
      setInvites([{ email: "", role: "member" }]);
      onClose();
    } catch {
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={t("invites.bulkInvite")}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-gray-600">
          Maximum 50 invitations per request
        </p>

        {/* Invite List */}
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {invites.map((invite, index) => (
            <div key={index} className="flex gap-3 items-start">
              <div className="flex-1 min-w-0">
                <input
                  type="email"
                  value={invite.email}
                  onChange={(e) => updateInvite(index, "email", e.target.value)}
                  placeholder={t("invites.emailPlaceholder")}
                  className="input-field w-full"
                  required
                />
              </div>

              <div className="w-48 flex-shrink-0">
                <select
                  value={invite.role}
                  onChange={(e) => updateInvite(index, "role", e.target.value)}
                  className="input-field w-full"
                  disabled={rolesLoading}
                  required
                >
                  {availableRoles.map((role) => (
                    <option key={role.value} value={role.value}>
                      {role.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => removeInvite(index)}
                className="p-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg disabled:opacity-50 transition-colors flex-shrink-0"
                disabled={invites.length === 1}
                title={t("common.delete")}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          ))}
        </div>

        {/* Add Button */}
        {invites.length < 50 && (
          <button
            type="button"
            onClick={addInvite}
            className="btn-outline flex items-center gap-2 w-full"
          >
            <Plus className="w-4 h-4" />
            {t("invites.addEmail")} ({invites.length}/50)
          </button>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="btn-outline"
            disabled={submitting}
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            className="btn-primary flex items-center gap-2"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <LoadingSpinner size="sm" />
                {t("common.loading")}
              </>
            ) : (
              t("common.create")
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}

