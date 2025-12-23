"use client";

import { useLanguage } from "@/contexts/language-context";
import { formatDistanceToNow } from "date-fns";
import { vi, enUS } from "date-fns/locale";

interface Activity {
  id: string;
  type: "create" | "update" | "delete" | "activate" | "invite";
  message: string;
  timestamp: string;
}

interface ActivityFeedProps {
  activities: Activity[];
  loading?: boolean;
}

const activityColors = {
  create: "bg-green-500",
  update: "bg-blue-500",
  delete: "bg-red-500",
  activate: "bg-orange-500",
  invite: "bg-purple-500",
};

export function ActivityFeed({ activities, loading = false }: ActivityFeedProps) {
  const { locale } = useLanguage();

  const getTimeAgo = (timestamp: string) => {
    try {
      return formatDistanceToNow(new Date(timestamp), {
        addSuffix: true,
        locale: locale === "vi" ? vi : enUS,
      });
    } catch {
      return timestamp;
    }
  };

  const { t } = useLanguage();

  if (loading) {
    return (
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {t("dashboard.recentActivity")}
        </h2>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg animate-pulse">
              <div className="w-2 h-2 bg-gray-300 rounded-full"></div>
              <div className="flex-1 h-4 bg-gray-300 rounded"></div>
              <div className="w-20 h-3 bg-gray-300 rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {t("dashboard.recentActivity")}
        </h2>
        <p className="text-center text-gray-500 py-8">
          {t("dashboard.noRecentActivity")}
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        {t("dashboard.recentActivity")}
      </h2>
      <div className="space-y-3">
        {activities.map((activity) => (
          <div key={activity.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
            <div className={`w-2 h-2 ${activityColors[activity.type]} rounded-full flex-shrink-0`}></div>
            <p className="text-sm text-gray-700 flex-1">{activity.message}</p>
            <span className="ml-auto text-xs text-gray-500 whitespace-nowrap">
              {getTimeAgo(activity.timestamp)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

