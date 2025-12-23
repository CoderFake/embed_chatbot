"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useLanguages } from "@/hooks/useLanguages";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { ToastContainer } from "@/components/ui/Toast";
import { BotActions } from "@/components/bots/BotActions";
import { DisplayConfigEditor } from "@/components/bots/DisplayConfigEditor";
import { ProviderConfigEditor } from "@/components/bots/ProviderConfigEditor";
import { ArrowLeft, Save, Palette, Settings, Plus, X } from "lucide-react";

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

interface DisplayConfig {
  header?: {
    title?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

interface Bot {
  id: string;
  name: string;
  bot_key: string;
  language: string | null;
  status: "active" | "inactive" | "draft";
  origin: string | null;
  collection_name: string;
  bucket_name: string;
  desc: string | null;
  assessment_questions: string[];
  provider_config: ProviderConfig | null;
  display_config: DisplayConfig;
  created_at: string;
  updated_at: string;
}

export default function BotDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { t } = useLanguage();
  const { languages, loading: languagesLoading } = useLanguages();
  const toast = useToast();
  const [bot, setBot] = useState<Bot | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showDisplayConfigEditor, setShowDisplayConfigEditor] = useState(false);
  const [showProviderConfigEditor, setShowProviderConfigEditor] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    language: "",
    status: "draft" as "active" | "inactive" | "draft",
    desc: "",
    assessment_questions: [] as string[],
  });
  const [questionInput, setQuestionInput] = useState("");

  const fetchBot = useCallback(async (id: string) => {
    try {
      setLoading(true);
      const response = await apiClient.get(`/bots/${id}`);
      setBot(response.data);
      setFormData({
        name: response.data.name,
        language: response.data.language || "",
        status: response.data.status,
        desc: response.data.desc || "",
        assessment_questions: response.data.assessment_questions || [],
      });
    } catch (error) {
      const err = error as { response?: { data?: { detail?: string } } };
      console.error("Failed to fetch bot:", error);
      toast.error(err.response?.data?.detail || t("common.error"));
      router.push("/dashboard/bots");
    } finally {
      setLoading(false);
    }
  }, [router, toast, t]);

  useEffect(() => {
    if (params.id) {
      fetchBot(params.id as string);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  const addAssessmentQuestion = () => {
    if (!questionInput.trim()) return;

    if (formData.assessment_questions.includes(questionInput)) {
      toast.error(t("bots.questionExists"));
      return;
    }

    setFormData({
      ...formData,
      assessment_questions: [...formData.assessment_questions, questionInput],
    });
    setQuestionInput("");
  };

  const removeAssessmentQuestion = (index: number) => {
    setFormData({
      ...formData,
      assessment_questions: formData.assessment_questions.filter((_, i) => i !== index),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!params.id) return;

    try {
      setSaving(true);

      const updateData: Partial<Bot> & { display_config?: DisplayConfig } = { ...formData };

      if (bot?.display_config && formData.name !== bot.name) {
        updateData.display_config = {
          ...bot.display_config,
          header: {
            ...bot.display_config.header,
            title: formData.name,
          },
        };
      }

      const response = await apiClient.put(`/bots/${params.id}`, updateData);

      setBot(response.data);

      await fetchBot(params.id as string);

      toast.success(t("bots.botUpdated"));
    } catch (error) {
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err.response?.data?.detail || t("common.error"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="card">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-1/4"></div>
            <div className="h-10 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded w-1/4"></div>
            <div className="h-10 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!bot) return null;

  if (showDisplayConfigEditor) {
    return (
      <DisplayConfigEditor
        botId={bot.id}
        botName={bot.name}
        onClose={() => setShowDisplayConfigEditor(false)}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push('/dashboard/bots')}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{t("bots.edit")}</h1>
            <p className="text-gray-600 mt-1">{bot.bot_key}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <BotActions
            botId={bot.id}
            botName={bot.name}
            status={bot.status}
            onStatusChange={() => fetchBot(params.id as string)}
          />
          <button
            onClick={() => setShowProviderConfigEditor(true)}
            className="btn-outline flex items-center gap-2"
          >
            <Settings className="w-4 h-4" />
            {t("bots.providerConfig.title")}
            {!bot.provider_config && (
              <span className="ml-1 px-2 py-0.5 text-xs bg-yellow-100 text-yellow-800 rounded">
                {t("bots.providerConfigRequired")}
              </span>
            )}
          </button>
          {bot.provider_config && (
            <button
              onClick={() => setShowDisplayConfigEditor(true)}
              className="btn-outline flex items-center gap-2"
            >
              <Palette className="w-4 h-4" />
              {t("bots.editDisplayConfig")}
            </button>
          )}
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("bots.basicInfo")}</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.name")}
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="input-field"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.desc")} ({t("common.optional")})
              </label>
              <textarea
                value={formData.desc}
                onChange={(e) => setFormData({ ...formData, desc: e.target.value })}
                className="input-field"
                rows={4}
                placeholder={t("bots.descPlaceholder")}
              />
              <p className="text-xs text-gray-500 mt-1">
                {t("bots.descHelper")}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.language")}
              </label>
              <select
                value={formData.language}
                onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                className="input-field"
                disabled={languagesLoading}
              >
                <option value="">{t("bots.selectLanguage")}</option>
                {languages.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.native_name} ({lang.name})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.status")}
              </label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as "active" | "inactive" | "draft" })}
                className="input-field"
              >
                <option value="draft">{t("bots.draft")}</option>
                <option value="active">{t("bots.active")}</option>
                <option value="inactive">{t("bots.inactive")}</option>
              </select>
            </div>
          </div>
        </div>

        {/* Assessment Questions */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            {t("bots.assessmentQuestions")} ({t("common.optional")})
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            {t("bots.assessmentQuestionsHelper")}
          </p>

          {/* Add Question Input */}
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={questionInput}
              onChange={(e) => setQuestionInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && (e.preventDefault(), addAssessmentQuestion())}
              className="input-field"
              placeholder={t("bots.questionPlaceholder")}
            />
            <button
              type="button"
              onClick={addAssessmentQuestion}
              className="btn-primary flex items-center gap-2 whitespace-nowrap"
            >
              <Plus className="w-4 h-4" />
              {t("bots.addQuestion")}
            </button>
          </div>

          {/* Question List */}
          {formData.assessment_questions.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">
                {formData.assessment_questions.length} {t("bots.questionsCount")}
              </p>
              <div className="max-h-60 overflow-y-auto space-y-2">
                {formData.assessment_questions.map((question, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-2 p-3 bg-gray-50 rounded-lg"
                  >
                    <span className="flex-shrink-0 w-6 h-6 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-xs font-medium">
                      {index + 1}
                    </span>
                    <span className="flex-1 text-sm text-gray-700">{question}</span>
                    <button
                      type="button"
                      onClick={() => removeAssessmentQuestion(index)}
                      className="text-red-600 hover:text-red-700 p-1"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Meta Info */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("bots.systemInfo")}</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">{t("bots.collection")}:</span>
              <span className="ml-2 text-gray-900">{bot.collection_name}</span>
            </div>
            <div>
              <span className="text-gray-600">{t("bots.bucket")}:</span>
              <span className="ml-2 text-gray-900">{bot.bucket_name}</span>
            </div>
            <div>
              <span className="text-gray-600">{t("bots.created")}:</span>
              <span className="ml-2 text-gray-900">
                {new Date(bot.created_at).toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-gray-600">{t("bots.updated")}:</span>
              <span className="ml-2 text-gray-900">
                {new Date(bot.updated_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => router.push('/dashboard/bots')}
            className="btn-outline"
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            disabled={saving}
            className="btn-primary flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {saving ? t("common.loading") : t("common.save")}
          </button>
        </div>
      </form>

      {/* Provider Config Editor Modal */}
      {showProviderConfigEditor && (
        <ProviderConfigEditor
          botId={bot.id}
          currentConfig={bot.provider_config}
          onClose={() => setShowProviderConfigEditor(false)}
          onSave={() => {
            fetchBot(params.id as string);
          }}
        />
      )}

      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </div>
  );
}
