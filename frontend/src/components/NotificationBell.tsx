"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { Bell } from "lucide-react";
import { apiClient } from "@/lib/auth-api";
import { NotificationList } from "./NotificationList";
import { ActiveTaskItem } from "./notifications/ActiveTaskItem";
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

interface ActiveTask {
  notification_id: string;
  task_id: string;
  task_type: string;
  bot_id?: string;
  progress: number;
  status: string;
  title: string;
  message: string;
  created_at: string;
}

export function NotificationBell() {
  const { t } = useLanguage();
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, right: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const hasLoadedTasks = useRef(false);

  const fetchActiveTasks = useCallback(async () => {
    try {
      const response = await apiClient.get<ActiveTask[]>("/notifications/active-tasks");
      setActiveTasks(response.data || []);
    } catch (error) {
      console.error("Failed to fetch active tasks:", error);
    }
  }, []);

  const handleTaskComplete = useCallback(() => {
    fetchUnreadCount();
    fetchActiveTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchUnreadCount();

    if (!hasLoadedTasks.current) {
      fetchActiveTasks();
      hasLoadedTasks.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    }

    if (showDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showDropdown]);

  const fetchUnreadCount = async () => {
    try {
      const response = await apiClient.get("/notifications/count");
      setUnreadCount(response.data.unread_count);
    } catch (error) {
      console.error("Failed to fetch unread count:", error);
    }
  };

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/notifications?limit=20");
      setNotifications(response.data);
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleBellClick = async () => {
    if (!showDropdown && buttonRef.current) {
      // Calculate position
      const rect = buttonRef.current.getBoundingClientRect();
      setDropdownPosition({
        top: rect.bottom + 8,
        right: window.innerWidth - rect.right,
      });
      await fetchNotifications();
    }
    setShowDropdown(!showDropdown);
  };

  const handleMarkAsRead = async (notificationId: string) => {
    try {
      await apiClient.put(`/notifications/${notificationId}/read`);

      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
        )
      );

      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (error) {
      console.error("Failed to mark notification as read:", error);
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await apiClient.put("/notifications/read-all");

      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      );

      setUnreadCount(0);
    } catch (error) {
      console.error("Failed to mark all as read:", error);
    }
  };

  const handleDelete = async (notificationId: string) => {
    try {
      await apiClient.delete(`/notifications/${notificationId}`);

      setNotifications((prev) => prev.filter((n) => n.id !== notificationId));

      // If deleted notification was unread, update unread count
      const notification = notifications.find(n => n.id === notificationId);
      if (notification && !notification.is_read) {
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error("Failed to delete notification:", error);
    }
  };

  const dropdownContent = showDropdown && (
    <div
      ref={dropdownRef}
      className="w-96 bg-white rounded-lg shadow-lg border border-gray-200 z-[9999] min-h-[200px] max-h-[600px] overflow-hidden flex flex-col"
      style={{
        position: "fixed",
        top: `${dropdownPosition.top}px`,
        right: `${dropdownPosition.right}px`,
      }}
    >
      {/* Active Tasks Section */}
      {activeTasks.length > 0 && (
        <div className="border-b border-gray-200">
          <div className="px-4 py-2 bg-gray-50 border-b border-gray-100">
            <h3 className="text-xs font-semibold text-gray-700 uppercase">
              {t("notifications.activeTasks")}
            </h3>
          </div>
          <div className="max-h-60 overflow-y-auto">
            {activeTasks.map((task) => (
              <ActiveTaskItem
                key={task.task_id}
                taskId={task.task_id}
                title={task.title}
                initialProgress={task.progress}
                initialStatus={task.status}
                onComplete={handleTaskComplete}
              />
            ))}
          </div>
        </div>
      )}

      {/* Notifications Section */}
      <div className="flex-1 overflow-y-auto">
        <NotificationList
          notifications={notifications}
          loading={loading}
          onMarkAsRead={handleMarkAsRead}
          onMarkAllAsRead={handleMarkAllAsRead}
          onDelete={handleDelete}
          onClose={() => setShowDropdown(false)}
        />
      </div>
    </div>
  );

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleBellClick}
        className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5 text-gray-700" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-red-500 rounded-full">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {typeof window !== "undefined" && createPortal(dropdownContent, document.body)}
    </>
  );
}

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

interface ActiveTask {
  notification_id: string;
  task_id: string;
  task_type: string;
  bot_id?: string;
  progress: number;
  status: string;
  title: string;
  message: string;
  created_at: string;
}
