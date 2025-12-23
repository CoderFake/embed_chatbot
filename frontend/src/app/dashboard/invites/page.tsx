"use client";

import { useEffect, useState, useCallback } from "react";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/error-utils";
import { ToastContainer } from "@/components/ui/Toast";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { BulkInviteModal } from "@/components/invites/BulkInviteModal";
import { Plus, Search, Mail, RefreshCw, XCircle } from "lucide-react";

interface Invite {
  id: string;
  email: string;
  role: string;
  status: "pending" | "accepted" | "expired" | "revoked";
  expires_at: string;
  created_at: string;
}

export default function InvitesPage() {
  const { t } = useLanguage();
  const toast = useToast();
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteToRevoke, setInviteToRevoke] = useState<Invite | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const fetchInvites = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/admin/invites");
      setInvites(response.data);
    } catch (error: unknown) {
      console.error("Failed to fetch invites:", error);
      toast.error(getErrorMessage(error, t("common.error")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchInvites();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreateInvites = async (inviteList: Array<{ email: string; role: string }>) => {
    try {
      await apiClient.post("/admin/invites", {
        invites: inviteList,
      });
      toast.success(t("invites.inviteCreated"));
      fetchInvites();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
      throw error;
    }
  };

  const handleResendInvite = async (inviteId: string) => {
    try {
      await apiClient.post(`/admin/invites/${inviteId}/resend`);
      toast.success(t("invites.inviteResent"));
      fetchInvites();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    }
  };

  const handleRevokeInvite = async () => {
    if (!inviteToRevoke) return;

    try {
      await apiClient.post(`/admin/invites/${inviteToRevoke.id}/revoke`);
      toast.success(t("invites.inviteRevoked"));
      fetchInvites();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    } finally {
      setInviteToRevoke(null);
    }
  };

  const filteredInvites = invites.filter((invite) =>
    invite.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusBadge = (status: string) => {
    const badges = {
      pending: "badge-warning",
      accepted: "badge-success",
      expired: "badge-error",
    };
    return badges[status as keyof typeof badges] || "badge-info";
  };

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t("invites.title")}</h1>
          <p className="text-gray-600 mt-1">{t("invites.manageInvites")}</p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          {t("invites.create")}
        </button>
      </div>

      {/* Search */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
          <input
            type="text"
            placeholder={t("common.search")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-field input-with-icon"
          />
        </div>
      </div>

      {/* Invites Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("invites.email")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("invites.role")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("invites.status")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("invites.expiresAt")}
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("invites.actions")}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    {t("common.loading")}
                  </td>
                </tr>
              ) : filteredInvites.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    {t("invites.noInvites")}
                  </td>
                </tr>
              ) : (
                filteredInvites.map((invite) => (
                  <tr key={invite.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <Mail className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-900">{invite.email}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="badge badge-info">
                        {invite.role}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`badge ${getStatusBadge(invite.status)}`}>
                        {t(`invites.${invite.status}`)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(invite.expires_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => handleResendInvite(invite.id)}
                          className="text-[var(--color-primary)] hover:text-[var(--color-primary-dark)] flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                          disabled={invite.status !== "pending"}
                        >
                          <RefreshCw className="w-4 h-4" />
                          {t("invites.resend")}
                        </button>
                        <button
                          onClick={() => setInviteToRevoke(invite)}
                          className="text-red-600 hover:text-red-700 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                          disabled={invite.status !== "pending"}
                        >
                          <XCircle className="w-4 h-4" />
                          {t("invites.revoke")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bulk Invite Modal */}
      <BulkInviteModal
        isOpen={showInviteModal}
        onClose={() => setShowInviteModal(false)}
        onSubmit={handleCreateInvites}
      />

      {/* Revoke Confirmation */}
      <ConfirmDialog
        isOpen={!!inviteToRevoke}
        onClose={() => setInviteToRevoke(null)}
        onConfirm={handleRevokeInvite}
        title={t("invites.revoke")}
        message={t("invites.confirmRevoke")}
        confirmText={t("common.confirm")}
        cancelText={t("common.cancel")}
        type="danger"
      />
    </div>
  );
}

