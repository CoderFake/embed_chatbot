"use client";

import { Menu } from "lucide-react";
import { Logo } from "@/components/Logo";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { LogoutButton } from "@/components/LogoutButton";
import { NotificationBell } from "@/components/NotificationBell";

interface AdminHeaderProps {
  onMenuClick: () => void;
}

export function AdminHeader({ onMenuClick }: AdminHeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 shadow-sm relative overflow-visible">
      <div className="flex items-center justify-between h-16 px-4 lg:px-6">
        {/* Left: Menu Button (Mobile) + Logo */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="p-2 rounded-lg hover:bg-gray-100 lg:hidden"
            aria-label="Toggle menu"
          >
            <Menu className="w-6 h-6" />
          </button>

          <div className="lg:hidden">
            <Logo variant="icon" />
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-3">
          <NotificationBell />
          <LanguageSwitcher />
          <LogoutButton variant="button" />
        </div>
      </div>
    </header>
  );
}

