/**
 * Common API calls for roles, languages, etc.
 */

import { apiClient } from "../auth-api";

export interface Role {
  value: string;
  label: string;
  description: string;
}

export interface Language {
  code: string;
  name: string;
  native_name: string;
}

export const commonAPI = {
  getRoles: async (): Promise<Role[]> => {
    const response = await apiClient.get("/others/roles");
    return response.data.roles;
  },

  getLanguages: async (): Promise<Language[]> => {
    const response = await apiClient.get("/others/languages");
    return response.data.languages;
  },
};

