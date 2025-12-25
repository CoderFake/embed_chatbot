"use client";

import { useState, useEffect } from "react";
import { Modal } from "@/components/ui/Modal";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";

interface WorkerSettingsModalProps {
    botId: string;
    isOpen: boolean;
    onClose: () => void;
}

type Frequency = "DAILY" | "WEEKLY" | "MONTHLY" | "YEARLY";

interface Worker {
    id: string;
    bot_id: string;
    schedule_type: string;
    auto: boolean;
    schedule_time: string;
    frequency: Frequency;
}

export function WorkerSettingsModal({ botId, isOpen, onClose }: WorkerSettingsModalProps) {
    const { t } = useLanguage();
    const toast = useToast();

    const [saving, setSaving] = useState(false);

    // Form state
    const [gradingEnabled, setGradingEnabled] = useState(false);
    const [emailEnabled, setEmailEnabled] = useState(false);
    const [frequency, setFrequency] = useState<Frequency>("DAILY");
    const [gradingTime, setGradingTime] = useState("14:00");
    const [emailTime, setEmailTime] = useState("15:00");

    // Fetch existing worker settings
    useEffect(() => {
        if (isOpen && botId) {
            fetchWorkerSettings();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, botId]);

    const fetchWorkerSettings = async () => {
        try {
            const response = await apiClient.get(`/bots/${botId}/workers`);
            const workers: Worker[] = response.data.workers || [];

            const gradingWorker = workers.find((w) => w.schedule_type === "grading");
            const emailWorker = workers.find((w) => w.schedule_type === "visitor_email");

            if (gradingWorker) {
                setGradingEnabled(gradingWorker.auto);
                setGradingTime(gradingWorker.schedule_time.substring(0, 5));
                setFrequency(gradingWorker.frequency);
            }

            if (emailWorker) {
                setEmailEnabled(emailWorker.auto);
                setEmailTime(emailWorker.schedule_time.substring(0, 5));
            }
        } catch (error) {
            console.error("Failed to fetch worker settings:", error);
        }
    };

    const handleSave = async () => {
        try {
            setSaving(true);

            await apiClient.post(`/bots/${botId}/workers`, {
                schedule_type: "grading",
                auto: gradingEnabled,
                schedule_time: `${gradingTime}:00`,
                frequency: frequency.toLowerCase(), 
            });

            await apiClient.post(`/bots/${botId}/workers`, {
                schedule_type: "visitor_email",
                auto: emailEnabled && gradingEnabled,
                schedule_time: `${emailTime}:00`,
                frequency: frequency.toLowerCase(),
            });

            toast.success(t("workers.settingsSaved"));
            onClose();
        } catch (error) {
            console.error("Failed to save worker settings:", error);
            toast.error(t("common.error"));
        } finally {
            setSaving(false);
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title={t("workers.settingsModal")} size="lg">
            <div className="space-y-6">
                {/* Auto Assessment Toggle */}
                <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-900">
                            {t("workers.autoAssessment")}
                        </label>
                        <p className="text-xs text-gray-500 mt-1">
                            {t("workers.autoAssessmentDesc")}
                        </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                        <input
                            type="checkbox"
                            checked={gradingEnabled}
                            onChange={(e) => setGradingEnabled(e.target.checked)}
                            className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                </div>

                {/* Frequency Dropdown */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        {t("workers.frequency")}
                    </label>
                    <select
                        value={frequency}
                        onChange={(e) => setFrequency(e.target.value as Frequency)}
                        disabled={!gradingEnabled}
                        className="input-field w-full disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <option value="DAILY">{t("workers.frequencyDaily")}</option>
                        <option value="WEEKLY">{t("workers.frequencyWeekly")}</option>
                        <option value="MONTHLY">{t("workers.frequencyMonthly")}</option>
                        <option value="YEARLY">{t("workers.frequencyYearly")}</option>
                    </select>
                </div>

                {/* Assessment Time Picker */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        {t("workers.assessmentTime")}
                    </label>
                    <input
                        type="time"
                        value={gradingTime}
                        onChange={(e) => setGradingTime(e.target.value)}
                        disabled={!gradingEnabled}
                        className="input-field w-full disabled:opacity-50 disabled:cursor-not-allowed"
                    />
                </div>

                {/* Send Email Toggle */}
                <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-900">
                            {t("workers.sendEmail")}
                        </label>
                        <p className="text-xs text-gray-500 mt-1">
                            {t("workers.sendEmailDesc")}
                        </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                        <input
                            type="checkbox"
                            checked={emailEnabled}
                            onChange={(e) => setEmailEnabled(e.target.checked)}
                            disabled={!gradingEnabled}
                            className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"></div>
                    </label>
                </div>

                {/* Email Time Picker */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        {t("workers.emailTime")}
                    </label>
                    <input
                        type="time"
                        value={emailTime}
                        onChange={(e) => setEmailTime(e.target.value)}
                        disabled={!gradingEnabled || !emailEnabled}
                        className="input-field w-full disabled:opacity-50 disabled:cursor-not-allowed"
                    />
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
                    <button
                        onClick={onClose}
                        disabled={saving}
                        className="btn-secondary disabled:opacity-50"
                    >
                        {t("workers.cancel")}
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="btn-primary disabled:opacity-50"
                    >
                        {saving ? t("common.saving") : t("workers.save")}
                    </button>
                </div>
            </div>
        </Modal>
    );
}
