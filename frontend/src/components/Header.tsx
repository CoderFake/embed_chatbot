"use client";

import { Logo } from "@/components/Logo";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { LogoutButton } from "@/components/LogoutButton";
import { useAuth } from "@/contexts/auth-context";

export function Header() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return null;
  }

  return (
    <header className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Logo variant="full" />
          </div>

          {/* Right Side Actions */}
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <LogoutButton variant="button" />
          </div>
        </div>
      </div>
    </header>
  );
}

