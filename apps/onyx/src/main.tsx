import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyMotionClass } from "./motion";
import "./onyx-command.css";

applyMotionClass();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
