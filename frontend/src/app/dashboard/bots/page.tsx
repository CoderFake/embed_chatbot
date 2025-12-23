"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/error-utils";
import { ToastContainer } from "@/components/ui/Toast";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { RecrawlConfirmDialog } from "@/components/bots/RecrawlConfirmDialog";
import { Plus, Search, Edit, Trash2, Power, PowerOff, RotateCw } from "lucide-react";

interface Bot {
  id: string;
  name: string;
  bot_key: string;
  language: string | null;
  status: "active" | "inactive" | "draft";
  origin: string | null;
  created_at: string;
}

export default function BotsPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const toast = useToast();
  const [bots, setBots] = useState<Bot[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [botToDelete, setBotToDelete] = useState<Bot | null>(null);
  const [botToRecrawl, setBotToRecrawl] = useState<Bot | null>(null);

  useEffect(() => {
    fetchBots();
  }, []);

  const fetchBots = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/bots");
      setBots(response.data);
    } catch (error) {
      console.error("Failed to fetch bots:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async (botId: string) => {
    try {
      await apiClient.post(`/bots/${botId}/activate`);
      fetchBots();
    } catch (error) {
      console.error("Failed to activate bot:", error);
    }
  };

  const handleDeactivate = async (botId: string) => {
    try {
      await apiClient.post(`/bots/${botId}/deactivate`);
      fetchBots();
    } catch (error) {
      console.error("Failed to deactivate bot:", error);
    }
  };

  const handleDelete = async () => {
    if (!botToDelete) return;

    try {
      await apiClient.delete(`/bots/${botToDelete.id}`);
      toast.success(t("bots.botDeleted"));
      fetchBots();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    } finally {
      setBotToDelete(null);
    }
  };

  const filteredBots = bots.filter((bot) =>
    bot.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    bot.origin?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    const badges = {
      active: "badge-success",
      inactive: "badge-error",
      draft: "badge-warning",
    };
    return badges[status as keyof typeof badges] || "badge-info";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t("bots.title")}</h1>
          <p className="text-gray-600 mt-1">{t("bots.manageBots")}</p>
        </div>
        <button
          onClick={() => router.push("/dashboard/bots/create")}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          {t("bots.create")}
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

      {/* Bots Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("bots.name")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("bots.status")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("bots.origin")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("bots.language")}
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("bots.actions")}
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
              ) : filteredBots.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                    {t("bots.noBots")}
                  </td>
                </tr>
              ) : (
                filteredBots.map((bot) => (
                  <tr key={bot.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{bot.name}</div>
                        <div className="text-sm text-gray-500">{bot.bot_key}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`badge ${getStatusBadge(bot.status)}`}>
                        {t(`bots.${bot.status}`)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {bot.origin || "-"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {bot.language || "-"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => router.push(`/dashboard/bots/${bot.id}`)}
                          className="text-[var(--color-primary)] hover:text-[var(--color-primary-dark)]"
                          title={t("bots.edit")}
                        >
                          <Edit className="w-4 h-4" />
                        </button>

                        {bot.status === "active" ? (
                          <button
                            onClick={() => handleDeactivate(bot.id)}
                            className="text-orange-600 hover:text-orange-700"
                            title={t("bots.deactivate")}
                          >
                            <PowerOff className="w-4 h-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleActivate(bot.id)}
                            className="text-green-600 hover:text-green-700"
                            title={t("bots.activate")}
                          >
                            <Power className="w-4 h-4" />
                          </button>
                        )}

                        <button
                          onClick={() => setBotToRecrawl(bot)}
                          className="text-blue-600 hover:text-blue-700"
                          title={t("bots.recrawl")}
                        >
                          <RotateCw className="w-4 h-4" />
                        </button>

                        <button
                          onClick={() => setBotToDelete(bot)}
                          className="text-red-600 hover:text-red-700"
                          title={t("bots.delete")}
                        >
                          <Trash2 className="w-4 h-4" />
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

      {/* Delete Confirmation */}
      {botToDelete && (
        <ConfirmDialog
          isOpen={true}
          onClose={() => setBotToDelete(null)}
          onConfirm={handleDelete}
          title={t("bots.confirmDelete")}
          message={`${t("common.confirmMessage")} "${botToDelete.name}"?`}
          confirmText={t("common.delete")}
          cancelText={t("common.cancel")}
          type="danger"
        />
      )}

      {/* Recrawl Confirmation */}

      {/* Recrawl Confirmation */}
      <RecrawlConfirmDialog
        botId={botToRecrawl?.id || null}
        botName={botToRecrawl?.name || null}
        isOpen={!!botToRecrawl}
        onClose={() => setBotToRecrawl(null)}
        onSuccess={fetchBots}
      />


      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </div>
  );
}

