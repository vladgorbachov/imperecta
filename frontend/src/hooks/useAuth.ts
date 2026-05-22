import { useMutation, useQueryClient } from "@tanstack/react-query";
import i18n from "@/i18n";
import { authApi } from "@/api/auth";

export function useAuth() {
  const queryClient = useQueryClient();
  const loginMutation = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authApi.login(email, password),
  });
  const registerMutation = useMutation({
    mutationFn: ({
      email,
      password,
      name,
      companyName,
    }: {
      email: string;
      password: string;
      name: string;
      companyName?: string;
      language?: string;
    }) => authApi.register(email, password, name, companyName, language ?? i18n.language),
  });
  return { loginMutation, registerMutation, queryClient };
}
