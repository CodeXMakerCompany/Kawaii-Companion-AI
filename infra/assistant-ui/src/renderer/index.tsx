/// <reference types="./preload.d.ts" />
import { createRoot } from "react-dom/client";
import { App } from "./App.js";
import React from "react";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Missing #root");
createRoot(rootEl).render(<App />);
