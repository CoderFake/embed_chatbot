"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useLanguage } from "@/contexts/language-context";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import {
  LayoutDashboard,
  Bot,
  Users,
  Mail,
  FileText,
  UserRound,
  X,
  Boxes
} from "lucide-react";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { t } = useLanguage();
  const { isRoot } = useCurrentUser();

  const menuItems = [
    {
      key: "dashboard",
      label: t("nav.dashboard"),
      icon: LayoutDashboard,
      href: "/dashboard",
    },
    {
      key: "bots",
      label: t("nav.bots"),
      icon: Bot,
      href: "/dashboard/bots",
    },
    {
      key: "users",
      label: t("nav.users"),
      icon: Users,
      href: "/dashboard/users",
    },
    {
      key: "invites",
      label: t("nav.invites"),
      icon: Mail,
      href: "/dashboard/invites",
    },
    {
      key: "documents",
      label: t("nav.documents"),
      icon: FileText,
      href: "/dashboard/documents",
    },
    {
      key: "visitors",
      label: t("nav.visitors"),
      icon: UserRound,
      href: "/dashboard/visitors",
    },
    ...(isRoot() ? [{
      key: "providers",
      label: t("nav.providers"),
      icon: Boxes,
      href: "/dashboard/providers",
    }] : []),
  ];

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === href;
    }
    return pathname?.startsWith(href);
  };

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 backdrop-blur-sm z-40 lg:hidden transition-all duration-300"
          style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)' }}
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-screen bg-white border-r border-gray-200
          transition-transform duration-300 ease-in-out
          w-64
          ${isOpen ? "translate-x-0 z-50" : "-translate-x-full -z-10"}
          lg:translate-x-0 lg:z-10
        `}
      >
        {/* Mobile Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-100 lg:hidden"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Sidebar Content */}
        <div className="flex flex-col h-full overflow-hidden">
          {/* Logo Area */}
          <div className="px-6 py-5 border-b border-gray-200 flex-shrink-0">
            <h2 className="text-xl font-bold text-[var(--color-primary)]">
              Embed Chatbot Admin
            </h2>
          </div>

          {/* Navigation Menu */}
          <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);

              return (
                <Link
                  key={item.key}
                  href={item.href}
                  onClick={() => onClose()}
                  className={`
                    sidebar-item
                    ${active ? "sidebar-item-active" : ""}
                  `}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-200 flex-shrink-0">
            <p className="text-xs text-gray-500">
              © 2025 NewWave Solutions
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}

