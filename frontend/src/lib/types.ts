export type Risk = "low" | "medium" | "high" | "critical";
export type Provider = "gmail" | "microsoft";

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  role: "owner" | "admin" | "operator" | "viewer";
}

export interface TokenPair {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Summary {
  connected_accounts: number;
  total_messages: number;
  analyzed_messages: number;
  open_alerts: number;
  critical_alerts: number;
  messages_last_24h: number;
  analysis_coverage_percent: number;
  trend: Array<{ day: string; messages: number; alerts: number }>;
}

export interface Account {
  id: string;
  provider: Provider;
  email: string;
  status: "connected" | "syncing" | "error" | "reauth_required" | "disconnected";
  last_synced_at: string | null;
  last_error: string | null;
  message_count: number;
  alert_count: number;
}

export interface Message {
  id: string;
  account_id: string;
  provider: Provider;
  account_email: string;
  sender: string | null;
  subject: string | null;
  snippet: string | null;
  body: string | null;
  body_html: string | null;
  received_at: string | null;
  category: string | null;
  risk_level: Risk | null;
  alert_count: number;
  is_read: boolean;
  is_starred: boolean;
  mailbox: "inbox" | "archive" | "trash";
  thread_id: string | null;
}

export interface MessageContent {
  id: string;
  body: string | null;
  body_html: string | null;
}

export interface Analysis {
  id: string;
  message_id: string;
  account_email: string;
  sender: string | null;
  subject: string | null;
  service: string | null;
  platform: string | null;
  amount: string | null;
  currency: string | null;
  country: string | null;
  language: string;
  priority: string;
  email_type: string;
  category: string;
  action_required: string | null;
  risk_level: Risk;
  alert_types: string[];
  model: string;
  prompt_version: string;
  created_at: string;
}

export interface Alert {
  id: string;
  message_id: string;
  alert_type: string;
  title: string;
  detail: string | null;
  risk_level: Risk;
  created_at: string;
  resolved_at: string | null;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface PlanUsage {
  plan_code: string; plan_name: string; status: string; period_end: string;
  accounts: number; accounts_limit: number; users: number; users_limit: number;
  messages_this_month: number; messages_limit: number;
}

export interface WorkspaceUser extends User {
  is_active: boolean;
  last_login_at: string | null;
}
