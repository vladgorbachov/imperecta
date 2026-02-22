import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { format } from "date-fns";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

export function SettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);

  const [profileForm, setProfileForm] = useState({
    name: "",
    company_name: "",
  });
  const [telegramCode, setTelegramCode] = useState<string | null>(null);
  const [telegramBotUrl, setTelegramBotUrl] = useState<string>("");

  const { data: user, isLoading } = useQuery({
    queryKey: ["user", "me"],
    queryFn: async () => {
      const { data } = await authApi.getMe();
      return data;
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (data: {
      name?: string;
      company_name?: string;
      language?: string;
    }) => {
      const res = await authApi.updateMe(data);
      return res.data;
    },
    onSuccess: (updatedUser) => {
      if (updatedUser) setUser(updatedUser);
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
      toast.success("Profile updated");
    },
    onError: () => toast.error("Failed to update"),
  });

  const telegramLinkMutation = useMutation({
    mutationFn: async () => {
      const { data } = await authApi.getTelegramLink();
      return data;
    },
    onSuccess: (data) => {
      setTelegramCode(data.code);
      setTelegramBotUrl(data.bot_url);
      toast.success("Code generated");
    },
    onError: () => toast.error("Failed to generate code"),
  });

  useEffect(() => {
    if (user) {
      setProfileForm({
        name: user.name,
        company_name: user.company_name ?? "",
      });
    }
  }, [user?.id]);

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate({
      name: profileForm.name,
      company_name: profileForm.company_name || undefined,
    });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("nav.settings")}</h1>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Update your account details</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <form onSubmit={handleProfileSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("auth.name")}</label>
                <Input
                  value={profileForm.name}
                  onChange={(e) =>
                    setProfileForm((f) => ({ ...f, name: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t("auth.companyName")}
                </label>
                <Input
                  value={profileForm.company_name}
                  onChange={(e) =>
                    setProfileForm((f) => ({
                      ...f,
                      company_name: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("auth.email")}</label>
                <Input value={user?.email ?? ""} readOnly className="bg-muted" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Language</label>
                <Select
                  value={user?.language ?? "ru"}
                  onValueChange={(v) =>
                    updateMutation.mutate({ language: v })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ru">Русский</SelectItem>
                    <SelectItem value="en">English</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" disabled={updateMutation.isPending}>
                Save
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Telegram</CardTitle>
          <CardDescription>
            Link your Telegram for notifications
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            {telegramCode
              ? `Your code: ${telegramCode}. Send it to the bot.`
              : "Get a 6-digit code to link your account."}
          </p>
          {telegramBotUrl && (
            <a
              href={telegramBotUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mb-4 block text-sm text-primary hover:underline"
            >
              {telegramBotUrl}
            </a>
          )}
          <Button
            variant="outline"
            onClick={() => telegramLinkMutation.mutate()}
            disabled={telegramLinkMutation.isPending}
          >
            Get link code
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>
            Preferred channel and digest time
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Configure in alert rules. Digest time: coming soon.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Plan</CardTitle>
          <CardDescription>Current subscription</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="font-medium capitalize">{user?.plan ?? "—"}</p>
          {user?.trial_ends_at && (
            <p className="mt-2 text-sm text-muted-foreground">
              Trial ends: {format(new Date(user.trial_ends_at), "dd.MM.yyyy")}
            </p>
          )}
          <Button variant="outline" className="mt-4" disabled>
            Upgrade (coming soon)
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
