"use client";

import { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
  bgColor?: string;
  loading?: boolean;
}

export function StatCard({ 
  label, 
  value, 
  icon: Icon, 
  color = "text-[var(--color-primary)]",
  bgColor = "bg-[var(--color-primary)]/10",
  loading = false
}: StatCardProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-600 mb-1">{label}</p>
          {loading ? (
            <div className="h-8 w-16 bg-gray-200 animate-pulse rounded"></div>
          ) : (
            <p className="text-2xl font-bold text-gray-900">{value}</p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${bgColor}`}>
          <Icon className={`w-6 h-6 ${color}`} />
        </div>
      </div>
    </div>
  );
}

