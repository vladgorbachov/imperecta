import { apiClient } from "./client";

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post("/auth/login", { email, password }),
  register: (email: string, password: string) =>
    apiClient.post("/auth/register", { email, password }),
};
