import { useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";
import { App } from "@/App";
import { LoadingScreen } from "@/components/LoadingScreen";

export function AppWithInit() {
  const restoreSession = useAuthStore((s) => s.restoreSession);
  const isInitialized = useAuthStore((s) => s.isInitialized);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  if (!isInitialized) {
    return <LoadingScreen />;
  }

  return <App />;
}
