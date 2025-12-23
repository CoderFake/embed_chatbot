"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { ArrowLeft, Save, Play } from "lucide-react";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { ToastContainer } from "@/components/ui/Toast";
import { CollapsibleSection } from "./CollapsibleSection";
import { ColorPickerGroup } from "./ColorPickerGroup";
import { ImageUpload } from "./ImageUpload";
import { apiClient } from "@/lib/auth-api";

interface DisplayConfigEditorProps {
  botId: string;
  botName: string;
  onClose: () => void;
}

interface DisplayConfig {
  position?: Record<string, unknown>;
  size?: Record<string, unknown>;
  colors?: Record<string, unknown>;
  button?: Record<string, unknown>;
  header?: Record<string, unknown>;
  welcome_message?: Record<string, unknown>;
  input?: Record<string, unknown>;
  behavior?: Record<string, unknown>;
  branding?: Record<string, unknown>;
  custom_css?: string;
  language?: string;
  timezone?: string;
}

export function DisplayConfigEditor({ botId, botName, onClose }: DisplayConfigEditorProps) {
  const { t } = useLanguage();
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [previewPosition, setPreviewPosition] = useState<"left" | "right">("right");
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [liveReloadKey, setLiveReloadKey] = useState(0);
  const [iframeKey, setIframeKey] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const liveContainerRef = useRef<HTMLDivElement>(null);
  const updateTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  // File uploads
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);

  const [config, setConfig] = useState<DisplayConfig>({
    position: { horizontal: "right", vertical: "bottom", offset_x: 20, offset_y: 20 },
    size: { width: 400, height: 600, mobile_width: 360, mobile_height: 500 },
    colors: {
      header: { background: "#4F46E5", text: "#FFFFFF", subtitle_text: "#E0E7FF", icon: "#FFFFFF", border: "#4338CA" },
      background: { main: "#FFFFFF", chat_area: "#F9FAFB", message_container: "#FFFFFF" },
      message: {
        user_background: "#4F46E5",
        user_text: "#FFFFFF",
        bot_background: "#F3F4F6",
        bot_text: "#1F2937",
        timestamp: "#6B7280",
        link: "#4F46E5",
        code_background: "#1F2937",
        code_text: "#F9FAFB",
      },
      input: {
        background: "#FFFFFF",
        text: "#1F2937",
        placeholder: "#9CA3AF",
        border: "#E5E7EB",
        border_focus: "#4F46E5",
        icon: "#6B7280",
      },
      button: {
        primary_background: "#4F46E5",
        primary_text: "#FFFFFF",
        primary_hover: "#4338CA",
        secondary_background: "#F3F4F6",
        secondary_text: "#1F2937",
        secondary_hover: "#E5E7EB",
        launcher_background: "#4F46E5",
        launcher_icon: "#FFFFFF",
        send_button: "#4F46E5",
        send_button_disabled: "#D1D5DB",
      },
      scrollbar: { thumb: "#D1D5DB", thumb_hover: "#9CA3AF", track: "#F3F4F6" },
      error: "#EF4444",
      success: "#10B981",
      warning: "#F59E0B",
      info: "#3B82F6",
      divider: "#E5E7EB",
      shadow: "rgba(0, 0, 0, 0.1)",
    },
    button: { icon: null, text: null, size: 60, show_notification_badge: true },
    header: { title: botName, subtitle: "Online", avatar_url: null, show_online_status: true, show_close_button: true },
    welcome_message: { enabled: true, message: "Hi! How can I help you today?", quick_replies: [] },
    input: {
      placeholder: "Type your message...",
      max_length: 1000,
      enable_file_upload: false,
      allowed_file_types: [".pdf", ".txt", ".doc", ".docx"],
      max_file_size_mb: 10,
      show_emoji_picker: true,
    },
    behavior: {
      auto_open: false,
      auto_open_delay: 3,
      minimize_on_outside_click: true,
      show_typing_indicator: true,
      enable_sound: true,
      persist_conversation: true,
    },
    branding: {
      show_powered_by: true,
      company_name: null,
      company_logo_url: null,
      privacy_policy_url: null,
      terms_url: null,
    },
    custom_css: "",
    language: "en",
    timezone: "UTC",
  });

  const [sections, setSections] = useState<Record<string, boolean>>({
    position: true,
    size: false,
    colors: true,
    button: false,
    header: false,
    welcome: false,
    input: false,
    behavior: false,
    branding: false,
    advanced: false,
  });

  const fetchConfig = useCallback(async () => {
    try {
      const response = await apiClient.get(`/bots/${botId}/display-config`);
      if (response.data) {
        setConfig((prev) => ({ ...prev, ...response.data }));
      }
    } catch (error) {
      console.error("Failed to fetch config:", error);
    }
  }, [botId]);

  useEffect(() => {
    fetchConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId]);

  const updatePreview = useCallback(() => {
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }

    updateTimeoutRef.current = setTimeout(() => {
      if (iframeRef.current?.contentWindow) {
        iframeRef.current.contentWindow.postMessage(
          {
            type: "UPDATE_CONFIG",
            config,
          },
          "*"
        );
      }
    }, 300);
  }, [config]);

  useEffect(() => {
    updatePreview();
  }, [config, updatePreview]);

  useEffect(() => {
    if (!isLiveMode && iframeRef.current) {
      const iframe = iframeRef.current;
      const sendConfigToIframe = () => {
        if (iframe.contentWindow) {
          iframe.contentWindow.postMessage(
            {
              type: "UPDATE_CONFIG",
              config,
            },
            "*"
          );
        }
      };

      iframe.addEventListener('load', sendConfigToIframe);

      if (iframe.contentDocument?.readyState === 'complete') {
        setTimeout(sendConfigToIframe, 100);
      }

      return () => {
        iframe.removeEventListener('load', sendConfigToIframe);
      };
    }
  }, [config, isLiveMode, iframeKey]);

  useEffect(() => {
    if (isLiveMode) {
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:18000';
      const script = document.createElement('script');
      script.defer = true;
      script.src = `${backendUrl}/widget/js`;
      script.setAttribute('data-bot-id', botId);
      script.id = `live-widget-script-${liveReloadKey}`;

      document.body.appendChild(script);

      return () => {
        const scriptEl = document.getElementById(`live-widget-script-${liveReloadKey}`);
        if (scriptEl) {
          scriptEl.remove();
        }

        // Remove widget container elements
        const widgetElements = document.querySelectorAll('[data-widget-container], [id*="chatbot"]');
        widgetElements.forEach(el => el.remove());
      };
    }
  }, [isLiveMode, botId, liveReloadKey]);

  const updateConfig = (path: string[], value: unknown) => {
    setConfig((prev) => {
      const newConfig = JSON.parse(JSON.stringify(prev));
      let current = newConfig;
      for (let i = 0; i < path.length - 1; i++) {
        if (!current[path[i]]) current[path[i]] = {};
        current = current[path[i]];
      }
      current[path[path.length - 1]] = value;
      return newConfig;
    });
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("config", JSON.stringify(config));

      // Append files if selected
      if (avatarFile) {
        formData.append("avatar", avatarFile);
      }
      if (logoFile) {
        formData.append("logo", logoFile);
      }

      await apiClient.put(`/bots/${botId}/display-config`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      toast.success(t("common.success"));

      if (isLiveMode) {
        setLiveReloadKey(prev => prev + 1);
      }
    } catch (error) {
      console.error("Save error:", error);
      toast.error(t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (section: string) => {
    setSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className="fixed inset-0 bg-white z-50 flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between bg-white">
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{t("bots.editDisplayConfig")}</h1>
            <p className="text-sm text-gray-600">{botName}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              const newLiveMode = !isLiveMode;
              setIsLiveMode(newLiveMode);
              if (newLiveMode) {
                setLiveReloadKey(prev => prev + 1);
              } else {
                setIframeKey(prev => prev + 1);
              }
            }}
            className={`btn-outline flex items-center gap-2 ${isLiveMode ? 'bg-green-50 border-green-500 text-green-700' : ''}`}
          >
            <Play className="w-4 h-4" />
            {isLiveMode ? "Live Mode (Production)" : "Preview Mode"}
          </button>
          <button onClick={() => setPreviewPosition(previewPosition === "left" ? "right" : "left")} className="btn-outline">
            {t("bots.switchPreview")}
          </button>
          <button onClick={handleSave} disabled={loading} className="btn-primary flex items-center gap-2">
            <Save className="w-4 h-4" />
            {loading ? t("common.saving") : t("common.save")}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className={`flex-1 flex ${previewPosition === "left" ? "flex-row-reverse" : "flex-row"} overflow-hidden`}>
        {/* Config Form - 2/3 */}
        <div className="w-2/3 overflow-y-auto p-6 space-y-6" style={{ scrollBehavior: "auto" }}>
          {/* Position Section */}
          <CollapsibleSection title={t("bots.positionSettings")} isOpen={sections.position} onToggle={() => toggleSection("position")}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.horizontal")}</label>
                <select
                  defaultValue={(config.position?.horizontal as string) || "right"}
                  onBlur={(e) => updateConfig(["position", "horizontal"], e.target.value)}
                  className="input-field"
                >
                  <option value="left">{t("bots.left")}</option>
                  <option value="right">{t("bots.right")}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.vertical")}</label>
                <select
                  defaultValue={(config.position?.vertical as string) || "bottom"}
                  onBlur={(e) => updateConfig(["position", "vertical"], e.target.value)}
                  className="input-field"
                >
                  <option value="top">{t("bots.top")}</option>
                  <option value="bottom">{t("bots.bottom")}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.offsetX")} (px)</label>
                <input
                  type="number"
                  defaultValue={(config.position?.offset_x as number) || 20}
                  onBlur={(e) => updateConfig(["position", "offset_x"], parseInt(e.target.value))}
                  className="input-field"
                  min="0"
                  max="200"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.offsetY")} (px)</label>
                <input
                  type="number"
                  defaultValue={(config.position?.offset_y as number) || 20}
                  onBlur={(e) => updateConfig(["position", "offset_y"], parseInt(e.target.value))}
                  className="input-field"
                  min="0"
                  max="200"
                />
              </div>
            </div>
          </CollapsibleSection>

          {/* Size Section */}
          <CollapsibleSection title={t("bots.sizeSettings")} isOpen={sections.size} onToggle={() => toggleSection("size")}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.width")} (px)</label>
                <input
                  type="number"
                  defaultValue={(config.size?.width as number) || 400}
                  onBlur={(e) => updateConfig(["size", "width"], parseInt(e.target.value))}
                  className="input-field"
                  min="300"
                  max="800"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.height")} (px)</label>
                <input
                  type="number"
                  defaultValue={(config.size?.height as number) || 600}
                  onBlur={(e) => updateConfig(["size", "height"], parseInt(e.target.value))}
                  className="input-field"
                  min="400"
                  max="900"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.mobileWidth")} (px)</label>
                <input
                  type="number"
                  defaultValue={(config.size?.mobile_width as number) || 360}
                  onBlur={(e) => updateConfig(["size", "mobile_width"], parseInt(e.target.value))}
                  className="input-field"
                  min="280"
                  max="500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.mobileHeight")} (px)</label>
                <input
                  type="number"
                  defaultValue={(config.size?.mobile_height as number) || 500}
                  onBlur={(e) => updateConfig(["size", "mobile_height"], parseInt(e.target.value))}
                  className="input-field"
                  min="400"
                  max="700"
                />
              </div>
            </div>
          </CollapsibleSection>

          {/* Colors Section */}
          <CollapsibleSection title={t("bots.colorSettings")} isOpen={sections.colors} onToggle={() => toggleSection("colors")}>
            <div className="space-y-6">
              <ColorPickerGroup
                title={t("bots.headerColors")}
                items={[
                  { key: "background", label: t("bots.background"), default: "#4F46E5" },
                  { key: "text", label: t("bots.textColor"), default: "#FFFFFF" },
                  { key: "subtitle_text", label: t("bots.subtitleText"), default: "#E0E7FF" },
                  { key: "icon", label: t("bots.iconColor"), default: "#FFFFFF" },
                  { key: "border", label: t("bots.borderColor"), default: "#4338CA" },
                ]}
                values={(config.colors?.header as Record<string, string>) || {}}
                onChange={(key, value) => updateConfig(["colors", "header", key], value)}
              />
              <ColorPickerGroup
                title={t("bots.buttonColors")}
                items={[
                  { key: "launcher_background", label: t("bots.launcherBg"), default: "#4F46E5" },
                  { key: "launcher_icon", label: t("bots.launcherIcon"), default: "#FFFFFF" },
                  { key: "send_button", label: t("bots.sendButton"), default: "#4F46E5" },
                  { key: "send_button_disabled", label: t("bots.sendButtonDisabled"), default: "#D1D5DB" },
                  { key: "primary_background", label: t("bots.primaryBg"), default: "#4F46E5" },
                  { key: "primary_text", label: t("bots.primaryText"), default: "#FFFFFF" },
                ]}
                values={(config.colors?.button as Record<string, string>) || {}}
                onChange={(key, value) => updateConfig(["colors", "button", key], value)}
              />
              <ColorPickerGroup
                title={t("bots.messageColors")}
                items={[
                  { key: "user_background", label: t("bots.userMessageBg"), default: "#4F46E5" },
                  { key: "user_text", label: t("bots.userMessageText"), default: "#FFFFFF" },
                  { key: "bot_background", label: t("bots.botMessageBg"), default: "#F3F4F6" },
                  { key: "bot_text", label: t("bots.botMessageText"), default: "#1F2937" },
                  { key: "timestamp", label: t("bots.timestampColor"), default: "#6B7280" },
                  { key: "link", label: t("bots.linkColor"), default: "#4F46E5" },
                ]}
                values={(config.colors?.message as Record<string, string>) || {}}
                onChange={(key, value) => updateConfig(["colors", "message", key], value)}
              />
              <ColorPickerGroup
                title={t("bots.inputColors")}
                items={[
                  { key: "background", label: t("bots.background"), default: "#FFFFFF" },
                  { key: "text", label: t("bots.textColor"), default: "#1F2937" },
                  { key: "placeholder", label: t("bots.placeholderColor"), default: "#9CA3AF" },
                  { key: "border", label: t("bots.borderColor"), default: "#E5E7EB" },
                  { key: "border_focus", label: t("bots.borderFocusColor"), default: "#4F46E5" },
                  { key: "icon", label: t("bots.iconColor"), default: "#6B7280" },
                ]}
                values={(config.colors?.input as Record<string, string>) || {}}
                onChange={(key, value) => updateConfig(["colors", "input", key], value)}
              />
              <ColorPickerGroup
                title={t("bots.backgroundColors")}
                items={[
                  { key: "main", label: t("bots.mainBackground"), default: "#FFFFFF" },
                  { key: "chat_area", label: t("bots.chatArea"), default: "#F9FAFB" },
                  { key: "message_container", label: t("bots.messageContainer"), default: "#FFFFFF" },
                ]}
                values={(config.colors?.background as Record<string, string>) || {}}
                onChange={(key, value) => updateConfig(["colors", "background", key], value)}
              />
            </div>
          </CollapsibleSection>

          {/* Button Section */}
          <CollapsibleSection title={t("bots.buttonSettings")} isOpen={sections.button} onToggle={() => toggleSection("button")}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.buttonSize")} (px)</label>
                <input
                  type="number"
                  defaultValue={(config.button?.size as number) || 60}
                  onBlur={(e) => updateConfig(["button", "size"], parseInt(e.target.value))}
                  className="input-field"
                  min="40"
                  max="100"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.button?.show_notification_badge !== false}
                  onChange={(e) => updateConfig(["button", "show_notification_badge"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.showNotificationBadge")}</label>
              </div>
            </div>
          </CollapsibleSection>

          {/* Header Section */}
          <CollapsibleSection title={t("bots.headerSettings")} isOpen={sections.header} onToggle={() => toggleSection("header")}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.widgetTitle")}</label>
                <input
                  type="text"
                  defaultValue={(config.header?.title as string) || botName}
                  onBlur={(e) => updateConfig(["header", "title"], e.target.value)}
                  className="input-field"
                  maxLength={100}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.widgetSubtitle")}</label>
                <input
                  type="text"
                  defaultValue={(config.header?.subtitle as string) || ""}
                  onBlur={(e) => updateConfig(["header", "subtitle"], e.target.value)}
                  className="input-field"
                  maxLength={200}
                />
              </div>
              <ImageUpload
                label={t("bots.avatarImage")}
                value={(config.header?.avatar_url as string) || ""}
                onChange={(file, previewUrl) => {
                  if (file) {
                    setAvatarFile(file);
                    if (previewUrl) {
                      updateConfig(["header", "avatar_url"], previewUrl);
                    }
                  } else {
                    setAvatarFile(null);
                    updateConfig(["header", "avatar_url"], "");
                  }
                }}
              />
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.header?.show_online_status !== false}
                  onChange={(e) => updateConfig(["header", "show_online_status"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.showOnlineStatus")}</label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.header?.show_close_button !== false}
                  onChange={(e) => updateConfig(["header", "show_close_button"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.showCloseButton")}</label>
              </div>
            </div>
          </CollapsibleSection>

          {/* Welcome Message Section */}
          <CollapsibleSection title={t("bots.welcomeMessage")} isOpen={sections.welcome} onToggle={() => toggleSection("welcome")}>
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.welcome_message?.enabled !== false}
                  onChange={(e) => updateConfig(["welcome_message", "enabled"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.enableWelcomeMessage")}</label>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.message")}</label>
                <textarea
                  defaultValue={(config.welcome_message?.message as string) || "Hi! How can I help you today?"}
                  onBlur={(e) => updateConfig(["welcome_message", "message"], e.target.value)}
                  className="input-field"
                  rows={3}
                  maxLength={500}
                />
              </div>
            </div>
          </CollapsibleSection>

          {/* Input Section */}
          <CollapsibleSection title={t("bots.inputSettings")} isOpen={sections.input} onToggle={() => toggleSection("input")}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.placeholder")}</label>
                <input
                  type="text"
                  defaultValue={(config.input?.placeholder as string) || "Type your message..."}
                  onBlur={(e) => updateConfig(["input", "placeholder"], e.target.value)}
                  className="input-field"
                  maxLength={100}
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.input?.enable_file_upload === true}
                  onChange={(e) => updateConfig(["input", "enable_file_upload"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.enableFileUpload")}</label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.input?.show_emoji_picker !== false}
                  onChange={(e) => updateConfig(["input", "show_emoji_picker"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.showEmojiPicker")}</label>
              </div>
            </div>
          </CollapsibleSection>

          {/* Behavior Section */}
          <CollapsibleSection title={t("bots.behaviorSettings")} isOpen={sections.behavior} onToggle={() => toggleSection("behavior")}>
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.behavior?.auto_open === true}
                  onChange={(e) => updateConfig(["behavior", "auto_open"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.autoOpen")}</label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.behavior?.minimize_on_outside_click !== false}
                  onChange={(e) => updateConfig(["behavior", "minimize_on_outside_click"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.minimizeOnOutsideClick")}</label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.behavior?.show_typing_indicator !== false}
                  onChange={(e) => updateConfig(["behavior", "show_typing_indicator"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.showTypingIndicator")}</label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.behavior?.enable_sound !== false}
                  onChange={(e) => updateConfig(["behavior", "enable_sound"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.enableSound")}</label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.behavior?.persist_conversation !== false}
                  onChange={(e) => updateConfig(["behavior", "persist_conversation"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.persistConversation")}</label>
              </div>
            </div>
          </CollapsibleSection>

          {/* Branding Section */}
          <CollapsibleSection title={t("bots.brandingSettings")} isOpen={sections.branding} onToggle={() => toggleSection("branding")}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.companyName")}</label>
                <input
                  type="text"
                  defaultValue={(config.branding?.company_name as string) || ""}
                  onBlur={(e) => updateConfig(["branding", "company_name"], e.target.value)}
                  className="input-field"
                  maxLength={100}
                />
              </div>
              <ImageUpload
                label={t("bots.companyLogo")}
                value={(config.branding?.company_logo_url as string) || ""}
                onChange={(file, previewUrl) => {
                  if (file) {
                    setLogoFile(file);
                    if (previewUrl) {
                      updateConfig(["branding", "company_logo_url"], previewUrl);
                    }
                  } else {
                    setLogoFile(null);
                    updateConfig(["branding", "company_logo_url"], "");
                  }
                }}
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.privacyPolicyUrl")}</label>
                <input
                  type="url"
                  defaultValue={(config.branding?.privacy_policy_url as string) || ""}
                  onBlur={(e) => updateConfig(["branding", "privacy_policy_url"], e.target.value)}
                  className="input-field"
                  placeholder="https://example.com/privacy"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.termsUrl")}</label>
                <input
                  type="url"
                  defaultValue={(config.branding?.terms_url as string) || ""}
                  onBlur={(e) => updateConfig(["branding", "terms_url"], e.target.value)}
                  className="input-field"
                  placeholder="https://example.com/terms"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  defaultChecked={config.branding?.show_powered_by !== false}
                  onChange={(e) => updateConfig(["branding", "show_powered_by"], e.target.checked)}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">{t("bots.showPoweredBy")}</label>
              </div>
            </div>
          </CollapsibleSection>

          {/* Advanced Section */}
          <CollapsibleSection title={t("bots.advancedSettings")} isOpen={sections.advanced} onToggle={() => toggleSection("advanced")}>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t("bots.customCSS")}</label>
                <textarea
                  defaultValue={(config.custom_css as string) || ""}
                  onBlur={(e) => updateConfig(["custom_css"], e.target.value)}
                  className="input-field font-mono text-sm"
                  rows={6}
                  maxLength={5000}
                  placeholder="/* Custom CSS */"
                />
              </div>
            </div>
          </CollapsibleSection>
        </div>

        {/* Preview - 1/3 */}
        <div className="w-1/3 border-l border-gray-200 bg-gray-50 p-6">
          {isLiveMode ? (
            <div className="w-full h-full" ref={liveContainerRef}></div>
          ) : (
            <iframe
              key={iframeKey}
              ref={iframeRef}
              src="/widget-preview.html"
              className="w-full h-full border-0"
            />
          )}
        </div>
      </div>

      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </div>
  );
}

