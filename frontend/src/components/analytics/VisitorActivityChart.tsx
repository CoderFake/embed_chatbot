"use client";

import { useEffect, useState, useCallback } from "react";
import { useLanguage } from "@/contexts/language-context";
import { apiClient } from "@/lib/auth-api";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from "recharts";
import { TrendingUp } from "lucide-react";

interface VisitorActivityChartProps {
    botId?: string;
    period: "day" | "month" | "year";
}

interface ActivityDataPoint {
    timestamp: string;
    visitor_count: number;
}

export function VisitorActivityChart({ botId, period }: VisitorActivityChartProps) {
    const { t } = useLanguage();
    const [data, setData] = useState<ActivityDataPoint[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const params = new URLSearchParams();
            if (botId) params.append("bot_id", botId);
            params.append("period", period);

            const response = await apiClient.get(`/stats/visitor-activity?${params.toString()}`);
            setData(response.data.data);
        } catch (err) {
            console.error("Failed to fetch visitor activity:", err);
            setError(t("dashboard.loadingError"));
        } finally {
            setLoading(false);
        }
    }, [botId, period, t]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const formatXAxis = (timestamp: string) => {
        const date = new Date(timestamp);
        const locale = typeof window !== 'undefined' ? window.navigator.language : 'en-US';

        if (period === "day") {
            return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
        } else if (period === "month") {
            return date.toLocaleDateString(locale, { month: "short", day: "numeric" });
        } else {
            return date.toLocaleDateString(locale, { month: "short", year: "numeric" });
        }
    };

    if (loading) {
        return (
            <div className="card">
                <div className="flex items-center justify-center h-64">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-primary)]"></div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="card">
                <div className="flex items-center justify-center h-64 text-gray-500">
                    {error}
                </div>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="card">
                <div className="flex items-center justify-center h-64 text-gray-500">
                    {t("dashboard.noData")}
                </div>
            </div>
        );
    }

    return (
        <div className="card">
            <div className="flex items-center gap-2 mb-6">
                <TrendingUp className="w-5 h-5 text-[var(--color-primary)]" />
                <h2 className="text-lg font-semibold text-gray-900">{t("dashboard.visitorActivity")}</h2>
            </div>

            <ResponsiveContainer width="100%" height={300}>
                <LineChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                        dataKey="timestamp"
                        tickFormatter={formatXAxis}
                        stroke="#6b7280"
                        style={{ fontSize: '12px' }}
                    />
                    <YAxis
                        stroke="#6b7280"
                        style={{ fontSize: '12px' }}
                    />
                    <Tooltip
                        labelFormatter={formatXAxis}
                        contentStyle={{
                            backgroundColor: 'white',
                            border: '1px solid #e5e7eb',
                            borderRadius: '8px',
                            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                        }}
                    />
                    <Legend />
                    <Line
                        type="monotone"
                        dataKey="visitor_count"
                        stroke="var(--color-primary)"
                        strokeWidth={2}
                        dot={{ fill: 'var(--color-primary)', r: 4 }}
                        activeDot={{ r: 6 }}
                        name={t("dashboard.visitors")}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
