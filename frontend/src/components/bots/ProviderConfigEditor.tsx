"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Save, Eye, EyeOff, Plus, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/auth-api";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { ToastContainer } from "@/components/ui/Toast";
import { useCurrentUser } from "@/hooks/useCurrentUser";

interface Provider {
  id: string;
  name: string;
  slug: string;
  api_base_url: string;
}

interface Model {
  id: string;
  name: string;
  provider_id: string;
}

interface ApiKey {
  key: string;
  name: string;
  active: boolean;
}

interface ProviderConfig {
  provider_id: string;
  model_id: string;
  api_keys: ApiKey[];
  config?: {
    temperature?: number;
    max_tokens?: number;
    [key: string]: unknown;
  };
}

interface ProviderConfigResponse {
  id: string;
  bot_id: string;
  provider_id: string;
  model_id: string;
  is_active: boolean;
  config: {
    temperature?: number;
    max_tokens?: number;
    [key: string]: unknown;
  };
  api_keys: ApiKey[];
  created_at: string;
  updated_at: string;
}

interface ProviderConfigEditorProps {
  botId: string;
  currentConfig: ProviderConfig | null;
  onClose: () => void;
  onSave: () => void;
}

export function ProviderConfigEditor({
  botId,
  currentConfig,
  onClose,
  onSave,
}: ProviderConfigEditorProps) {
  const { t } = useLanguage();
  const toast = useToast();
  const { isRoot } = useCurrentUser();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showKeys, setShowKeys] = useState<boolean[]>([]);

  const [formData, setFormData] = useState({
    provider_id: "",
    model_id: "",
    api_keys: [{ key: "", name: "Primary", active: true }] as ApiKey[],
    config: {
      temperature: 0.7,
      max_tokens: 2000,
    },
  });

  const getPlainKeyStorageKey = (index: number) => `bot_${botId}_plain_key_${index}`;

  const savePlainKeyToStorage = (index: number, key: string) => {
    if (typeof window !== 'undefined' && key && key.trim()) {
      localStorage.setItem(getPlainKeyStorageKey(index), key);
    }
  };

  const getPlainKeyFromStorage = (index: number): string => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(getPlainKeyStorageKey(index)) || '';
    }
    return '';
  };

  const removePlainKeyFromStorage = (index: number) => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(getPlainKeyStorageKey(index));
    }
  };

  const clearAllPlainKeys = () => {
    if (typeof window !== 'undefined') {
      formData.api_keys.forEach((_, index) => {
        localStorage.removeItem(getPlainKeyStorageKey(index));
      });
    }
  };

  const fetchCurrentConfig = useCallback(async () => {
    try {
      const response = await apiClient.get<ProviderConfigResponse>(`/bots/${botId}/provider-config`);
      const config = response.data;
      setFormData({
        provider_id: config.provider_id || "",
        model_id: config.model_id || "",
        api_keys: config.api_keys.length > 0
          ? config.api_keys.map(k => ({
            key: k.key || "",
            name: k.name || "",
            active: k.active ?? true
          }))
          : [{ key: "", name: "Primary", active: true }],
        config: {
          temperature: config.config?.temperature ?? 0.7,
          max_tokens: config.config?.max_tokens ?? 2000,
        },
      });
      setShowKeys(config.api_keys.map(() => false));
    } catch (error) {
      console.error("Failed to fetch provider config:", error);
    }
  }, [botId]);

  const fetchProviders = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/providers/active");
      setProviders(response.data);
    } catch (error) {
      console.error("Failed to fetch providers:", error);
      toast.error(t("common.error"));
    } finally {
      setLoading(false);
    }
  }, [t, toast]);

  const fetchModels = useCallback(async (providerId: string) => {
    try {
      const response = await apiClient.get(`/providers/${providerId}/models/active`);
      setModels(response.data);
    } catch (error) {
      console.error("Failed to fetch models:", error);
      toast.error(t("common.error"));
    }
  }, [t, toast]);

  useEffect(() => {
    fetchProviders();
    if (currentConfig) {
      fetchCurrentConfig();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentConfig]);

  useEffect(() => {
    if (formData.provider_id) {
      fetchModels(formData.provider_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData.provider_id]);

  const handleAddApiKey = () => {
    setFormData({
      ...formData,
      api_keys: [...formData.api_keys, { key: "", name: `Key ${formData.api_keys.length + 1}`, active: true }],
    });
    setShowKeys([...showKeys, false]);
  };

  const handleRemoveApiKey = (index: number) => {
    removePlainKeyFromStorage(index);
    const newKeys = formData.api_keys.filter((_: ApiKey, i: number) => i !== index);
    setFormData({ ...formData, api_keys: newKeys });
    setShowKeys(showKeys.filter((_: boolean, i: number) => i !== index));
  };

  const handleApiKeyChange = (index: number, field: "key" | "name", value: string) => {
    const newKeys = [...formData.api_keys];
    if (field === "key") {
      newKeys[index].key = value;
      savePlainKeyToStorage(index, value);
    } else if (field === "name") {
      newKeys[index].name = value;
    }
    setFormData({ ...formData, api_keys: newKeys });
  };

  const toggleShowKey = async (index: number) => {
    const newShowKeys = [...showKeys];
    const currentKey = formData.api_keys[index].key;

    if (!newShowKeys[index]) {
      const plainKey = getPlainKeyFromStorage(index);

      if (plainKey && plainKey.trim()) {
        const newKeys = [...formData.api_keys];
        newKeys[index].key = plainKey;
        setFormData({ ...formData, api_keys: newKeys });
        newShowKeys[index] = true;
        setShowKeys(newShowKeys);
      } else if (currentKey && currentKey.startsWith("gAAAA")) {
        try {
          const response = await apiClient.post(`/bots/${botId}/reveal-api-key`, {
            encrypted_key: currentKey,
          });
          const decryptedKey = response.data.decrypted_key || "";

          if (decryptedKey) {
            const newKeys = [...formData.api_keys];
            newKeys[index].key = decryptedKey;
            setFormData({ ...formData, api_keys: newKeys });
            savePlainKeyToStorage(index, decryptedKey);
            newShowKeys[index] = true;
            setShowKeys(newShowKeys);
          } else {
            newShowKeys[index] = true;
            setShowKeys(newShowKeys);
          }
        } catch (error) {
          console.error("Failed to reveal API key:", error);
          toast.error(t("common.error"));
          newShowKeys[index] = true;
          setShowKeys(newShowKeys);
        }
      } else {
        newShowKeys[index] = true;
        setShowKeys(newShowKeys);
      }
    } else {
      newShowKeys[index] = false;
      setShowKeys(newShowKeys);
    }
  };

  const handleClose = () => {
    clearAllPlainKeys();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.provider_id || !formData.model_id) {
      toast.error("Please select provider and model");
      return;
    }

    if (formData.api_keys.length === 0 || !formData.api_keys[0].key) {
      toast.error("At least one API key is required");
      return;
    }

    try {
      setSaving(true);
      await apiClient.put(`/bots/${botId}`, {
        provider_config: formData,
      });

      toast.success("Provider configuration saved successfully");
      onSave();
      handleClose();
    } catch (error) {
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err.response?.data?.detail || t("common.error"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center z-50"
        style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      >
        <div className="bg-white rounded-lg p-8">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="fixed inset-0 bg-black flex items-center justify-center z-50 p-4"
        style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      >
        <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white">
            <h2 className="text-xl font-semibold text-gray-900">
              {t("bots.providerConfig.title")}
            </h2>
            <button
              onClick={handleClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            {/* Provider Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.providerConfig.provider")} *
              </label>
              <select
                value={formData.provider_id}
                onChange={(e) => {
                  setFormData({ ...formData, provider_id: e.target.value, model_id: "" });
                  setModels([]);
                }}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value="">{t("bots.providerConfig.selectProvider")}</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.providerConfig.model")} *
              </label>
              <select
                value={formData.model_id}
                onChange={(e) => setFormData({ ...formData, model_id: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                disabled={!formData.provider_id}
              >
                <option value="">{t("bots.providerConfig.selectModel")}</option>
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
            </div>

            {/* API Keys */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  {t("bots.providerConfig.apiKeys")} *
                </label>
                <button
                  type="button"
                  onClick={handleAddApiKey}
                  className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
                >
                  <Plus className="w-4 h-4" />
                  {t("bots.providerConfig.addKey")}
                </button>
              </div>

              <div className="space-y-3">
                {formData.api_keys.map((apiKey: ApiKey, index: number) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={apiKey.name}
                      onChange={(e) => handleApiKeyChange(index, "name", e.target.value)}
                      placeholder={t("bots.providerConfig.keyName")}
                      className="w-32 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <div className="flex-1 relative">
                      <input
                        type={showKeys[index] ? "text" : "password"}
                        value={apiKey.key}
                        onChange={(e) => handleApiKeyChange(index, "key", e.target.value)}
                        placeholder={t("bots.providerConfig.apiKeyPlaceholder")}
                        className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowKey(index)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-100 rounded"
                      >
                        {showKeys[index] ? (
                          <EyeOff className="w-4 h-4 text-gray-500" />
                        ) : (
                          <Eye className="w-4 h-4 text-gray-500" />
                        )}
                      </button>
                    </div>
                    {formData.api_keys.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveApiKey(index)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {t("bots.providerConfig.multipleKeysHint")}
              </p>
            </div>

            {/* Advanced Config - Only for Root */}
            {isRoot() && (
              <div className="border-t border-gray-200 pt-6">
                <h3 className="text-sm font-medium text-gray-900 mb-4">
                  {t("bots.providerConfig.advancedConfig")}
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {t("bots.providerConfig.temperature")}
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="2"
                      step="0.1"
                      value={formData.config.temperature}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setFormData({
                          ...formData,
                          config: { ...formData.config, temperature: isNaN(val) ? 0.7 : val }
                        });
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      {t("bots.providerConfig.temperatureHint")}
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {t("bots.providerConfig.maxTokens")}
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="32000"
                      step="1"
                      value={formData.config.max_tokens}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        setFormData({
                          ...formData,
                          config: { ...formData.config, max_tokens: isNaN(val) ? 2000 : val }
                        });
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      {t("bots.providerConfig.maxTokensHint")}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                disabled={saving}
              >
                {t("common.cancel")}
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={saving}
              >
                {saving ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    {t("common.saving")}
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    {t("common.save")}
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </>
  );
}
