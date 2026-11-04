import type { LucideIcon } from "lucide-react";
import type { PlatformPermission } from "@/shared/auth/platformAccess";

export type NavItem = {
  path: string;
  label: string;
  title?: string;
  section?: string;
  subtitle?: string;
  requirementId?: string;
  requiredPermission?: PlatformPermission;
  icon: LucideIcon;
  contentHeading?: boolean;
  layout?: "conversation";
};
