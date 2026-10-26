import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  User, CreditScore, Loan, Funding, Repayment, Transaction,
  Notification, AutoInvestPrefs, Analytics, RiskFlag,
  ScheduleEntry, VoiceResponse, FundResult, RepayResult,
} from '../models';

const BASE = environment.apiUrl;

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  // ── Profile ────────────────────────────────────────────
  me(): Observable<User> {
    return this.http.get<User>(`${BASE}/users/me`);
  }

  myCreditScore(): Observable<CreditScore> {
    return this.http.get<CreditScore>(`${BASE}/users/me/credit-score`);
  }

  myTransactions(): Observable<Transaction[]> {
    return this.http.get<Transaction[]>(`${BASE}/users/me/transactions`);
  }

  // ── Auto-invest preferences (lender) ──────────────────
  getAutoInvest(): Observable<AutoInvestPrefs> {
    return this.http.get<AutoInvestPrefs>(`${BASE}/users/me/auto-invest`);
  }

  updateAutoInvest(prefs: Partial<AutoInvestPrefs>): Observable<AutoInvestPrefs> {
    return this.http.put<AutoInvestPrefs>(`${BASE}/users/me/auto-invest`, prefs);
  }

  // ── Loans ──────────────────────────────────────────────
  requestLoan(payload: {
    amount: number;
    duration_days: number;
    purpose?: string;
    source?: string;
  }): Observable<Loan> {
    return this.http.post<Loan>(`${BASE}/loans`, payload);
  }

  listLoans(params: { status?: string; mine?: boolean } = {}): Observable<Loan[]> {
    let p = new HttpParams();
    if (params.status) p = p.set('status', params.status);
    if (params.mine)   p = p.set('mine', 'true');
    return this.http.get<Loan[]>(`${BASE}/loans`, { params: p });
  }

  getLoan(id: string): Observable<Loan> {
    return this.http.get<Loan>(`${BASE}/loans/${id}`);
  }

  getLoanFundings(id: string): Observable<Funding[]> {
    return this.http.get<Funding[]>(`${BASE}/loans/${id}/fundings`);
  }

  getLoanRepayments(id: string): Observable<Repayment[]> {
    return this.http.get<Repayment[]>(`${BASE}/loans/${id}/repayments`);
  }

  getLoanSchedule(id: string): Observable<ScheduleEntry[]> {
    return this.http.get<ScheduleEntry[]>(`${BASE}/loans/${id}/schedule`);
  }

  fundLoan(id: string, amount: number): Observable<FundResult> {
    return this.http.post<FundResult>(`${BASE}/loans/${id}/fund`, { amount });
  }

  repayLoan(id: string, amount: number): Observable<RepayResult> {
    return this.http.post<RepayResult>(`${BASE}/loans/${id}/repay`, { amount });
  }

  // ── Notifications ──────────────────────────────────────
  getNotifications(unreadOnly = false): Observable<Notification[]> {
    let p = new HttpParams();
    if (unreadOnly) p = p.set('unread_only', 'true');
    return this.http.get<Notification[]>(`${BASE}/notifications`, { params: p });
  }

  markNotificationRead(id: string): Observable<void> {
    return this.http.patch<void>(`${BASE}/notifications/${id}/read`, {});
  }

  markAllNotificationsRead(): Observable<void> {
    return this.http.patch<void>(`${BASE}/notifications/read-all`, {});
  }

  // ── Voice ──────────────────────────────────────────────
  voiceTurn(text: string, sessionId?: string, language: string = 'en'): Observable<VoiceResponse> {
    return this.http.post<VoiceResponse>(`${BASE}/voice/turn`, {
      text,
      session_id: sessionId,
      language,
    });
  }

  voiceAudio(audioBlob: Blob, language: string = 'en', sessionId?: string): Observable<VoiceResponse> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'speech.wav');
    formData.append('language', language);
    if (sessionId) formData.append('session_id', sessionId);
    return this.http.post<VoiceResponse>(`${BASE}/voice/audio`, formData);
  }

  transcribeWhisper(audioBlob: Blob, language: string = 'en'): Observable<{ text: string }> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'speech.wav');
    formData.append('language', language);
    return this.http.post<{ text: string }>(`${BASE}/voice/transcribe-whisper`, formData);
  }

  dtmfTurn(digit: string, sessionId?: string): Observable<VoiceResponse> {
    let p = new HttpParams();
    if (sessionId) p = p.set('session_id', sessionId);
    return this.http.post<VoiceResponse>(`${BASE}/voice/dtmf/${digit}`, {}, { params: p });
  }

  // ── Export ─────────────────────────────────────────────
  exportTransactions(format: 'csv' | 'pdf'): Observable<Blob> {
    return this.http.get(`${BASE}/users/me/export`, {
      params: new HttpParams().set('format', format).set('type', 'transactions'),
      responseType: 'blob',
    });
  }

  adminExport(format: 'csv' | 'pdf', type: string): Observable<Blob> {
    return this.http.get(`${BASE}/admin/export`, {
      params: new HttpParams().set('format', format).set('type', type),
      responseType: 'blob',
    });
  }

  // ── Admin ──────────────────────────────────────────────
  adminUsers(): Observable<User[]> {
    return this.http.get<User[]>(`${BASE}/admin/users`);
  }

  adminLoans(): Observable<Loan[]> {
    return this.http.get<Loan[]>(`${BASE}/admin/loans`);
  }

  adminRepayments(): Observable<Repayment[]> {
    return this.http.get<Repayment[]>(`${BASE}/admin/repayments`);
  }

  adminTransactions(): Observable<Transaction[]> {
    return this.http.get<Transaction[]>(`${BASE}/admin/transactions`);
  }

  adminAnalytics(): Observable<Analytics> {
    return this.http.get<Analytics>(`${BASE}/admin/analytics`);
  }

  adminFlags(): Observable<RiskFlag[]> {
    return this.http.get<RiskFlag[]>(`${BASE}/admin/flags`);
  }

  createFlag(payload: Partial<RiskFlag>): Observable<RiskFlag> {
    return this.http.post<RiskFlag>(`${BASE}/admin/flags`, payload);
  }

  // ── Enhanced Voice (Multilingual) ──────────────────────
  enhancedVoice(payload: {
    text?: string;
    audio_base64?: string;
    language?: string;
    session_id?: string;
  }): Observable<any> {
    return this.http.post<any>(`${BASE}/voice/enhanced/process`, payload);
  }

  // ── EMI Calculator ─────────────────────────────────────
  calculateEMI(payload: {
    principal: number;
    annual_rate: number;
    tenure_days: number;
    repayment_method?: string;
  }): Observable<any> {
    return this.http.post<any>(`${BASE}/emi-calculator/calculate`, payload);
  }

  compareEMI(principal: number, tenureDays: number, rates?: string): Observable<any> {
    let p = new HttpParams()
      .set('principal', principal.toString())
      .set('tenure_days', tenureDays.toString());
    if (rates) p = p.set('rates', rates);
    return this.http.get<any>(`${BASE}/emi-calculator/compare`, { params: p });
  }

  explainEMI(payload: {
    principal: number;
    annual_rate: number;
    tenure_days: number;
    repayment_method?: string;
  }, language: string = 'en'): Observable<any> {
    return this.http.post<any>(`${BASE}/emi-calculator/explain?language=${language}`, payload);
  }

  // ── AI Explainability ──────────────────────────────────
  explainCreditScore(language: string = 'en'): Observable<any> {
    return this.http.get<any>(`${BASE}/explainability/credit-score?language=${language}`);
  }

  explainLoanDecision(loanId: string, language: string = 'en'): Observable<any> {
    return this.http.get<any>(`${BASE}/explainability/loan-decision/${loanId}?language=${language}`);
  }

  getCreditFactors(language: string = 'en'): Observable<any> {
    return this.http.get<any>(`${BASE}/explainability/factors?language=${language}`);
  }

  // ── Blockchain ─────────────────────────────────────────
  getTransaction(txHash: string): Observable<any> {
    return this.http.get<any>(`${BASE}/blockchain/transaction/${txHash}`);
  }

  getLoanTransactions(loanId: string): Observable<any> {
    return this.http.get<any>(`${BASE}/blockchain/loan/${loanId}/transactions`);
  }

  verifyLoan(loanId: string): Observable<any> {
    return this.http.get<any>(`${BASE}/blockchain/verify/loan/${loanId}`);
  }

  blockchainStatus(): Observable<any> {
    return this.http.get<any>(`${BASE}/blockchain/status`);
  }

  resolveFlag(id: string): Observable<RiskFlag> {
    return this.http.patch<RiskFlag>(`${BASE}/admin/flags/${id}/resolve`, {});
  }

  // ── Wallet / Bank Balance ───────────────────────────────
  depositWallet(amount: number): Observable<{ status: string; balance: number; wallet_balance: number; field: string }> {
    return this.http.post<any>(`${BASE}/users/me/deposit`, { amount });
  }

  withdrawWallet(amount: number): Observable<{ status: string; balance: number; wallet_balance: number; field: string }> {
    return this.http.post<any>(`${BASE}/users/me/withdraw`, { amount });
  }

  // ── Admin Overdue & Fairness Testing ────────────────────
  detectOverdueLoans(): Observable<any> {
    return this.http.post<any>(`${BASE}/admin/loans/detect-overdue`, {});
  }

  getFairnessAudit(): Observable<any> {
    return this.http.get<any>(`${BASE}/admin/ml/fairness`);
  }
}

