"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { apiClient } from "@/lib/auth-api";
import { Plus, Edit, Trash2, CheckCircle, XCircle } from "lucide-react";
import { useToast } from "@/hooks/useToast";
import { ToastContainer } from "@/components/ui/Toast";
import { ModelFormModal } from "@/components/providers/ModelFormModal";
import { ProviderFormModal } from "@/components/providers/ProviderFormModal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useCurrentUser } from "@/hooks/useCurrentUser";

interface Provider {
  id: string;
  name: string;
  slug: string;
  api_base_url: string;
  auth_type: string;
  status: string;
  extra_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface Model {
  id: string;
  provider_id: string;
  name: string;
  model_type: string;
  context_window: number;
  pricing: number;
  is_active: boolean;
  extra_data: {
    cost_per_1k_input?: number;
    cost_per_1k_output?: number;
    currency?: string;
  };
  created_at: string;
  updated_at: string;
}

export default function ProvidersPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const toast = useToast();
  const { loading: userLoading, isRoot } = useCurrentUser();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [isProviderModalOpen, setIsProviderModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<Model | null>(null);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; modelId: string | null }>({
    isOpen: false,
    modelId: null,
  });

  useEffect(() => {
    if (!userLoading && !isRoot()) {
      router.push("/404");
    }
  }, [userLoading, isRoot, router]);

