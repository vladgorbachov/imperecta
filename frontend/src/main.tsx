import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppWithInit } from "@/AppWithInit";
import "@/api/setupAuth";
import "@/i18n";
import "./index.css";
import "./styles/glass.css";
import "./styles/components.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppWithInit />
  </StrictMode>
);
