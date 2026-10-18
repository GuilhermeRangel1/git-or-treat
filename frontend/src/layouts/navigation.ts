import type { LucideIcon } from "lucide-react";

export type NavItem = {
  path: string;
  label: string;
  subtitle?: string;
  requirementId?: string;
  icon: LucideIcon;
  contentHeading?: boolean;
};
