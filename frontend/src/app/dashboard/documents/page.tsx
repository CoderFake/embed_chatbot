"use client";

import { useEffect, useState, useCallback } from "react";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { ToastContainer } from "@/components/ui/Toast";
import { BotListForDocuments } from "@/components/documents/BotListForDocuments";
import { Search, X } from "lucide-react";

interface Bot {
  id: string;
  name: string;
  bot_key: string;
  status: "active" | "inactive" | "draft";
  document_count?: number;
}

export default function DocumentsIndexPage() {
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

      const botsWithDocCount = await Promise.all(
        botsData.map(async (bot: Bot) => {
          try {
            const docResponse = await apiClient.get(
              `/bots/${bot.id}/documents?page=1&size=1`
            );
            return {
              ...bot,
              document_count: docResponse.data.total || 0,
            };
          } catch {
            return { ...bot, document_count: 0 };
          }
        })
      );

      setBots(botsWithDocCount);
      setFilteredBots(botsWithDocCount);
    } catch (error) {
      console.error("Failed to fetch bots:", error);
      showError("Failed to fetch bots");
    } finally {
      setLoading(false);
    }
  }, [showError]);

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

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            {t("documents.title")}
          </h1>
          <p className="text-gray-600 mt-1">{t("documents.selectBotToManage")}</p>
        </div>
      </div>

      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
          <input
            type="text"
            placeholder={t("documents.searchBots")}
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

      <BotListForDocuments bots={filteredBots} loading={loading} />

      <ToastContainer toasts={toasts} onClose={removeToast} />
    </div>
  );
}
