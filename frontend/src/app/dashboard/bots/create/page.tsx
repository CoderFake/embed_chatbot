"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useLanguages } from "@/hooks/useLanguages";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/error-utils";
import { ToastContainer } from "@/components/ui/Toast";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { ArrowLeft, Plus, X } from "lucide-react";


export default function CreateBotPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const { languages, loading: languagesLoading } = useLanguages();
  const toast = useToast();

  const [formData, setFormData] = useState({
    name: "",
    origin: "",
    language: "",
    desc: "",
    assessment_questions: [] as string[],
    sitemapUrls: [] as string[],
  });
  const [urlInput, setUrlInput] = useState("");
  const [questionInput, setQuestionInput] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const addSitemapUrl = () => {
    if (!urlInput.trim()) return;
    
    if (!urlInput.startsWith("http://") && !urlInput.startsWith("https://")) {
      toast.error("URL must start with http:// or https://");
      return;
    }

    if (formData.sitemapUrls.length >= 100) {
      toast.error("Maximum 100 URLs allowed");
      return;
    }

    if (formData.sitemapUrls.includes(urlInput)) {
      toast.error("URL already added");
      return;
    }

    setFormData({
      ...formData,
      sitemapUrls: [...formData.sitemapUrls, urlInput],
    });
    setUrlInput("");
  };

  const removeSitemapUrl = (index: number) => {
    setFormData({
      ...formData,
      sitemapUrls: formData.sitemapUrls.filter((_, i) => i !== index),
    });
  };

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
    
    if (!formData.name.trim()) {
      toast.error(t("common.requiredField"));
      return;
    }

    if (!formData.origin.trim()) {
      toast.error(t("common.requiredField"));
      return;
    }

    setSubmitting(true);

    try {
      const response = await apiClient.post("/bots", {
        name: formData.name,
        origin: formData.origin,
        language: formData.language || null,
        desc: formData.desc || null,
        assessment_questions: formData.assessment_questions,
        sitemap_urls: formData.sitemapUrls,
      });

      const data = response.data;

      toast.success(t("bots.botCreated"));
      router.push(`/dashboard/bots/${data.bot.id}`);

    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />

      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t("bots.create")}</h1>
          <p className="text-gray-600 mt-1">{t("bots.manageBots")}</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t("bots.basicInfo")}
          </h2>

          <div className="space-y-4">
            {/* Bot Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.name")} *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="input-field"
                required
                placeholder="My Support Bot"
              />
            </div>

            {/* Origin */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.origin")} *
              </label>
              <input
                type="url"
                value={formData.origin}
                onChange={(e) => setFormData({ ...formData, origin: e.target.value })}
                className="input-field"
                required
                placeholder={t("bots.originPlaceholder")}
              />
              <p className="text-xs text-gray-500 mt-1">{t("bots.originHelper")}</p>
            </div>

            {/* Language */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("bots.language")} ({t("common.optional")})
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

            {/* Description */}
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

        {/* Sitemap URLs */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            {t("bots.sitemapUrls")} ({t("common.optional")})
          </h2>
          <p className="text-sm text-gray-600 mb-4">{t("bots.sitemapHelper")}</p>

          {/* Add URL Input */}
          <div className="flex gap-2 mb-4">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && (e.preventDefault(), addSitemapUrl())}
              className="input-field"
              placeholder={t("bots.sitemapUrlPlaceholder")}
            />
            <button
              type="button"
              onClick={addSitemapUrl}
              className="btn-primary flex items-center gap-2 whitespace-nowrap"
            >
              <Plus className="w-4 h-4" />
              {t("bots.addSitemapUrl")}
            </button>
          </div>

          {/* URL List */}
          {formData.sitemapUrls.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">
                {formData.sitemapUrls.length} / 100 URLs
              </p>
              <div className="max-h-60 overflow-y-auto space-y-2">
                {formData.sitemapUrls.map((url, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg"
                  >
                    <span className="flex-1 text-sm text-gray-700 truncate">{url}</span>
                    <button
                      type="button"
                      onClick={() => removeSitemapUrl(index)}
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

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="btn-outline"
            disabled={submitting}
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            className="btn-primary flex items-center gap-2"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <LoadingSpinner size="sm" />
                {t("common.loading")}
              </>
            ) : (
              t("common.create")
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

