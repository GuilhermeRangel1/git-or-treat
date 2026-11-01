import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { onlineManager } from "@tanstack/react-query";
import { afterEach, beforeEach, vi } from "vitest";
import {
  clearReauthenticationRequired,
  setSessionConfigured,
  setUnauthorizedHandler,
} from "@/shared/auth/authorization";

// Garante que o TanStack Query sempre considere o ambiente online em testes
onlineManager.setOnline(true);

beforeEach(() => {
  setSessionConfigured(false);
  clearReauthenticationRequired();
  setUnauthorizedHandler(null);
  if (typeof window !== "undefined") {
    window.matchMedia =
      window.matchMedia ||
      vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));
  }
});

afterEach(cleanup);