  const fetchProviders = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get<Provider[]>("/providers");
      setProviders(response.data);
    } catch (error) {
      console.error("Failed to fetch providers:", error);
      toast.error(t("common.error"));
    } finally {
      setLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    fetchProviders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchModels = async (providerId: string) => {
    try {
      const response = await apiClient.get<Model[]>(`/providers/${providerId}/models`);
      setModels(response.data);
    } catch (error) {
      console.error("Failed to fetch models:", error);
      toast.error(t("common.error"));
    }
  };

  const handleProviderClick = (provider: Provider) => {
    setSelectedProvider(provider);
    fetchModels(provider.id);
  };

  const handleEditProvider = (provider: Provider) => {
    setEditingProvider(provider);
    setIsProviderModalOpen(true);
  };

  const handleSubmitProvider = async (data: {
    name: string;
    api_base_url: string;
    auth_type: "api_key" | "bearer" | "otp";
    status: "active" | "inactive";
  }) => {
    if (!editingProvider) return;

    try {
      await apiClient.put(`/providers/${editingProvider.id}`, data);
      toast.success(t("common.success"));
      fetchProviders();
      setIsProviderModalOpen(false);
    } catch (error) {
      console.error("Failed to update provider:", error);
      toast.error(t("common.error"));
      throw error;
    }
  };

  const handleAddModel = () => {
    setEditingModel(null);
    setIsModelModalOpen(true);
  };

  const handleEditModel = (model: Model) => {
    setEditingModel(model);
    setIsModelModalOpen(true);
  };

  const handleDeleteModel = (modelId: string) => {
    setDeleteConfirm({ isOpen: true, modelId });
  };

  const confirmDelete = async () => {
    if (!deleteConfirm.modelId) return;

    try {
      await apiClient.delete(`/models/${deleteConfirm.modelId}`);
      toast.success(t("common.success"));
      if (selectedProvider) {
        fetchModels(selectedProvider.id);
      }
    } catch (error) {
      console.error("Failed to delete model:", error);
      toast.error(t("common.error"));
    } finally {
      setDeleteConfirm({ isOpen: false, modelId: null });
    }
  };

  const handleSubmitModel = async (data: {
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
  }) => {
    if (!selectedProvider) return;

    try {
      if (editingModel) {
        await apiClient.put(`/models/${editingModel.id}`, data);
      } else {
        await apiClient.post(`/providers/${selectedProvider.id}/models`, data);
      }
      toast.success(t("common.success"));
      fetchModels(selectedProvider.id);
      setIsModelModalOpen(false);
    } catch (error) {
      console.error("Failed to save model:", error);
      toast.error(t("common.error"));
      throw error;
    }
  };

  if (userLoading || loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!isRoot()) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t("providers.title")}</h1>
          <p className="text-gray-600 mt-1">{t("providers.description")}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Providers List */}
        <div className="lg:col-span-1 space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">{t("providers.providersList")}</h2>
          <div className="space-y-2">
            {providers.map((provider) => (
              <div
                key={provider.id}
                className={`relative p-4 pr-10 rounded-lg border transition-all ${
                  selectedProvider?.id === provider.id
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:border-gray-300 bg-white"
                }`}
              >
                <button
                  onClick={() => handleProviderClick(provider)}
                  className="w-full text-left"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-gray-900 truncate">{provider.name}</h3>
                      <p className="text-sm text-gray-500 truncate">{provider.slug}</p>
                    </div>
                    <div className="flex-shrink-0">
                      {provider.status === "active" ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <XCircle className="w-5 h-5 text-gray-400" />
                      )}
                    </div>
                  </div>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEditProvider(provider);
                  }}
                  className="absolute top-2 right-2 p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  title={t("common.edit")}
                >
                  <Edit className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Models List */}
        <div className="lg:col-span-2">
          {selectedProvider ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">
                  {t("providers.modelsFor")} {selectedProvider.name}
                </h2>
                <button
                  onClick={handleAddModel}
                  className="btn-outline flex items-center gap-2 text-sm"
                >
                  <Plus className="w-4 h-4" />
                  {t("providers.addModel")}
                </button>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t("providers.modelName")}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t("providers.contextWindow")}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t("providers.pricing")}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t("providers.status")}
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t("common.actions")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {models.map((model) => (
                      <tr key={model.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">{model.name}</div>
                          <div className="text-xs text-gray-500">{model.model_type}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {model.context_window.toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {model.extra_data.cost_per_1k_input && model.extra_data.cost_per_1k_output ? (
                            <div>
                              <div>In: ${model.extra_data.cost_per_1k_input}/1K</div>
                              <div>Out: ${model.extra_data.cost_per_1k_output}/1K</div>
                            </div>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`badge ${model.is_active ? "badge-success" : "badge-error"}`}>
                            {model.is_active ? t("common.active") : t("common.inactive")}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleEditModel(model)}
                              className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteModel(model.id)}
                              className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {models.length === 0 && (
                  <div className="text-center py-12 text-gray-500">
                    {t("providers.noModels")}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
              <p className="text-gray-500">{t("providers.selectProvider")}</p>
            </div>
          )}
        </div>
      </div>

      <ProviderFormModal
        isOpen={isProviderModalOpen}
        onClose={() => setIsProviderModalOpen(false)}
        onSubmit={handleSubmitProvider}
        initialData={editingProvider ? {
          ...editingProvider,
          auth_type: editingProvider.auth_type as "api_key" | "bearer" | "otp",
          status: editingProvider.status as "active" | "inactive"
        } : undefined}
        title={t("providers.editProvider")}
      />

      <ModelFormModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
        onSubmit={handleSubmitModel}
        initialData={editingModel ? {
          ...editingModel,
          model_type: editingModel.model_type as "chat" | "embedding",
          extra_data: {
            cost_per_1k_input: editingModel.extra_data.cost_per_1k_input || 0,
            cost_per_1k_output: editingModel.extra_data.cost_per_1k_output || 0,
            currency: editingModel.extra_data.currency || "USD"
          }
        } : undefined}
        title={editingModel ? t("providers.editModel") : t("providers.addModel")}
      />

      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        onClose={() => setDeleteConfirm({ isOpen: false, modelId: null })}
        onConfirm={confirmDelete}
        title={t("providers.deleteModelTitle")}
        message={t("providers.deleteModelMessage")}
      />

      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </div>
  );
}

