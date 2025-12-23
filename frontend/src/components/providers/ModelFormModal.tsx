"use client";

import { useState, useEffect } from "react";
import { useLanguage } from "@/contexts/language-context";
import { X } from "lucide-react";

interface ModelFormData {
  name: string;
  model_type: "chat" | "embedding";
  context_window: number;
  pricing: number;
  is_active: boolean;
  extra_data: {
    cost_per_1k_input: number;
    cost_per_1k_output: number;
    currency: string;
  };
}

interface ModelFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: ModelFormData) => Promise<void>;
  initialData?: Partial<ModelFormData>;
  title: string;
}

export function ModelFormModal({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  title,
}: ModelFormModalProps) {
  const { t } = useLanguage();
  const [formData, setFormData] = useState<ModelFormData>({
    name: "",
    model_type: "chat",
    context_window: 4096,
    pricing: 0,
    is_active: true,
    extra_data: {
      cost_per_1k_input: 0,
      cost_per_1k_output: 0,
      currency: "USD",
    },
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name || "",
        model_type: initialData.model_type || "chat",
        context_window: initialData.context_window || 4096,
        pricing: initialData.pricing || 0,
        is_active: initialData.is_active ?? true,
        extra_data: {
          cost_per_1k_input: initialData.extra_data?.cost_per_1k_input || 0,
          cost_per_1k_output: initialData.extra_data?.cost_per_1k_output || 0,
          currency: initialData.extra_data?.currency || "USD",
        },
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
      console.error("Failed to submit model:", error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black flex items-center justify-center z-50"
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
              {t("providers.modelName")}
            </label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="gpt-4-turbo"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("providers.modelType")}
              </label>
              <select
                value={formData.model_type}
                onChange={(e) => setFormData({ ...formData, model_type: e.target.value as "chat" | "embedding" })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="chat">{t("providers.chat")}</option>
                <option value="embedding">{t("providers.embedding")}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("providers.contextWindow")}
              </label>
              <input
                type="number"
                required
                min="1"
                value={formData.context_window}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  setFormData({ ...formData, context_window: isNaN(val) ? 4096 : val });
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>




          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("providers.inputCost")}
              </label>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={formData.extra_data.cost_per_1k_input}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setFormData({
                    ...formData,
                    extra_data: {
                      ...formData.extra_data,
                      cost_per_1k_input: isNaN(val) ? 0 : val,
                    },
                  });
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">{t("providers.inputCostHint")}</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("providers.outputCost")}
              </label>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={formData.extra_data.cost_per_1k_output}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setFormData({
                    ...formData,
                    extra_data: {
                      ...formData.extra_data,
                      cost_per_1k_output: isNaN(val) ? 0 : val,
                    },
                  });
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">{t("providers.outputCostHint")}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="is_active" className="text-sm font-medium text-gray-700">
              {t("providers.activeModel")}
            </label>
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
