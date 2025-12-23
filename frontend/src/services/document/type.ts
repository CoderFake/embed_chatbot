export type UploadDocumentProps = {
    bot_id: string;
    file: File;
    title?: string;
    token: string;
};
export type GetListDocumentParams = {
    bot_id: string;
    page?: number;
    size?: number;
    status_filter?: string | null;
};
export interface UploadDocumentResponse {
    job_id: string;
    job_type: string;
    status: string;
    message: string;
    sse_endpoint: string;
    document_id: string;
    bot_id: string;
}
export interface DocumentResponse {
    title: string;
    url: string;
    file_path: string;
    id: string;
    bot_id: string;
    user_id: string;
    content_hash: string;
    status: string;
    raw_content: string;
    //   extra_data: Record<string, any>;
    error_message: string;
    processed_at: string;
    created_at: string;
    updated_at: string;
}
