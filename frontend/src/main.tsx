import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { useAuthStore } from "@/stores/authStore";
import { App } from "@/App";
import { LoadingScreen } from "@/components/LoadingScreen";
import "@/api/setupAuth";
import "@/i18n";
import "./index.css";

function AppWithInit() {
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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppWithInit />
  </StrictMode>
);
