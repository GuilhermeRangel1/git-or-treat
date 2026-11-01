import { useState, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "@/shared/api/query-client";
import { ThemeProvider } from "@/shared/theme/ThemeProvider";
import GoldPublicationNotice from "./GoldPublicationNotice";
import { AuthProvider } from "@/shared/auth/AuthProvider";

export default function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <GoldPublicationNotice />
          {children}
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
