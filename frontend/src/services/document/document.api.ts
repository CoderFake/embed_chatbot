import globalConfig from "@/configs";
import { apiClient } from "@/lib/auth-api";

export interface Document {
  id: string;
  bot_id: string;
  uploaded_by?: string;
  title: string;
  source_type: "file" | "crawl";
  file_path?: string;
  web_url?: string;
  status: "pending" | "processing" | "completed" | "failed";
  chunk_count: number;
  file_size?: number;
  mime_type?: string;
  error_message?: string;
  task_id?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface DocumentJobResponse {
  job_id: string;
  job_type: string;
  status: string;
  message: string;
  sse_endpoint: string;
  document_id: string;
  bot_id: string;
}

export interface UploadDocumentParams {
  botId: string;
  file: File;
  title?: string;
}

export interface ListDocumentsParams {
  botId: string;
  page?: number;
  size?: number;
  status?: "pending" | "processing" | "completed" | "failed";
  sortBy?: string;
}

/**
 * Upload a document file for a bot
 */
export const uploadDocument = async (
  params: UploadDocumentParams
): Promise<DocumentJobResponse> => {
  const { botId, file, title } = params;

  const formData = new FormData();
  formData.append("file", file);

  let url = `/bots/${botId}/documents/upload`;
  if (title) {
    url += `?title=${encodeURIComponent(title)}`;
  }

  const response = await apiClient.post(url, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

/**
 * List documents for a bot
 */
export const listDocuments = async (
  params: ListDocumentsParams
): Promise<DocumentListResponse> => {
  const { botId, page = 1, size = 20, status, sortBy = "created_at" } = params;

  const queryParams = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
    sort_by: sortBy,
  });

  if (status) {
    queryParams.append("status_filter", status);
  }

  const response = await apiClient.get(
    `/bots/${botId}/documents?${queryParams.toString()}`
  );

  return response.data;
};

/**
 * Get document by ID
 */
export const getDocument = async (documentId: string): Promise<Document> => {
  const response = await apiClient.get(`/documents/${documentId}`);
  return response.data;
};

/**
 * Delete document
 */
export const deleteDocument = async (documentId: string): Promise<void> => {
  await apiClient.delete(`/documents/${documentId}`);
};

/**
 * Get SSE endpoint URL for task progress
 */
export const getTaskProgressUrl = (taskId: string): string => {
  return `${globalConfig.apiUrl}/api/v1/tasks/${taskId}/progress`;
};

