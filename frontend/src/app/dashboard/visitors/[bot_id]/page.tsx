"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { ToastContainer } from "@/components/ui/Toast";
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  MapPin,
  Award,
  MessageSquare,
  ClipboardCheck,
  X,
  Clock,
  CheckCircle2,
  AlertCircle,
  Settings,
} from "lucide-react";
import { WorkerSettingsModal } from "@/components/visitors/WorkerSettingsModal";

interface Visitor {
  id: string;
  bot_id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  lead_score: number;
  lead_assessment: {
    assessment?: {
      results?: AssessmentResult[];
      summary?: string;
      assessed_at?: string;
    };
  } | null;
  is_new: boolean;
  created_at: string;
}

interface AssessmentResult {
  question: string;
  answer: string;
  confidence: number;
  relevant_messages: Array<{ role: string; content: string }>;
}

interface Bot {
  id: string;
  name: string;
  bot_key: string;
  assessment_questions: string[];
}

interface ChatMessage {
  id: string;
  query: string;
  response: string;
  created_at: string;
}

interface ChatSession {
  id: string;
  session_token: string;
  created_at: string;
  closed_at: string | null;
  messages: ChatMessage[];
}

interface AssessmentProgress {
  progress: number;
  status: string;
  message: string;
}

export default function BotVisitorsPage() {
  const params = useParams();
  const router = useRouter();
  const { t } = useLanguage();
  const toast = useToast();
  const botId = params.bot_id as string;

  const [bot, setBot] = useState<Bot | null>(null);
  const [visitors, setVisitors] = useState<Visitor[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedVisitor, setSelectedVisitor] = useState<Visitor | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [loadingChat, setLoadingChat] = useState(false);
  const [showChatModal, setShowChatModal] = useState(false);
  const [showAssessmentModal, setShowAssessmentModal] = useState(false);
  const [showWorkerSettings, setShowWorkerSettings] = useState(false);
  const [loadingWorkerSettings, setLoadingWorkerSettings] = useState(false);
  const [assessmentStates, setAssessmentStates] = useState<Map<string, AssessmentProgress>>(new Map());

  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map());

  // Pagination & Sorting
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [sortBy, setSortBy] = useState("assessed_at");

  const hasFetchedBot = useRef(false);

  useEffect(() => {
    if (!botId || hasFetchedBot.current) return;
    hasFetchedBot.current = true;

    const fetchBot = async () => {
      try {
        const response = await apiClient.get(`/bots/${botId}`);
        setBot(response.data);
      } catch (error) {
        console.error("Failed to fetch bot:", error);
        toast.error(t("common.error"));
        router.push("/dashboard/visitors");
      }
    };

    fetchBot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId]);

  useEffect(() => {
    if (botId) {
      fetchVisitors();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId, page, sortBy]);

  useEffect(() => {
    if (!botId) return;
    fetchVisitors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId]);

  useEffect(() => {
    if (!visitors || visitors.length === 0) return;

    const fetchActiveAssessments = async () => {
      try {
        const response = await apiClient.get('/admin/visitors/active-assessments/bulk');
        const activeAssessments = response.data;
        Object.entries(activeAssessments).forEach(([visitorId, taskId]) => {
          const visitor = visitors.find(v => v.id === visitorId);
          if (!visitor) return;

          setAssessmentStates(prev => new Map(prev).set(visitorId, {
            progress: 50,
            status: "IN_PROGRESS",
            message: t("analytics.assessmentInProgress")
          }));

          const token = localStorage.getItem("access_token");
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
          const eventSource = new EventSource(
            `${apiUrl}/admin/assessment/${taskId}/progress?token=${token}`
          );

          eventSourcesRef.current.set(visitorId, eventSource);

          eventSource.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              setAssessmentStates(prev => new Map(prev).set(visitorId, data));

              if (data.status === "COMPLETED") {
                toast.success(t("analytics.assessmentComplete"));
                eventSource.close();
                eventSourcesRef.current.delete(visitorId);
                setAssessmentStates(prev => {
                  const newMap = new Map(prev);
                  newMap.delete(visitorId);
                  return newMap;
                });
                fetchVisitors();
              } else if (data.status === "FAILED") {
                toast.error(data.message || t("analytics.assessmentFailed"));
                eventSource.close();
                eventSourcesRef.current.delete(visitorId);
                setAssessmentStates(prev => {
                  const newMap = new Map(prev);
                  newMap.delete(visitorId);
                  return newMap;
                });
              }
            } catch (error) {
              console.error("Failed to parse SSE data:", error);
            }
          };

          eventSource.onerror = () => {
            eventSource.close();
            eventSourcesRef.current.delete(visitorId);
            setAssessmentStates(prev => {
              const newMap = new Map(prev);
              newMap.delete(visitorId);
              return newMap;
            });
          };
        });
      } catch (error) {
        console.error('Failed to fetch active assessments:', error);
      }
    };

    fetchActiveAssessments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visitors]);

  const fetchVisitors = async () => {
    try {
      setLoading(true);
      const offset = (page - 1) * pageSize;
      const response = await apiClient.get(
        `/admin/visitors?bot_id=${botId}&limit=${pageSize}&offset=${offset}&sort_by=${sortBy}`
      );
      setVisitors(response.data);
    } catch (error) {
      console.error("Failed to fetch visitors:", error);
      toast.error(t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  const fetchChatHistory = async (visitorId: string) => {
    try {
      setLoadingChat(true);
      const response = await apiClient.get(`/admin/visitors/${visitorId}/chat-history`);
      setChatSessions(response.data);
    } catch (error) {
      console.error("Failed to fetch chat history:", error);
      toast.error(t("common.error"));
    } finally {
      setLoadingChat(false);
    }
  };

  const handleViewChat = async (visitor: Visitor) => {
    setSelectedVisitor(visitor);
    setShowChatModal(true);
    await fetchChatHistory(visitor.id);

    // Check for active assessment and reconnect if found
    await checkAndReconnectAssessment(visitor.id);
  };

  const checkAndReconnectAssessment = async (visitorId: string) => {
    try {
      const response = await apiClient.get(`/admin/visitors/${visitorId}/active-assessment`);
      if (response.data.active && response.data.task_id) {
        const taskId = response.data.task_id;

        console.log(`Reconnecting to active assessment: ${taskId}`);
        const currentProgress = response.data.progress || 50;
        const currentStatus = response.data.status || "IN_PROGRESS";
        const currentMessage = response.data.message || t("analytics.assessmentInProgress");

        setAssessmentStates(prev => new Map(prev).set(visitorId, {
          progress: currentProgress,
          status: currentStatus,
          message: currentMessage
        }));

        const token = localStorage.getItem("access_token");
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
        const eventSource = new EventSource(
          `${apiUrl}/admin/assessment/${taskId}/progress?token=${token}`
        );

        eventSourcesRef.current.set(visitorId, eventSource);

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setAssessmentStates(prev => new Map(prev).set(visitorId, data));

            if (data.status === "COMPLETED") {
              toast.success(t("analytics.assessmentComplete"));
              eventSource.close();
              eventSourcesRef.current.delete(visitorId);
              setAssessmentStates(prev => {
                const newMap = new Map(prev);
                newMap.delete(visitorId);
                return newMap;
              });
              fetchVisitors();
            } else if (data.status === "FAILED") {
              toast.error(data.message || t("analytics.assessmentFailed"));
              eventSource.close();
              eventSourcesRef.current.delete(visitorId);
              setAssessmentStates(prev => {
                const newMap = new Map(prev);
                newMap.delete(visitorId);
                return newMap;
              });
            }
          } catch (error) {
            console.error("Failed to parse SSE data:", error);
          }
        };

        eventSource.onerror = () => {
          eventSource.close();
          eventSourcesRef.current.delete(visitorId);
          setAssessmentStates(prev => {
            const newMap = new Map(prev);
            newMap.delete(visitorId);
            return newMap;
          });
        };
      }
    } catch (error) {
      console.error("Failed to check active assessment:", error);
    }
  };

  const handleOpenWorkerSettings = async () => {
    setLoadingWorkerSettings(true);
    try {
      await new Promise(resolve => setTimeout(resolve, 100));
      setShowWorkerSettings(true);
    } catch (error) {
      console.error("Failed to open worker settings:", error);
      toast.error(t("common.error"));
    } finally {
      setLoadingWorkerSettings(false);
    }
  };

  const handleViewAssessment = async (visitor: Visitor) => {
    setSelectedVisitor(visitor);
    setShowAssessmentModal(true);

    try {
      await apiClient.get(`/admin/visitors/${visitor.id}`);
      await fetchVisitors();
    } catch (error) {
      console.error("Failed to mark visitor as viewed:", error);
    }
  };

  const handleTriggerAssessment = async (visitorId: string) => {
    console.log("Triggering assessment for visitor:", visitorId);
    console.log("Bot:", bot);
    console.log("Assessment questions:", bot?.assessment_questions);

    if (!bot?.assessment_questions || bot.assessment_questions.length === 0) {
      console.error("No assessment questions configured");
      toast.error(t("analytics.noAssessmentQuestions"));
      return;
    }

    try {
      setAssessmentStates(prev => new Map(prev).set(visitorId, {
        progress: 0,
        status: "PENDING",
        message: t("analytics.assessmentInProgress")
      }));

      console.log("Calling API:", `/admin/visitors/${visitorId}/assess`);
      const response = await apiClient.post(`/admin/visitors/${visitorId}/assess?force=true`);
      console.log("API Response:", response.data);
      const taskId = response.data.task_id;

      const token = localStorage.getItem("access_token");
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
      const eventSource = new EventSource(
        `${apiUrl}/admin/assessment/${taskId}/progress?token=${token}`
      );

      eventSourcesRef.current.set(visitorId, eventSource);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setAssessmentStates(prev => new Map(prev).set(visitorId, data));

          if (data.status === "COMPLETED") {
            toast.success(t("analytics.assessmentComplete"));
            eventSource.close();
            eventSourcesRef.current.delete(visitorId);
            setAssessmentStates(prev => {
              const newMap = new Map(prev);
              newMap.delete(visitorId);
              return newMap;
            });
            fetchVisitors();
          } else if (data.status === "FAILED") {
            toast.error(data.message || t("analytics.assessmentFailed"));
            eventSource.close();
            eventSourcesRef.current.delete(visitorId);
            setAssessmentStates(prev => {
              const newMap = new Map(prev);
              newMap.delete(visitorId);
              return newMap;
            });
          }
        } catch (error) {
          console.error("Failed to parse SSE data:", error);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        eventSourcesRef.current.delete(visitorId);
        setAssessmentStates(prev => {
          const newMap = new Map(prev);
          newMap.delete(visitorId);
          return newMap;
        });
        toast.error(t("analytics.assessmentFailed"));
      };
    } catch (error: unknown) {
      console.error("Failed to trigger assessment:", error);
      console.error("Error details:", JSON.stringify(error, null, 2));
      const errorMsg =
        error && typeof error === "object" && "response" in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data
            ?.detail
          : undefined;
      console.error("Error message:", errorMsg);
      toast.error(errorMsg || t("common.error"));
      eventSourcesRef.current.delete(visitorId);
      setAssessmentStates(prev => {
        const newMap = new Map(prev);
        newMap.delete(visitorId);
        return newMap;
      });
    }
  };

  useEffect(() => {
    return () => {
      // Close all EventSources on unmount
      eventSourcesRef.current.forEach(eventSource => eventSource.close());
      eventSourcesRef.current.clear();
    };
  }, []);

  const getLeadScoreBadge = (score: number) => {
    if (score >= 80) return "badge-success";
    if (score >= 50) return "badge-warning";
    return "badge-error";
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/dashboard/visitors")}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              {bot?.name || t("common.loading")}
            </h1>
            <p className="text-gray-600 mt-1">{t("visitors.viewVisitors")}</p>
          </div>
        </div>
        <button
          onClick={handleOpenWorkerSettings}
          disabled={loadingWorkerSettings}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loadingWorkerSettings ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>{t("common.loading")}</span>
            </>
          ) : (
            <>
              <Settings className="w-4 h-4" />
              <span>{t("workers.settingsModal")}</span>
            </>
          )}
        </button>
      </div>

      <div className="card">
        {/* Sort Dropdown */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">
              {t("common.sortBy")}:
            </label>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              className="input-field py-1.5"
            >
              <option value="assessed_at">{t("visitors.sortByAssessed")}</option>
              <option value="lead_score">{t("visitors.sortByScore")}</option>
              <option value="created_at">{t("visitors.sortByCreated")}</option>
            </select>
          </div>
        </div>
        {loading ? (
          <div className="text-center py-12 text-gray-500">{t("common.loading")}</div>
        ) : visitors.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            {t("analytics.noVisitors")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t("analytics.name")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t("analytics.email")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t("analytics.phone")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t("analytics.leadScore")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t("analytics.createdAt")}
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t("analytics.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {visitors.map((visitor) => (
                  <tr key={visitor.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-900">
                          {visitor.name || "-"}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {visitor.email || "-"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {visitor.phone || "-"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <Award className="w-4 h-4 text-gray-400" />
                        <span
                          className={`badge ${getLeadScoreBadge(visitor.lead_score)}`}
                        >
                          {visitor.lead_score}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(visitor.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          onClick={() => handleViewChat(visitor)}
                          className="text-[var(--color-primary)] hover:text-[var(--color-primary-dark)] flex items-center gap-1"
                        >
                          <MessageSquare className="w-4 h-4" />
                          <span>{t("visitors.viewChat")}</span>
                        </button>

                        {visitor.lead_assessment?.assessment ? (
                          <>
                            <button
                              onClick={() => handleViewAssessment(visitor)}
                              className="text-green-600 hover:text-green-700 flex items-center gap-1"
                            >
                              <CheckCircle2 className="w-4 h-4" />
                              <span>{t("visitors.viewAssessment")}</span>
                              {visitor.is_new && (
                                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-red-500 text-white rounded-full animate-pulse">
                                  NEW
                                </span>
                              )}
                            </button>
                            {assessmentStates.has(visitor.id) ? (
                              <div className="flex items-center gap-2 text-yellow-600">
                                <Clock className="w-4 h-4 animate-spin" />
                                <span className="text-xs">
                                  {assessmentStates.get(visitor.id)?.progress || 0}%
                                </span>
                              </div>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  handleTriggerAssessment(visitor.id);
                                }}
                                className="text-blue-600 hover:text-blue-700 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled={!bot?.assessment_questions || bot.assessment_questions.length === 0}
                                title="Re-assess visitor"
                              >
                                <ClipboardCheck className="w-4 h-4" />
                                <span>{t("analytics.triggerAssessment")}</span>
                              </button>
                            )}
                          </>
                        ) : assessmentStates.has(visitor.id) ? (
                          <div className="flex items-center gap-2 text-yellow-600">
                            <Clock className="w-4 h-4 animate-spin" />
                            <span className="text-xs">
                              {assessmentStates.get(visitor.id)?.progress || 0}%
                            </span>
                          </div>
                        ) : (
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              console.log("Button clicked for visitor:", visitor.id);
                              handleTriggerAssessment(visitor.id);
                            }}
                            className="text-blue-600 hover:text-blue-700 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                            disabled={!bot?.assessment_questions || bot.assessment_questions.length === 0}
                          >
                            <ClipboardCheck className="w-4 h-4" />
                            <span>{t("analytics.triggerAssessment")}</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        {!loading && visitors.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200 flex items-center justify-between">
            <div className="text-sm text-gray-700">
              {t("common.showing")} {visitors.length} {t("visitors.visitors")}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.previous")}
              </button>
              <span className="px-4 py-2 text-sm text-gray-700">
                {t("common.page")} {page}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={visitors.length < pageSize}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.next")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Chat History Modal */}
      {showChatModal && selectedVisitor && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">
                {t("visitors.chatHistory")} - {selectedVisitor.name || selectedVisitor.email || t("visitors.anonymous")}
              </h2>
              <button
                onClick={() => {
                  setShowChatModal(false);
                  setSelectedVisitor(null);
                  setChatSessions([]);
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-600" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loadingChat ? (
                <div className="text-center py-12 text-gray-500">
                  {t("common.loading")}
                </div>
              ) : chatSessions.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  {t("visitors.noMessages")}
                </div>
              ) : (
                chatSessions.map((session) => (
                  <div key={session.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-sm text-gray-600 mb-4">
                      <Clock className="w-4 h-4" />
                      <span>{formatDate(session.created_at)}</span>
                      {session.closed_at && (
                        <span className="text-gray-400">
                          - {formatDate(session.closed_at)}
                        </span>
                      )}
                    </div>

                    <div className="space-y-3">
                      {session.messages.map((message) => (
                        <div key={message.id} className="space-y-2">
                          <div className="flex items-start gap-2">
                            <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                              <User className="w-3 h-3 text-blue-600" />
                            </div>
                            <div className="flex-1 bg-blue-50 rounded-lg p-3">
                              <p className="text-sm text-gray-900">{message.query}</p>
                            </div>
                          </div>

                          <div className="flex items-start gap-2">
                            <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                              <MessageSquare className="w-3 h-3 text-green-600" />
                            </div>
                            <div className="flex-1 bg-gray-50 rounded-lg p-3">
                              <p className="text-sm text-gray-900">{message.response}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Assessment Results Modal */}
      {showAssessmentModal && selectedVisitor?.lead_assessment?.assessment && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto"
          onClick={() => {
            setShowAssessmentModal(false);
            setSelectedVisitor(null);
          }}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col my-8"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">
                {t("analytics.assessmentResults")} - {selectedVisitor.name || selectedVisitor.email}
              </h2>
              <button
                onClick={() => {
                  setShowAssessmentModal(false);
                  setSelectedVisitor(null);
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-600" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Summary */}
              {selectedVisitor.lead_assessment.assessment.summary && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="font-semibold text-blue-900 mb-2">
                    {t("analytics.assessmentSummary")}
                  </h3>
                  <p className="text-sm text-blue-800">
                    {selectedVisitor.lead_assessment.assessment.summary}
                  </p>
                </div>
              )}

              {/* Questions & Answers */}
              {selectedVisitor.lead_assessment.assessment.results?.map((result, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4 space-y-3">
                  <div>
                    <span className="text-xs font-semibold text-gray-500 uppercase">
                      {t("analytics.question")} {index + 1}
                    </span>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {result.question}
                    </p>
                  </div>

                  <div>
                    <span className="text-xs font-semibold text-gray-500 uppercase">
                      {t("analytics.answer")}
                    </span>
                    <p className="text-sm text-gray-700 mt-1">{result.answer}</p>
                  </div>

                  <div className="flex items-center gap-4">
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase">
                        {t("analytics.confidence")}
                      </span>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="w-full bg-gray-200 rounded-full h-2 max-w-[200px]">
                          <div
                            className="bg-green-600 h-2 rounded-full"
                            style={{ width: `${result.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-gray-900">
                          {Math.round(result.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {selectedVisitor.lead_assessment.assessment.assessed_at && (
                <div className="text-xs text-gray-500 text-center pt-4 border-t border-gray-200">
                  {t("visitors.assessedAt")}: {formatDate(selectedVisitor.lead_assessment.assessment.assessed_at)}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Worker Settings Modal */}
      <WorkerSettingsModal
        botId={botId}
        isOpen={showWorkerSettings}
        onClose={() => setShowWorkerSettings(false)}
      />

      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </div>
  );
}

