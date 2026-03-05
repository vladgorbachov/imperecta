import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { useAuthStore } from "@/stores/authStore";
import { App } from "@/App";
import { LoadingScreen } from "@/components/LoadingScreen";
import "@/i18n";
import "./index.css";

function AppWithInit() {
  const init = useAuthStore((s) => s.init);
  const isInitialized = useAuthStore((s) => s.isInitialized);

  useEffect(() => {
    init();
  }, [init]);

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
