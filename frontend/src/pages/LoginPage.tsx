import { useState } from "react";
import { Link, useNavigate, useLocation, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((s) => s.login);
  const accessToken = useAuthStore((s) => s.accessToken);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (accessToken) {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const message = err && typeof err === "object" && "response" in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : "Invalid email or password";
      setError(typeof message === "string" ? message : "Invalid email or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-100 p-4">
      <Card className="w-full max-w-md border border-neutral-200 bg-white text-neutral-900 shadow-md">
        <CardHeader>
          <CardTitle className="text-2xl text-neutral-900">{t("auth.login")}</CardTitle>
          <CardDescription className="text-neutral-600">
            Enter your credentials to access your account
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-neutral-700">
                {t("auth.email")}
              </label>
              <Input
                className="border-neutral-300 bg-white text-neutral-900 placeholder:text-neutral-500"
                id="email"
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-neutral-700">
                {t("auth.password")}
              </label>
              <Input
                id="password"
                type="password"
                className="border-neutral-300 bg-white text-neutral-900"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-4">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "..." : t("auth.submitLogin")}
            </Button>
            <p className="text-center text-sm text-neutral-600">
              {t("auth.noAccount")}{" "}
              <Link to="/register" className="font-medium text-indigo-600 hover:underline">
                {t("auth.register")}
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
