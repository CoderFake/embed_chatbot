import globalConfig from "@/configs";
import { ResponseErrorDetail } from "@/types/response.type";
import {
    DocumentResponse,
    GetListDocumentParams,
    UploadDocumentProps,
    UploadDocumentResponse,
} from "./type";

export const uploadDocument = async ({
    bot_id,
    file,
    title,
    token,
}: UploadDocumentProps): Promise<
    UploadDocumentResponse | ResponseErrorDetail
> => {
    const formData = new FormData();
    formData.append("file", file);
    let url = `${globalConfig.apiUrl}/api/v1/bots/${bot_id}/documents/upload`;
    if (title) {
        url += `?title=${encodeURIComponent(title)}`;
    }

    const response = await fetch(url, {
        method: "POST",
        headers: {
            Authorization: `Bearer ${token}`,
        },
        body: formData,
    });

    if (!response.ok) {
        throw new Error("Failed to upload document");
    }

    return await response.json();
};

export const getListDocument = async (
    id: string,
    params: GetListDocumentParams
) => {
    try {
        const { page = 1, size = 20, status_filter = "pending" } = params;
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/bots/${id}/documents?page=${page}&size=${size}&status_filter=${status_filter}`
        );
        if (!response.ok) {
            throw new Error("Failed to fetch data");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching data:", error);
        return null;
    }
};

export const getDocumentById = async (
    id: string
): Promise<DocumentResponse | ResponseErrorDetail | null> => {
    try {
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/documents/${id}`
        );
        if (!response.ok) {
            throw new Error("Failed to fetch data");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching data:", error);
        return null;
    }
};

export const deleteDocumentById = async (id: string, token: string) => {
    try {
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/documents/${id}`,
            {
                method: "DELETE",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            }
        );
        if (!response.ok) {
            throw new Error("Failed to delete document");
        }
        return true;
    } catch (error) {
        console.error("Error deleting document:", error);
        return null;
    }
};
