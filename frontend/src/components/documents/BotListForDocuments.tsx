"use client";

import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { FileText, ChevronRight, Bot as BotIcon } from "lucide-react";

interface Bot {
  id: string;
  name: string;
  bot_key: string;
  status: "active" | "inactive" | "draft";
  document_count?: number;
  display_config?: {
    header?: {
      avatar_url?: string;
    };
  };
}

interface BotListForDocumentsProps {
  bots: Bot[];
  loading: boolean;
}

export function BotListForDocuments({ bots, loading }: BotListForDocumentsProps) {
  const router = useRouter();
  const { t } = useLanguage();

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="card animate-pulse">
            <div className="h-32 bg-gray-200 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  if (bots.length === 0) {
    return (
      <div className="card text-center py-12">
        <BotIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          {t("documents.noBots")}
        </h3>
        <p className="text-gray-600 mb-6">{t("documents.createBotFirst")}</p>
        <button
          onClick={() => router.push("/dashboard/bots/create")}
          className="btn-primary"
        >
          {t("bots.create")}
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {bots.map((bot) => (
        <button
          key={bot.id}
          onClick={() => router.push(`/dashboard/documents/${bot.id}`)}
          className="card hover:shadow-lg transition-all duration-200 text-left group"
        >
          <div className="flex items-start justify-between mb-4 gap-3">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="w-10 h-10 bg-none bg-opacity-10 rounded-lg flex items-center justify-center overflow-hidden flex-shrink-0">
                {bot.display_config?.header?.avatar_url ? (
                  <img
                    src={bot.display_config.header.avatar_url}
                    alt={bot.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <BotIcon className="w-5 h-5 text-[var(--color-primary)]" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary transition-colors truncate">
                  {bot.name}
                </h3>
                <p className="text-sm text-gray-500 font-mono truncate">{bot.bot_key}</p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-primary transition-colors flex-shrink-0" />
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-gray-100">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-600">
                {bot.document_count || 0} {t("documents.documents")}
              </span>
            </div>
            <span
              className={`px-2 py-1 text-xs font-medium rounded-full ${bot.status === "active"
                ? "bg-green-100 text-green-800"
                : bot.status === "inactive"
                  ? "bg-gray-100 text-gray-800"
                  : "bg-yellow-100 text-yellow-800"
                }`}
            >
              {t(`bots.${bot.status}`)}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

