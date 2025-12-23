"use client";

import { useRouter } from "next/navigation";
import { Bell, UserPlus, TrendingUp, AlertCircle, X } from "lucide-react";
import { useLanguage } from "@/contexts/language-context";

interface Notification {
  id: string;
  title: string;
  message: string;
  notification_type: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

interface NotificationListProps {
  notifications: Notification[];
  loading: boolean;
  onMarkAsRead: (id: string) => void;
  onMarkAllAsRead: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

export function NotificationList({
  notifications,
  loading,
  onMarkAsRead,
  onMarkAllAsRead,
  onDelete,
  onClose,
}: NotificationListProps) {
  const router = useRouter();
  const { t } = useLanguage();

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case "invite":
        return <UserPlus className="w-5 h-5 text-blue-500" />;
      case "lead_scored":
        return <TrendingUp className="w-5 h-5 text-green-500" />;
      case "visitor_review":
        return <Bell className="w-5 h-5 text-purple-500" />;
      case "bot_alert":
        return <AlertCircle className="w-5 h-5 text-orange-500" />;
      default:
        return <Bell className="w-5 h-5 text-gray-500" />;
    }
  };

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.is_read) {
      onMarkAsRead(notification.id);
    }

    if (notification.link) {
      router.push(notification.link);
      onClose();
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return t("notifications.time.justNow");
    if (diffMins < 60) return `${diffMins}${t("notifications.time.minutesAgo")}`;
    if (diffHours < 24) return `${diffHours}${t("notifications.time.hoursAgo")}`;
    if (diffDays < 7) return `${diffDays}${t("notifications.time.daysAgo")}`;
    return date.toLocaleDateString();
  };

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">{t("notifications.title")}</h3>
        {notifications.some((n) => !n.is_read) && (
          <button
            onClick={onMarkAllAsRead}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            {t("notifications.markAllAsRead")}
          </button>
        )}
      </div>

      {/* Notification List */}
      <div className="overflow-y-auto flex-1">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-gray-500">
            <Bell className="w-12 h-12 mb-2 text-gray-300" />
            <p className="text-sm">{t("notifications.empty")}</p>
          </div>
        ) : (
          notifications.map((notification) => (
            <div
              key={notification.id}
              className={`relative p-4 hover:bg-gray-50 transition-colors border-t border-gray-100 first:border-t-0 ${!notification.is_read ? "bg-blue-50" : ""
                }`}
            >
              <div
                className="flex gap-3 cursor-pointer"
                onClick={() => handleNotificationClick(notification)}
              >
                <div className="flex-shrink-0 mt-1">
                  {getNotificationIcon(notification.notification_type)}
                </div>
                <div className="flex-1 min-w-0 pr-6">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-gray-900 line-clamp-1">
                      {notification.title}
                    </p>
                    {!notification.is_read && (
                      <span className="flex-shrink-0 w-2 h-2 bg-blue-600 rounded-full mt-1"></span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                    {notification.message}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {formatTime(notification.created_at)}
                  </p>
                </div>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(notification.id);
                }}
                className="absolute top-2 right-2 p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors"
                title={t("common.delete")}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </>
  );
}
