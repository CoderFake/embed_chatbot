"use client";

import { useLanguage } from "@/contexts/language-context";
import { Globe } from "lucide-react";

export function LanguageSwitcher() {
  const { locale, setLocale } = useLanguage();

  const toggleLanguage = () => {
    setLocale(locale === "en" ? "vi" : "en");
  };

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors rounded-lg hover:bg-gray-100"
      aria-label="Switch language"
    >
      <Globe className="w-4 h-4" />
      <span className="font-medium">{locale === "en" ? "EN" : "VI"}</span>
    </button>
  );
}

