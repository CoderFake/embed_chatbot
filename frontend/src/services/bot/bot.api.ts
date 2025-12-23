import globalConfig from "@/configs";
import { ChatbotPropsType } from "@/types/chatbot.type";
import { GetBotParams, UpdateBotType } from "./type";
import { ResponseErrorDetail } from "@/types/response.type";

export const createBot = async (
    data: ChatbotPropsType,
    token: string
): Promise<ChatbotPropsType | ResponseErrorDetail | null> => {
    try {
        const responsePost = await fetch(`${globalConfig.apiUrl}/api/v1/bots`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(data),
        });

        if (!responsePost.ok) {
            console.error(
                "Failed to create bot:",
                responsePost.status,
                responsePost.statusText
            );
            return null;
        }

        const dataPost: ChatbotPropsType = await responsePost.json();
        return dataPost;
    } catch (error) {
        console.error("Error creating bot:", error);
        return null;
    }
};

export const getBot = async (params: GetBotParams) => {
    try {
        const { skip = 0, limit = 100, status = "active" } = params;
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/bots?skip=${skip}&limit=${limit}&status=${status}`
        );
        if (!response.ok) {
            throw new Error("Failed to fetch data");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching bots:", error);
        return null;
    }
};

export const getBotById = async (id: string, token: string) => {
    try {
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/bots/${id}`,
            {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            }
        );
        if (!response.ok) {
            throw new Error("Failed to fetch data");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error fetching bot:", error);
        return null;
    }
};

export const updateBotById = async (
    id: string,
    token: string,
    updateData: UpdateBotType
) => {
    try {
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/bots/${id}`,
            {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify(updateData),
            }
        );
        if (!response.ok) {
            throw new Error("Failed to update data");
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error updating bot:", error);
        return null;
    }
};

export const deleteBotById = async (id: string, token: string) => {
    try {
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/bots/${id}`,
            {
                method: "DELETE",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            }
        );
        if (!response.ok) {
            throw new Error("Failed to delete data");
        }
        return true;
    } catch (error) {
        console.error("Error deleting bot:", error);
        return null;
    }
};

export const activeBotById = async (id: string, token: string) => {
    try {
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/bots/${id}/activate`,
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            }
        );
        if (!response.ok) {
            throw new Error("Failed to activate data");
        }
        return true;
    } catch (error) {
        console.error("Error activating bot:", error);
        return null;
    }
};

export const deactivateBotById = async (id: string, token: string) => {
    try {
        const response = await fetch(
            `${globalConfig.apiUrl}/api/v1/bots/${id}/deactivate`,
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            }
        );
        if (!response.ok) {
            throw new Error("Failed to deactivate data");
        }
        return true;
    } catch (error) {
        console.error("Error deactivating bot:", error);
        return null;
    }
};
