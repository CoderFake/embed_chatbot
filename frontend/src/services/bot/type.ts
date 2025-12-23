import { DisplayConfigType } from "@/types/chatbot.type";

export type GetBotParams = {
    skip?: number;
    limit?: number;
    status?: string;
};

export type UpdateBotType = {
    name: string;
    language: string;
    status: string;
    display_config: DisplayConfigType;
    provider_config: {
        provider_id: string;
        model_id: string;
        api_key: string;
        // config: {};
    };
};
