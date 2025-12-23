"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useToast } from "@/hooks/useToast";
import { apiClient } from "@/lib/auth-api";
import { getErrorMessage } from "@/lib/error-utils";
import { ToastContainer } from "@/components/ui/Toast";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DocumentRow } from "@/components/documents/DocumentRow";
import {
  Upload,
  Search,
  X,
  ArrowLeft,
} from "lucide-react";
import {
  Document,
  uploadDocument,
  listDocuments,
  deleteDocument,
} from "@/services/document";

interface Bot {
  id: string;
  name: string;
  bot_key: string;
  status: string;
}

export default function BotDocumentsPage() {
  const params = useParams();
  const router = useRouter();
  const { t } = useLanguage();
  const toast = useToast();
  const botId = params.bot_id as string;
  const [bot, setBot] = useState<Bot | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(
    null
  );
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [sortBy, setSortBy] = useState("created_at");

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
        router.push("/dashboard/documents");
      }
    };

    fetchBot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId]);

  useEffect(() => {
    if (!botId) return;

    const fetchDocuments = async () => {
      try {
        setLoading(true);
        const response = await listDocuments({
          botId,
          page,
          size: 20,
          status: statusFilter as "pending" | "processing" | "completed" | "failed" | undefined,
          sortBy,
        });
        setDocuments(response.items);
        setTotal(response.total);
        setTotalPages(response.pages);
      } catch (error) {
        console.error("Failed to fetch documents:", error);
        toast.error(t("common.error"));
      } finally {
        setLoading(false);
      }
    };

    fetchDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId, page, statusFilter, sortBy]);

  const refreshDocuments = async () => {
    if (!botId) return;
    try {
      setLoading(true);
      const response = await listDocuments({
        botId,
        page,
        size: 20,
        status: statusFilter as "pending" | "processing" | "completed" | "failed" | undefined,
        sortBy,
      });
      setDocuments(response.items);
      setTotal(response.total);
      setTotalPages(response.pages);
    } catch (error) {
      console.error("Failed to fetch documents:", error);
      toast.error(t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    const filesToUpload = uploadFiles.length > 0 ? uploadFiles : (uploadFile ? [uploadFile] : []);

    if (filesToUpload.length === 0 || !botId) {
      toast.error(t("documents.selectFile"));
      return;
    }

    // Validate file sizes (50MB = 50 * 1024 * 1024 bytes)
    const MAX_SIZE = 50 * 1024 * 1024;
    const oversizedFiles = filesToUpload.filter(f => f.size > MAX_SIZE);
    if (oversizedFiles.length > 0) {
      toast.error(`File(s) too large: ${oversizedFiles.map(f => f.name).join(", ")}. Max 50MB per file.`);
      return;
    }

    try {
      setUploading(true);

      // Upload files sequentially
      for (const file of filesToUpload) {
        await uploadDocument({
          botId,
          file,
          title: uploadTitle || undefined,
        });
      }

      toast.success(t("documents.uploadSuccess"));

      setShowUploadModal(false);
      setUploadFile(null);
      setUploadFiles([]);
      setUploadTitle("");
      setUploading(false);

      refreshDocuments();
    } catch (error: unknown) {
      console.error("Failed to upload document:", error);
      toast.error(getErrorMessage(error, t("documents.uploadFailed")));
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadFiles([]);
      setUploadTitle("");
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!documentToDelete) return;

    try {
      await deleteDocument(documentToDelete.id);
      toast.success(t("documents.documentDeleted"));
      refreshDocuments();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, t("common.error")));
    } finally {
      setDocumentToDelete(null);
    }
  };

  const filteredDocuments = documents.filter(
    (doc) =>
      doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.web_url?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.file_path?.toLowerCase().includes(searchQuery.toLowerCase())
  );



  if (!bot) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb & Header */}
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <button
          onClick={() => router.push("/dashboard/documents")}
          className="hover:text-primary transition-colors"
        >
          {t("documents.title")}
        </button>
        <span>/</span>
        <span className="text-gray-900 font-medium">{bot.name}</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/dashboard/documents")}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{bot.name}</h1>
            <p className="text-gray-600 mt-1 font-mono text-sm">{bot.bot_key}</p>
          </div>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Upload className="w-5 h-5" />
          {t("documents.upload")}
        </button>
      </div>

      {/* Filters */}
      <div className="card space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t("documents.filterByStatus")}
            </label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="input-field"
            >
              <option value="">{t("documents.allStatuses")}</option>
              <option value="pending">{t("documents.pending")}</option>
              <option value="processing">{t("documents.processing")}</option>
              <option value="completed">{t("documents.completed")}</option>
              <option value="failed">{t("documents.failed")}</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t("common.sortBy")}
            </label>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              className="input-field"
            >
              <option value="created_at">{t("documents.sortByCreated")}</option>
              <option value="title">{t("documents.sortByTitle")}</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t("documents.search")}
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
              <input
                type="text"
                placeholder={t("documents.searchPlaceholder")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-field input-with-icon pr-10"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Documents Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("documents.name")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("documents.type")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("documents.status")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("documents.uploadedBy")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("documents.size")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("documents.createdAt")}
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("documents.actions")}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    {t("common.loading")}
                  </td>
                </tr>
              ) : filteredDocuments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    {t("documents.noDocuments")}
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((doc) => (
                  <DocumentRow
                    key={doc.id}
                    document={doc}
                    onDelete={setDocumentToDelete}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Showing {documents.length} of {total} documents
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary disabled:opacity-50"
              >
                Previous
              </button>
              <span className="px-4 py-2 text-sm text-gray-700">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-secondary disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black flex items-center justify-center z-50 p-4"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
        >
          <div className="bg-white rounded-lg max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                {t("documents.uploadFile")}
              </h3>
              <button
                onClick={() => {
                  if (!uploading) {
                    setShowUploadModal(false);
                    setUploadFile(null);
                    setUploadTitle("");
                  }
                }}
                className="text-gray-400 hover:text-gray-600"
                disabled={uploading}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("documents.documentTitle")}
              </label>
              <input
                type="text"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder={t("documents.titlePlaceholder")}
                className="input-field"
                disabled={uploading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("documents.selectFile")}
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                <input
                  type="file"
                  multiple
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length > 0) {
                      setUploadFiles(files);
                      if (!uploadTitle && files.length === 1) {
                        setUploadTitle(files[0].name);
                      }
                    }
                  }}
                  accept=".pdf,.docx,.txt"
                  className="hidden"
                  id="file-upload"
                  disabled={uploading}
                />
                <label
                  htmlFor="file-upload"
                  className="cursor-pointer flex flex-col items-center"
                >
                  <Upload className="w-12 h-12 text-gray-400 mb-2" />
                  <p className="text-sm text-gray-600">
                    {uploadFiles.length > 0
                      ? `${uploadFiles.length} file(s) selected: ${uploadFiles.map(f => f.name).join(", ")}`
                      : uploadFile
                        ? uploadFile.name
                        : t("documents.dragDropFile")}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {t("documents.fileTypes")}
                  </p>
                  <p className="text-xs text-gray-500">
                    Max 50MB per file
                  </p>
                </label>
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadFile(null);
                  setUploadTitle("");
                }}
                className="btn-secondary"
                disabled={uploading}
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleUpload}
                className="btn-primary"
                disabled={uploadFiles.length === 0 && !uploadFile || uploading}
              >
                {uploading ? t("documents.uploading") : t("documents.upload")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {documentToDelete && (
        <ConfirmDialog
          isOpen={true}
          onClose={() => setDocumentToDelete(null)}
          onConfirm={handleDelete}
          title={t("documents.confirmDelete")}
          message={`${t("common.confirmMessage")} "${documentToDelete.title}"?`}
          confirmText={t("common.delete")}
          cancelText={t("common.cancel")}
          type="danger"
        />
      )}

      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </div>
  );
}
