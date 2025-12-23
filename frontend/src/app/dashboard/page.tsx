"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/contexts/language-context";
import { apiClient } from "@/lib/auth-api";
import { Bot, Users, Eye } from "lucide-react";
import { StatCard } from "@/components/admin/StatCard";
import { VisitorActivityChart } from "@/components/analytics/VisitorActivityChart";

interface DashboardStats {
  total_bots: number;
  total_users: number;
  total_visitors: number;
}

interface BotOption {
  id: string;
  name: string;
}

export default function DashboardPage() {
  const { t } = useLanguage();
  const [stats, setStats] = useState<DashboardStats>({
    total_bots: 0,
    total_users: 0,
    total_visitors: 0,
  });
  const [bots, setBots] = useState<BotOption[]>([]);
  const [selectedBotId, setSelectedBotId] = useState<string>("");
  const [selectedPeriod, setSelectedPeriod] = useState<"day" | "month" | "year">("day");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);

      // Fetch stats summary
      const statsResponse = await apiClient.get("/stats/summary");
      setStats(statsResponse.data);

      // Fetch bots for dropdown
      const botsResponse = await apiClient.get("/bots");
      const botsList = botsResponse.data;
      setBots(botsList);
      if (botsList.length > 0) {
        setSelectedBotId(botsList[0].id);
      }
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      label: t("dashboard.totalBots"),
      value: stats.total_bots,
      icon: Bot,
      color: "text-[var(--color-primary)]",
      bgColor: "bg-[var(--color-primary)]/10",
    },
    {
      label: t("dashboard.activeUsers"),
      value: stats.total_users,
      icon: Users,
      color: "text-[var(--color-secondary)]",
      bgColor: "bg-[var(--color-secondary)]/10",
    },
    {
      label: t("dashboard.totalVisitors"),
      value: stats.total_visitors.toLocaleString(),
      icon: Eye,
      color: "text-green-600",
      bgColor: "bg-green-100",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">
          {t("dashboard.title")}
        </h1>
        <p className="text-gray-600 mt-1">
          {t("dashboard.welcome")}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {statCards.map((stat, index) => (
          <StatCard
            key={index}
            label={stat.label}
            value={stat.value}
            icon={stat.icon}
            color={stat.color}
            bgColor={stat.bgColor}
            loading={loading}
          />
        ))}
      </div>

      {/* Statistics Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            {t("dashboard.statistics")}
          </h2>

          <div className="flex items-center gap-3">
            {/* Bot Selector */}
            <select
              value={selectedBotId}
              onChange={(e) => setSelectedBotId(e.target.value)}
              className="input-field w-48"
              disabled={loading || bots.length === 0}
            >
              {bots.map((bot) => (
                <option key={bot.id} value={bot.id}>
                  {bot.name}
                </option>
              ))}
            </select>

            {/* Period Selector */}
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value as "day" | "month" | "year")}
              className="input-field w-32"
            >
              <option value="day">{t("dashboard.day")}</option>
              <option value="month">{t("dashboard.month")}</option>
              <option value="year">{t("dashboard.year")}</option>
            </select>
          </div>
        </div>

        {/* Visitor Activity Chart */}
        <VisitorActivityChart
          botId={selectedBotId}
          period={selectedPeriod}
        />
      </div>
    </div>
  );
}
