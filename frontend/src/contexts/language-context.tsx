"use client";

import React, { createContext, useContext, useState } from "react";
import enTranslations from "@/locales/en.json";
import viTranslations from "@/locales/vi.json";

type Locale = "en" | "vi";

interface LanguageContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
}

const translations = {
  en: enTranslations,
  vi: viTranslations,
};

const LanguageContext = createContext<LanguageContextType>({
  locale: "vi",
  setLocale: () => {},
  t: () => "",
});

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window !== "undefined") {
      const savedLocale = localStorage.getItem("locale") as Locale;
      if (savedLocale && (savedLocale === "en" || savedLocale === "vi")) {
        return savedLocale;
      }
    }
    return "vi";
  });

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem("locale", newLocale);
  };

  const t = (key: string): string => {
    const keys = key.split(".");
    let value: unknown = translations[locale];

    for (const k of keys) {
      if (value && typeof value === "object" && k in value) {
        value = (value as Record<string, unknown>)[k];
      } else {
        return key; // Return key if translation not found
      }
    }

    return typeof value === "string" ? value : key;
  };

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
};

