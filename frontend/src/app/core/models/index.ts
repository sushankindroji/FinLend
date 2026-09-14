// ============================================================
// FinLend – canonical TypeScript models matching backend schemas
// ============================================================

export type Role = 'borrower' | 'lender' | 'admin';
export type RiskCategory = 'LOW' | 'MEDIUM' | 'HIGH';
export type ChainMode = 'ON_CHAIN' | 'LOCAL_SIMULATION' | 'DISABLED';

export type LoanStatus =
  | 'REQUESTED'
  | 'CREDIT_CHECK'
  | 'APPROVED'
  | 'REJECTED'
  | 'OPEN_FOR_FUNDING'
  | 'PARTIALLY_FUNDED'
  | 'FUNDED'
  | 'ACTIVE'
  | 'LATE'
  | 'REPAID'
  | 'DEFAULTED';

// ── Auth ──────────────────────────────────────────────────
export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  role: Role;
  user_id: string;
}

// ── User ──────────────────────────────────────────────────
export interface UserStats {
  completed_loans?: number;
  total_borrowed?: number;
  total_repaid?: number;
  on_time_repayments?: number;
  late_repayments?: number;
  defaults?: number;
  average_delay_days?: number;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  phone?: string;
  credit_score?: number;
  borrowing_limit?: number;
  lending_balance?: number;
  stats?: UserStats;
  created_at: string;
}

// ── Credit score ──────────────────────────────────────────
export interface CreditHistoryEntry {
  credit_score: number;
  previous_score: number;
  events: string[];
  borrowing_limit: number;
  reason: string;
  created_at: string;
}

export interface CreditScore {
  user_id: string;
  credit_score: number;
  risk_category: RiskCategory;
  borrowing_limit: number;
  explanation: string;
  history: CreditHistoryEntry[];
}

// ── Loan ──────────────────────────────────────────────────
export interface Loan {
  id: string;
  borrower_id: string;
  borrower_name?: string;
  amount: number;
  duration_days: number;
  interest_rate: number;
  total_due: number;
  amount_funded: number;
  amount_repaid: number;
  status: LoanStatus;
  risk_category?: RiskCategory;
  purpose?: string;
  source: string;
  due_date?: string;
  rejection_reason?: string;
  created_at: string;
  updated_at: string;
}

// ── Funding ───────────────────────────────────────────────
export interface Funding {
  id: string;
  loan_id: string;
  lender_id: string;
  amount: number;
  expected_return: number;
  tx_hash?: string;
  chain_mode?: ChainMode;
  created_at: string;
}

// ── Repayment ─────────────────────────────────────────────
export interface Repayment {
  id: string;
  loan_id: string;
  borrower_id: string;
  amount: number;
  is_on_time: boolean;
  is_early: boolean;
  days_late: number;
  tx_hash?: string;
  chain_mode?: ChainMode;
  created_at: string;
}

// ── Repayment schedule entry ──────────────────────────────
export interface ScheduleEntry {
  payment_number: number;
  due_date: string;
  principal: number;
  interest: number;
  total: number;
  status: 'paid' | 'due' | 'upcoming' | 'overdue';
  paid_amount?: number;
}

// ── Transaction ───────────────────────────────────────────
export interface Transaction {
  id: string;
  loan_id: string;
  type: 'FUNDING' | 'REPAYMENT';
  amount: number;
  tx_hash?: string;
  chain_mode?: ChainMode;
  explorer_url?: string;
  created_at: string;
  // lender investments: enriched field
  expected_return?: number;
  status?: LoanStatus;
}

// ── Notification ──────────────────────────────────────────
export type NotificationType =
  | 'LOAN_APPROVED'
  | 'LOAN_REJECTED'
  | 'LOAN_FUNDED'
  | 'LOAN_ACTIVE'
  | 'REPAYMENT_RECEIVED'
  | 'LOAN_REPAID'
  | 'LOAN_LATE'
  | 'LOAN_DEFAULTED'
  | 'CREDIT_UPDATED'
  | 'AUTO_INVEST'
  | 'SYSTEM';

export interface Notification {
  id: string;
  user_id: string;
  type: NotificationType;
  title: string;
  body: string;
  loan_id?: string;
  read: boolean;
  created_at: string;
}

// ── Auto-invest preferences ────────────────────────────────
export interface AutoInvestPrefs {
  enabled: boolean;
  max_per_loan: number;
  min_credit_score: number;
  risk_tolerance: RiskCategory | 'ALL';
  max_duration_days: number;
  updated_at?: string;
}

// ── Admin analytics ────────────────────────────────────────
export interface Analytics {
  total_loans: number;
  loan_status_distribution: Record<string, number>;
  risk_distribution: Record<string, number>;
  credit_score_distribution: Record<string, number>;
  total_amount_funded: number;
  total_amount_repaid: number;
  borrower_count: number;
  lender_count: number;
  flagged_count?: number;
}

// ── Risk flag ─────────────────────────────────────────────
export interface RiskFlag {
  id: string;
  entity_type: 'loan' | 'user';
  entity_id: string;
  flag_type: string;
  reason: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  resolved: boolean;
  created_at: string;
  resolved_at?: string;
}

// ── Voice ─────────────────────────────────────────────────
export interface VoiceResponse {
  transcript: string;
  intent: string;
  entities: Record<string, unknown>;
  reply_text: string;
  audio_available: boolean;
  session_id: string;
}

// ── Export ────────────────────────────────────────────────
export interface ExportRequest {
  format: 'csv' | 'pdf';
  type: 'transactions' | 'loans' | 'repayments';
  from_date?: string;
  to_date?: string;
}

// ── API response wrappers ─────────────────────────────────
export interface FundResult {
  loan: Loan;
  funding: Funding;
}

export interface RepayResult {
  loan: Loan;
  repayment: Repayment;
  credit_score: number;
  borrowing_limit: number;
  events: string[];
}
