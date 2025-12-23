"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { ToastContainer } from "@/components/ui/Toast";
import { Search, X, Users, ChevronRight, Bot } from "lucide-react";

interface Bot {
  id: string;
  name: string;
  bot_key: string;
  status: "active" | "inactive" | "draft";
  visitor_count?: number;
  display_config?: {
    header?: {
      avatar_url?: string;
    };
  };
}

export default function VisitorsIndexPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const { toasts, removeToast, error: showError } = useToast();
  const [bots, setBots] = useState<Bot[]>([]);
  const [filteredBots, setFilteredBots] = useState<Bot[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  const fetchBots = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/bots");
      const botsData = response.data;

      const botsWithVisitorCount = await Promise.all(
        botsData.map(async (bot: Bot) => {
          try {
            const visitorResponse = await apiClient.get(
              `/admin/visitors/stats/count?bot_id=${bot.id}`
            );
            return {
              ...bot,
              visitor_count: visitorResponse.data?.total || 0,
            };
          } catch {
            return { ...bot, visitor_count: 0 };
          }
        })
      );

      setBots(botsWithVisitorCount);
      setFilteredBots(botsWithVisitorCount);
    } catch (error) {
      console.error("Failed to fetch bots:", error);
      showError(t("common.error"));
    } finally {
      setLoading(false);
    }
  }, [showError, t]);

  useEffect(() => {
    fetchBots();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      setFilteredBots(
        bots.filter(
          (bot) =>
            bot.name.toLowerCase().includes(query) ||
            bot.bot_key.toLowerCase().includes(query)
        )
      );
    } else {
      setFilteredBots(bots);
    }
  }, [searchQuery, bots]);

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case "active":
        return "badge-success";
      case "inactive":
        return "badge-error";
      case "draft":
        return "badge-warning";
      default:
        return "badge-default";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            {t("visitors.title")}
          </h1>
          <p className="text-gray-600 mt-1">{t("visitors.selectBotToView")}</p>
        </div>
      </div>

      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
          <input
            type="text"
            placeholder={t("visitors.searchBots")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-field input-with-icon pr-10"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      <div className="card">
        {loading ? (
          <div className="text-center py-12 text-gray-500">
            {t("common.loading")}
          </div>
        ) : filteredBots.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            {searchQuery ? t("visitors.noBotsFound") : t("visitors.noBots")}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredBots.map((bot) => (
              <div
                key={bot.id}
                onClick={() => router.push(`/dashboard/visitors/${bot.id}`)}
                className="p-6 border border-gray-200 rounded-lg hover:border-[var(--color-primary)] hover:shadow-md transition-all cursor-pointer group"
              >
                <div className="flex items-start justify-between mb-3 gap-3">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="w-10 h-10 bg-none bg-opacity-10 rounded-lg flex items-center justify-center overflow-hidden flex-shrink-0">
                      {bot.display_config?.header?.avatar_url ? (
                        <img
                          src={bot.display_config.header.avatar_url}
                          alt={bot.name}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <Bot className="w-5 h-5 text-[var(--color-primary)]" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-gray-900 group-hover:text-[var(--color-primary)] transition-colors truncate">
                        {bot.name}
                      </h3>
                      <p className="text-xs text-gray-500 mt-0.5 truncate">
                        {bot.bot_key}
                      </p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-[var(--color-primary)] transition-colors flex-shrink-0" />
                </div>
                
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                  <span className={`badge ${getStatusBadgeClass(bot.status)}`}>
                    {t(`bots.${bot.status}`)}
                  </span>
                  <span className="text-sm text-gray-600">
                    <span className="font-semibold text-gray-900">
                      {bot.visitor_count || 0}
                    </span>{" "}
                    {t("visitors.visitors")}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <ToastContainer toasts={toasts} onClose={removeToast} />
    </div>
  );
}

