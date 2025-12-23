"use client";

import { useState, useEffect } from "react";
import { useLanguage } from "@/contexts/language-context";
import { X } from "lucide-react";

interface ProviderFormData {
  name: string;
  api_base_url: string;
  auth_type: "api_key" | "bearer" | "otp";
  status: "active" | "inactive";
}

interface ProviderFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: ProviderFormData) => Promise<void>;
  initialData?: Partial<ProviderFormData>;
  title: string;
}

export function ProviderFormModal({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  title,
}: ProviderFormModalProps) {
  const { t } = useLanguage();
  const [formData, setFormData] = useState<ProviderFormData>({
    name: "",
    api_base_url: "",
    auth_type: "api_key",
    status: "active",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name || "",
        api_base_url: initialData.api_base_url || "",
        auth_type: initialData.auth_type || "api_key",
        status: initialData.status || "active",
      });
    }
  }, [initialData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onSubmit(formData);
      onClose();
    } catch (error) {
      console.error("Failed to submit provider:", error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black flex items-center justify-center z-50"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t("providers.providerName")}
            </label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="OpenAI"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t("providers.apiBaseUrl")}
            </label>
            <input
              type="url"
              required
              value={formData.api_base_url}
              onChange={(e) => setFormData({ ...formData, api_base_url: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="https://api.openai.com/v1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("providers.authType")}
              </label>
              <select
                value={formData.auth_type}
                onChange={(e) => setFormData({ ...formData, auth_type: e.target.value as "api_key" | "bearer" | "otp" })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="api_key">{t("providers.apiKey")}</option>
                <option value="bearer">{t("providers.bearer")}</option>
                <option value="otp">{t("providers.otp")}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("providers.status")}
              </label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as "active" | "inactive" })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="active">{t("common.active")}</option>
                <option value="inactive">{t("common.inactive")}</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? t("common.saving") : t("common.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

