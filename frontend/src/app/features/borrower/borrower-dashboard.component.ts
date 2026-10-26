import {
  Component, OnInit, OnDestroy, signal, computed, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule, DecimalPipe, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { RealtimeService } from '../../core/services/realtime.service';
import { NavbarComponent } from '../../shared/components/navbar.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';
import { ProgressBarComponent } from '../../shared/components/progress-bar.component';
import { LoadingSpinnerComponent } from '../../shared/components/loading-spinner.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import { ModalComponent } from '../../shared/components/modal.component';
import { EMICalculatorComponent } from '../../shared/components/emi-calculator.component';
import { CreditExplanationComponent } from '../../shared/components/credit-explanation.component';
import { BlockchainVerificationComponent } from '../../shared/components/blockchain-verification.component';
import type { Loan, CreditScore, ScheduleEntry, VoiceResponse } from '../../core/models';

type WizardStep = 1 | 2 | 3;
type RequestMode = 'wizard' | 'voice' | 'keypad';

const LOAN_TIMELINE_STEPS = [
  { status: 'REQUESTED',        label: 'Requested',         icon: '📝' },
  { status: 'CREDIT_CHECK',     label: 'Credit check',      icon: '🔍' },
  { status: 'APPROVED',         label: 'Approved',          icon: '✅' },
  { status: 'OPEN_FOR_FUNDING', label: 'Seeking funding',   icon: '💰' },
  { status: 'PARTIALLY_FUNDED', label: 'Partially funded',  icon: '⏳' },
  { status: 'FUNDED',           label: 'Fully funded',      icon: '🎉' },
  { status: 'ACTIVE',           label: 'Active (repaying)', icon: '🔄' },
  { status: 'REPAID',           label: 'Repaid',            icon: '🏆' },
];

const STATUS_ORDER: Record<string, number> = Object.fromEntries(
  LOAN_TIMELINE_STEPS.map((s, i) => [s.status, i])
);

@Component({
  selector: 'app-borrower-dashboard',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Default,
  imports: [
    CommonModule, FormsModule, RouterLink,
    NavbarComponent, StatusBadgeComponent, ProgressBarComponent,
    LoadingSpinnerComponent, EmptyStateComponent, ModalComponent,
    EMICalculatorComponent, CreditExplanationComponent, BlockchainVerificationComponent,
  ],
  template: `
    <app-navbar></app-navbar>

    <div class="page-container space-y-6 animate-fade-in-up">

      <!-- ══ TOP STATS ROW ════════════════════════════════════════════════ -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" *ngIf="!creditLoading(); else creditSkel">
        <!-- Bank / Wallet Balance -->
        <div class="stat-card glass-card-hover relative overflow-hidden flex flex-col justify-between">
          <div class="absolute inset-0 bg-gradient-to-br from-emerald-500/10 to-transparent rounded-xl2 pointer-events-none"></div>
          <div>
            <div class="flex items-center justify-between mb-1">
              <span class="stat-label">Bank & Wallet Balance</span>
              <span class="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span> Live
              </span>
            </div>
            <div class="flex items-baseline gap-1 mt-1">
              <span class="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400 tabular-nums">
                ₹{{ walletBalance() | number:'1.2-2' }}
              </span>
            </div>
            <p class="text-xs text-on-surface-muted mt-1">
              Instant loan disbursement & one-click repayment
            </p>
          </div>
          <div class="flex items-center gap-2 mt-3 pt-2 border-t border-gray-100 dark:border-white/5 relative z-10">
            <button
              (click)="openDepositModal()"
              class="flex-1 py-1 px-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-sm transition flex items-center justify-center gap-1"
            >
              <span>+</span> Deposit
            </button>
            <button
              (click)="openWithdrawModal()"
              class="flex-1 py-1 px-2 bg-gray-100 dark:bg-white/10 hover:bg-gray-200 dark:hover:bg-white/15 text-on-surface text-xs font-medium rounded-lg transition flex items-center justify-center gap-1"
            >
              <span>↑</span> Transfer
            </button>
          </div>
        </div>

        <!-- Credit score -->
        <div class="stat-card glass-card-hover relative">

          <div class="absolute inset-0 bg-gradient-to-br from-brand-500/8 to-transparent rounded-xl2 pointer-events-none"></div>
          <span class="stat-label">Credit score</span>
          <div class="flex items-end gap-2">
            <span class="text-4xl font-bold text-brand-600 dark:text-brand-400 tabular-nums">
              {{ credit()?.credit_score ?? '—' }}
            </span>
            <span class="text-sm text-on-surface-muted pb-1">/ 850</span>
          </div>
          <!-- Score bar -->
          <app-progress-bar
            [pct]="scorePercent()"
            [color]="scoreColor()"
            [height]="5"
            [subLabel]="'Min 300'"
            [subLabelRight]="'Max 850'"
          ></app-progress-bar>
          <app-status-badge [value]="credit()?.risk_category ?? ''" type="risk" [dot]="true"></app-status-badge>
          <p class="text-xs text-on-surface-muted mt-1">{{ credit()?.explanation }}</p>
          <!-- Add credit explanation button -->
          <div class="mt-2 relative z-10">
            <button
              class="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1.5 hover:bg-brand-500/10 transition font-medium"
              (click)="openCreditExplanationModal()"
            >
              <span>💡</span> Explain My Score
            </button>
          </div>
        </div>

        <!-- Borrowing limit -->
        <div class="stat-card glass-card-hover">
          <span class="stat-label">Borrowing limit</span>
          <span class="stat-value">₹{{ credit()?.borrowing_limit | number:'1.0-0' }}</span>
          <p class="text-xs text-on-surface-muted mt-1">Based on your credit score tier</p>
          <a routerLink="/borrower/loans"
             class="text-xs text-brand-600 dark:text-brand-400 font-medium hover:underline mt-auto pt-2 block">
            View credit history →
          </a>
        </div>

        <!-- Active loan quick-stat -->
        <div class="stat-card glass-card-hover">
          <span class="stat-label">Active loans</span>
          <span class="stat-value">{{ activeLoans().length }}</span>
          <div *ngIf="activeLoans().length > 0" class="mt-2 space-y-1.5">
            <div *ngFor="let l of activeLoans().slice(0,2)">
              <div class="flex justify-between text-xs text-on-surface-muted mb-0.5">
                <span>Repaid</span>
                <span>₹{{ l.amount_repaid | number:'1.0-0' }} / ₹{{ l.total_due | number:'1.0-0' }}</span>
              </div>
              <app-progress-bar
                [pct]="(l.amount_repaid / l.total_due) * 100"
                color="success"
                [height]="4"
              ></app-progress-bar>
            </div>
          </div>
          <p *ngIf="activeLoans().length === 0" class="text-xs text-on-surface-muted mt-1">
            No active loans right now.
          </p>
        </div>
      </div>

      <!-- Credit skeleton -->
      <ng-template #creditSkel>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div *ngFor="let _ of [1,2,3]" class="glass-card p-5 space-y-3">
            <div class="skeleton h-3 w-24 rounded"></div>
            <div class="skeleton h-9 w-32 rounded"></div>
            <div class="skeleton h-2 rounded"></div>
          </div>
        </div>
      </ng-template>

      <!-- ══ REQUEST A LOAN ════════════════════════════════════════════════ -->
      <div class="glass-card p-6">
        <div class="flex items-center justify-between mb-5">
          <div>
            <h2 class="section-title">🎙️ Request Loan - Voice First</h2>
            <p class="section-subtitle">Speak naturally in your language</p>
          </div>
          
          <!-- Language Selector -->
          <div class="flex gap-2">
            <button
              *ngFor="let lang of languages"
              (click)="changeLanguage(lang.code)"
              [class]="selectedLanguage() === lang.code ? 'btn-primary text-xs px-2 py-1' : 'btn-secondary text-xs px-2 py-1'">
              {{ lang.flag }} {{ lang.label }}
            </button>
          </div>
        </div>
        
        <div class="mb-4">
          <!-- Mode tabs -->
          <div class="flex gap-1 bg-gray-100 dark:bg-white/10 p-1 rounded-xl">
            <button *ngFor="let m of modes"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200"
                    [ngClass]="requestMode === m.id
                      ? 'bg-white dark:bg-white/15 shadow-soft text-on-surface'
                      : 'text-on-surface-muted hover:text-on-surface'"
                    (click)="requestMode = m.id">
              {{ m.icon }} {{ m.label }}
            </button>
          </div>
        </div>

        <!-- ─── WIZARD MODE ──────────────────────────────────────────── -->
        <div *ngIf="requestMode === 'wizard'" class="animate-fade-in">

          <!-- Step indicator -->
          <div class="flex items-center gap-0 mb-6">
            <ng-container *ngFor="let s of [1,2,3]; let last = last">
              <div [ngClass]="wizStep(s)" class="transition-all duration-300 text-sm flex-shrink-0">
                <span *ngIf="s < wizardStep()">✓</span>
                <span *ngIf="s >= wizardStep()">{{ s }}</span>
              </div>
              <div *ngIf="!last" class="flex-1 h-0.5 transition-all duration-500"
                   [ngClass]="s < wizardStep() ? 'bg-brand-500' : 'bg-gray-200 dark:bg-white/10'">
              </div>
            </ng-container>
          </div>

          <!-- Step 1 — Amount -->
          <div *ngIf="wizardStep() === 1" class="animate-fade-in-up space-y-4 max-w-sm">
            <div>
              <p class="font-semibold text-on-surface mb-1">How much do you need?</p>
              <p class="text-sm text-on-surface-muted">Your current limit is ₹{{ credit()?.borrowing_limit | number }}</p>
            </div>
            <div>
              <label class="input-label" for="w-amount">Loan amount (₹)</label>
              <input id="w-amount" type="number" class="input-field"
                     [class.input-field-error]="wTouched.amount && !amountValid"
                     [(ngModel)]="wAmount" name="w-amount" min="1" step="100"
                     (blur)="wTouched.amount = true" />
              <p *ngIf="wTouched.amount && wAmount <= 0" class="input-error">
                <span>⚠</span> Enter a valid amount
              </p>
              <p *ngIf="wTouched.amount && wAmount > (credit()?.borrowing_limit ?? 0)" class="input-error">
                <span>⚠</span> Exceeds your borrowing limit of ₹{{ credit()?.borrowing_limit | number }}
              </p>
            </div>
            <!-- Quick-amount chips -->
            <div class="flex flex-wrap gap-2">
              <button *ngFor="let a of quickAmounts"
                      type="button"
                      class="px-3 py-1.5 rounded-xl border text-xs font-medium transition-all duration-200"
                      [ngClass]="wAmount === a
                        ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
                        : 'border-gray-200 dark:border-white/10 text-on-surface-muted hover:border-brand-300'"
                      (click)="wAmount = a">
                ₹{{ a | number }}
              </button>
            </div>
            <button class="btn-primary" (click)="wizNext()">Continue →</button>
          </div>

          <!-- Step 2 — Duration & purpose -->
          <div *ngIf="wizardStep() === 2" class="animate-fade-in-up space-y-4 max-w-sm">
            <p class="font-semibold text-on-surface">Loan details</p>
            <div>
              <label class="input-label">Duration</label>
              <div class="grid grid-cols-3 gap-2">
                <button *ngFor="let d of durationOptions"
                        type="button"
                        class="p-3 rounded-xl border text-center transition-all duration-200"
                        [ngClass]="wDuration === d.days
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
                          : 'border-gray-200 dark:border-white/10 text-on-surface-muted hover:border-brand-300'"
                        (click)="wDuration = d.days">
                  <p class="font-semibold">{{ d.days }}d</p>
                  <p class="text-xs opacity-70">{{ d.label }}</p>
                </button>
              </div>
            </div>
            <div>
              <label class="input-label" for="w-purpose">Purpose <span class="text-on-surface-muted font-normal">(optional)</span></label>
              <input id="w-purpose" type="text" class="input-field"
                     [(ngModel)]="wPurpose" name="w-purpose"
                     placeholder="e.g. Medical, Education, Business" />
            </div>
            <!-- Summary preview -->
            <div class="bg-brand-50 dark:bg-brand-500/10 rounded-xl p-4 space-y-2 text-sm">
              <div class="flex justify-between"><span class="text-on-surface-muted">Principal</span><span class="font-semibold">₹{{ wAmount | number }}</span></div>
              <div class="flex justify-between"><span class="text-on-surface-muted">Interest (10%)</span><span>₹{{ (wAmount * 0.1) | number:'1.2-2' }}</span></div>
              <div class="flex justify-between border-t border-brand-200 dark:border-brand-500/20 pt-2 mt-1">
                <span class="font-medium">Total due</span><span class="font-bold">₹{{ (wAmount * 1.1) | number:'1.2-2' }}</span>
              </div>
            </div>

            <!-- EMI Calculator -->
            <div class="border-t border-gray-200 dark:border-white/10 pt-4 mt-4">
              <app-emi-calculator
                [lockPrincipal]="true"
                [lockDuration]="true"
              ></app-emi-calculator>
            </div>

            <div class="flex gap-3">
              <button class="btn-secondary flex-1" (click)="wizardStep.set(1)">← Back</button>
              <button class="btn-primary flex-1" (click)="wizNext()">Continue →</button>
            </div>
          </div>

          <!-- Step 3 — Confirm & submit -->
          <div *ngIf="wizardStep() === 3" class="animate-fade-in-up space-y-4 max-w-sm">
            <p class="font-semibold text-on-surface">Confirm your request</p>
            <div class="glass-panel p-4 space-y-3 text-sm">
              <div class="flex justify-between"><span class="text-on-surface-muted">Amount</span><span class="font-bold text-brand-600 dark:text-brand-400">₹{{ wAmount | number }}</span></div>
              <div class="flex justify-between"><span class="text-on-surface-muted">Duration</span><span>{{ wDuration }} days</span></div>
              <div class="flex justify-between"><span class="text-on-surface-muted">Purpose</span><span>{{ wPurpose || '—' }}</span></div>
              <div class="flex justify-between"><span class="text-on-surface-muted">Total repayable</span><span class="font-semibold">₹{{ (wAmount * 1.1) | number:'1.2-2' }}</span></div>
            </div>
            <div class="flex gap-3">
              <button class="btn-secondary flex-1" (click)="wizardStep.set(2)">← Back</button>
              <button class="btn-primary flex-1 py-3" (click)="submitLoan()" [disabled]="submitting()">
                <app-spinner *ngIf="submitting()" mode="inline" size="sm"></app-spinner>
                {{ submitting() ? 'Submitting…' : '🚀 Submit request' }}
              </button>
            </div>
          </div>
        </div>

        <!-- ─── VOICE MODE (PRIMARY) ───────────────────────────────────────────── -->
        <div *ngIf="requestMode === 'voice'" class="animate-fade-in space-y-4">
          
          <!-- 📞 LIVE CALL MODE (HANDS-FREE CONTINUOUS CONVERSATION) -->
          <div *ngIf="!isCallActive()" class="rounded-3xl p-6 bg-gradient-to-r from-emerald-600 via-teal-700 to-cyan-800 text-white shadow-xl flex flex-col sm:flex-row items-center justify-between gap-4">
            <div class="space-y-1 text-center sm:text-left">
              <div class="flex items-center justify-center sm:justify-start gap-2">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-2xs font-bold uppercase tracking-wider bg-white/25 text-white backdrop-blur-sm">
                  ⚡ Autonomous Voice Agent
                </span>
                <span class="text-xs text-white/90">Whisper + Groq AI (Free Tier)</span>
              </div>
              <h3 class="text-xl font-bold flex items-center justify-center sm:justify-start gap-2">
                <span>📞</span>
                <span>Live Voice Call Mode</span>
              </h3>
              <p class="text-xs text-emerald-100 max-w-lg">
                Talk continuously like on a live phone call! Say "I want to repay my loan", "Check my loan status", or "I need a loan of 5000" — fully hands-free!
              </p>
            </div>
            <button
              type="button"
              (click)="startLiveCall()"
              class="px-6 py-3.5 rounded-full bg-white text-emerald-800 font-bold shadow-lg hover:bg-emerald-50 hover:scale-105 active:scale-95 transition-all flex items-center gap-2 text-sm shrink-0">
              <span class="text-xl">📞</span>
              <span>Start Voice Call</span>
            </button>
          </div>

          <!-- 🟢 LIVE CALL ACTIVE HUD (FULL DUPLEX) -->
          <div *ngIf="isCallActive()" class="rounded-3xl p-6 bg-gradient-to-br from-slate-950 via-gray-900 to-emerald-950 text-white border-2 border-emerald-500/60 shadow-2xl relative overflow-hidden space-y-5 animate-fade-in">
            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
              <div class="flex items-center gap-3">
                <div class="relative">
                  <div class="w-12 h-12 rounded-full bg-emerald-500/20 border-2 border-emerald-400 flex items-center justify-center text-2xl shadow-inner">
                    🤖
                  </div>
                  <span class="absolute -top-1 -right-1 flex h-4 w-4">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-4 w-4 bg-emerald-500"></span>
                  </span>
                </div>
                <div>
                  <h4 class="font-bold text-base flex items-center gap-2">
                    <span>FinLend Live Voice Agent</span>
                    <span class="text-2xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      ON CALL
                    </span>
                  </h4>
                  <p class="text-xs text-slate-400 font-mono flex items-center gap-1.5">
                    <span>⏱️ Call Duration:</span>
                    <span class="text-emerald-400 font-bold">{{ callDuration() }}</span>
                  </p>
                </div>
              </div>

              <!-- Status pill -->
              <div class="flex items-center gap-2">
                <span *ngIf="callState() === 'listening'" class="px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-2 animate-pulse">
                  <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                  🎙️ Listening (Speak now)
                </span>
                <span *ngIf="callState() === 'processing'" class="px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full bg-amber-400 animate-spin"></span>
                  🧠 Agent Executing Action...
                </span>
                <span *ngIf="callState() === 'speaking'" class="px-3 py-1.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                  🗣️ Agent Speaking...
                </span>
              </div>
            </div>

            <!-- Frequency Waveform Animation -->
            <div class="flex items-center justify-center gap-2 py-2">
              <span class="w-2 bg-emerald-400 rounded-full transition-all duration-300" [ngClass]="callState() === 'listening' || callState() === 'speaking' ? 'h-10 animate-bounce' : 'h-3'"></span>
              <span class="w-2 bg-teal-400 rounded-full transition-all duration-300" [ngClass]="callState() === 'listening' || callState() === 'speaking' ? 'h-16 animate-bounce [animation-delay:0.15s]' : 'h-4'"></span>
              <span class="w-2 bg-cyan-400 rounded-full transition-all duration-300" [ngClass]="callState() === 'listening' || callState() === 'speaking' ? 'h-20 animate-bounce [animation-delay:0.3s]' : 'h-6'"></span>
              <span class="w-2 bg-emerald-300 rounded-full transition-all duration-300" [ngClass]="callState() === 'listening' || callState() === 'speaking' ? 'h-14 animate-bounce [animation-delay:0.1s]' : 'h-4'"></span>
              <span class="w-2 bg-teal-300 rounded-full transition-all duration-300" [ngClass]="callState() === 'listening' || callState() === 'speaking' ? 'h-18 animate-bounce [animation-delay:0.25s]' : 'h-5'"></span>
              <span class="w-2 bg-cyan-300 rounded-full transition-all duration-300" [ngClass]="callState() === 'listening' || callState() === 'speaking' ? 'h-12 animate-bounce [animation-delay:0.4s]' : 'h-3'"></span>
            </div>

            <!-- In-Call Real-time Speech Subtitles / Dialogue -->
            <div class="bg-black/50 rounded-2xl p-4 border border-white/10 min-h-[75px] flex items-center justify-center text-center">
              <p *ngIf="liveSpeechText()" class="text-sm font-semibold text-emerald-300 animate-fade-in">
                "{{ liveSpeechText() }}"
              </p>
              <p *ngIf="!liveSpeechText() && callState() === 'listening'" class="text-xs text-slate-400 italic">
                Speak naturally... e.g. "I want to repay my loan", "Check my status", or "Need a loan of 5000"
              </p>
              <p *ngIf="callState() === 'speaking'" class="text-sm font-medium text-slate-100">
                🤖 {{ currentSpeechResponse() }}
              </p>
              <p *ngIf="callState() === 'processing'" class="text-xs text-amber-300 font-mono">
                ⚡ Checking loan database & blockchain...
              </p>
            </div>

            <!-- In-Call Action Bar -->
            <div class="flex items-center justify-center gap-4 pt-1">
              <button
                type="button"
                (click)="toggleMute()"
                class="px-5 py-2.5 rounded-full bg-slate-800 text-slate-200 hover:bg-slate-700 text-xs font-semibold flex items-center gap-2 border border-slate-700 transition-all">
                <span>{{ isMuted() ? '🔇 Unmute Mic' : '🎙️ Mute Mic' }}</span>
              </button>
              <button
                type="button"
                (click)="endLiveCall()"
                class="px-6 py-2.5 rounded-full bg-red-600 hover:bg-red-700 text-white text-xs font-bold shadow-xl hover:scale-105 active:scale-95 transition-all flex items-center gap-2">
                <span>🔴 Hang Up / End Call</span>
              </button>
            </div>
          </div>

          <!-- Voice Instructions with Examples -->
          <div class="glass-panel p-5 bg-gradient-to-br from-brand/10 to-brand/5">
            <h3 class="text-lg font-semibold text-on-surface mb-2 flex items-center gap-2">
              <span class="text-2xl">🎤</span>
              Autonomous Voice Assistant
            </h3>
            <p class="text-sm text-on-surface-muted mb-3">
              Ask anything — Repay loans, request funds, check balances, or calculate EMIs in {{ selectedLanguage() === 'hi' ? 'हिंदी' : selectedLanguage() === 'te' ? 'తెలుగు' : 'English' }}.
            </p>
            
            <!-- Example Prompts -->
            <div class="bg-surface/50 rounded-lg p-3 text-xs space-y-1">
              <p class="font-medium text-on-surface mb-2">Examples:</p>
              <p *ngIf="selectedLanguage() === 'en'" class="text-on-surface-muted">
                • "I want to repay my loan 500 rupees"<br>
                • "Pay my active loan in full"<br>
                • "What is my loan status and due date?"<br>
                • "I need a loan of 5000 rupees for 60 days"<br>
                • "Check my credit score and borrowing limit"
              </p>
              <p *ngIf="selectedLanguage() === 'hi'" class="text-on-surface-muted">
                • "मुझे 500 रुपये का लोन चुकाना है"<br>
                • "मेरा एक्टिव लोन पूरा भरें"<br>
                • "मेरा लोन स्टेटस क्या है?"<br>
                • "मुझे 5000 रुपये का 60 दिन का लोन चाहिए"<br>
                • "मेरा क्रेडिट स्कोर क्या है?"
              </p>
              <p *ngIf="selectedLanguage() === 'te'" class="text-on-surface-muted">
                • "నా లోన్ 500 రూపాయలు కట్టాలి"<br>
                • "నా పూర్తి లోన్ చెల్లించండి"<br>
                • "నా లోన్ స్టేటస్ ఏమిటి?"<br>
                • "నాకు 5000 రూపాయల 60 రోజుల లోన్ కావాలి"<br>
                • "నా క్రెడిట్ స్కోర్ ఎంత?"
              </p>
            </div>
          </div>

          <!-- Voice Input Controls -->
          <div class="glass-panel p-6 space-y-5">
            
            <!-- Large Microphone Button with Animated Waveform Visualizer -->
            <div class="flex flex-col items-center justify-center gap-3">
              <div class="relative flex items-center justify-center">
                <!-- Glowing pulsating ring when listening -->
                <div *ngIf="listening()" class="absolute w-32 h-32 rounded-full bg-red-500/20 animate-ping"></div>
                <div *ngIf="listening()" class="absolute w-28 h-28 rounded-full bg-red-500/30 animate-pulse"></div>

                <button
                  *ngIf="!listening()"
                  (click)="startListening()"
                  class="relative z-10 w-24 h-24 rounded-full bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-2xl hover:scale-105 active:scale-95 transition-all flex items-center justify-center"
                  title="Click to speak">
                  <span class="text-5xl">🎙️</span>
                </button>
                
                <button
                  *ngIf="listening()"
                  (click)="stopListening()"
                  class="relative z-10 w-24 h-24 rounded-full bg-red-600 text-white shadow-2xl animate-pulse flex items-center justify-center"
                  title="Click to stop">
                  <span class="text-5xl">⏸️</span>
                </button>
              </div>

              <!-- Animated Frequency Waveform Bars -->
              <div *ngIf="listening()" class="flex items-center justify-center gap-1.5 h-10 my-1">
                <span class="w-1.5 bg-red-500 rounded-full animate-bounce [animation-delay:0.1s] h-5"></span>
                <span class="w-1.5 bg-brand-500 rounded-full animate-bounce [animation-delay:0.25s] h-9"></span>
                <span class="w-1.5 bg-red-500 rounded-full animate-bounce [animation-delay:0.4s] h-10"></span>
                <span class="w-1.5 bg-brand-500 rounded-full animate-bounce [animation-delay:0.15s] h-7"></span>
                <span class="w-1.5 bg-red-500 rounded-full animate-bounce [animation-delay:0.3s] h-9"></span>
                <span class="w-1.5 bg-brand-500 rounded-full animate-bounce [animation-delay:0.45s] h-6"></span>
              </div>
              
              <p class="text-sm font-medium text-center" [class.text-red-600]="listening()" [class.animate-pulse]="listening()">
                {{ listening() ? '🔴 Listening... Speak loan amount & duration!' : 'Tap microphone to speak or pick a quick command below' }}
              </p>
            </div>

            <!-- Interactive Quick-Prompt Suggestion Chips -->
            <div class="space-y-1.5 pt-1">
              <span class="text-xs font-semibold text-on-surface-muted flex items-center gap-1.5">
                <span>⚡</span>
                <span>{{ selectedLanguage() === 'hi' ? 'तुरंत पूछें (एक क्लिक में):' : selectedLanguage() === 'te' ? 'త్వరిత సూచనలు (ఒక క్లిక్):' : 'Quick Voice Commands (1-click):' }}</span>
              </span>
              <div class="flex flex-wrap gap-2">
                <button *ngFor="let qp of quickPrompts()"
                        type="button"
                        (click)="selectQuickPrompt(qp)"
                        class="px-3 py-1.5 rounded-xl border border-brand-200 dark:border-brand-800/40 bg-brand-50/70 dark:bg-brand-500/10 text-brand-700 dark:text-brand-300 hover:bg-brand-100 dark:hover:bg-brand-500/20 text-xs font-medium hover:scale-[1.02] active:scale-95 transition-all shadow-sm">
                  💬 {{ qp }}
                </button>
              </div>
            </div>

            <!-- Text Input (Fallback/Alternative) -->
            <div class="relative">
              <textarea
                class="input-field resize-none text-base"
                rows="3"
                [(ngModel)]="voiceText"
                name="voiceText"
                [placeholder]="getPlaceholder()"
              ></textarea>
              
              <button 
                *ngIf="voiceText.trim()"
                (click)="voiceText = ''"
                class="absolute top-2 right-2 text-on-surface-muted hover:text-on-surface text-lg"
                title="Clear">
                ✕
              </button>
            </div>
            
            <!-- Send Button -->
            <button 
              class="btn-primary w-full text-lg py-3.5 font-semibold shadow-md hover:shadow-lg transition-all" 
              (click)="sendVoiceText()" 
              [disabled]="submitting() || !voiceText.trim()">
              <app-spinner *ngIf="submitting()" mode="inline" size="sm"></app-spinner>
              <span *ngIf="!submitting()">{{ selectedLanguage() === 'hi' ? '🗣️ भेजें' : selectedLanguage() === 'te' ? '🗣️ పంపండి' : '🗣️ Send Message' }}</span>
            </button>
          </div>

          <!-- Interactive Chat Thread / Conversation History -->
          <div *ngIf="chatHistory().length" class="glass-panel p-5 space-y-4 animate-fade-in border border-brand-500/20">
            <div class="flex items-center justify-between pb-2 border-b border-gray-100 dark:border-white/10">
              <h3 class="font-semibold text-sm flex items-center gap-2 text-on-surface">
                <span>💬</span>
                <span>Voice Conversation History</span>
                <span class="badge badge-brand text-2xs">{{ chatHistory().length }} turns</span>
              </h3>
              <div class="flex items-center gap-2">
                <button (click)="stopSpeaking()" class="btn-ghost text-2xs text-on-surface-muted hover:text-on-surface flex items-center gap-1">
                  🔇 Stop Audio
                </button>
                <button (click)="chatHistory.set([])" class="btn-ghost text-2xs text-on-surface-muted hover:text-danger-600">
                  Clear
                </button>
              </div>
            </div>

            <div class="space-y-3 max-h-[380px] overflow-y-auto pr-1 scrollbar-thin">
              <div *ngFor="let turn of chatHistory()"
                   [ngClass]="turn.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
                <!-- User bubble -->
                <div *ngIf="turn.role === 'user'"
                     class="max-w-[85%] rounded-2xl rounded-br-none bg-brand-600 text-white p-3.5 shadow-md space-y-1">
                  <div class="flex items-center gap-1.5 text-xs text-white/80">
                    <span>🗣️ You</span>
                    <span>·</span>
                    <span class="text-2xs">{{ turn.time }}</span>
                  </div>
                  <p class="text-sm font-medium">{{ turn.text }}</p>
                </div>

                <!-- Assistant bubble -->
                <div *ngIf="turn.role === 'assistant'"
                     class="max-w-[85%] rounded-2xl rounded-bl-none bg-white dark:bg-white/10 border border-gray-200 dark:border-white/10 p-4 shadow-md space-y-2 text-on-surface">
                  <div class="flex items-center justify-between gap-2">
                    <div class="flex items-center gap-1.5 text-xs font-semibold text-brand-600 dark:text-brand-400">
                      <span>🤖 FinLend Assistant</span>
                      <span>·</span>
                      <span class="text-2xs text-on-surface-muted font-normal">{{ turn.time }}</span>
                    </div>
                    <button (click)="speakResponse(turn.text, selectedLanguage())"
                            class="text-xs text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
                            title="Listen again">
                      🔊 Listen
                    </button>
                  </div>
                  <p class="text-sm leading-relaxed">{{ turn.text }}</p>
                  
                  <div *ngIf="turn.intent || turn.amount || turn.days" class="flex flex-wrap gap-2 pt-1 border-t border-gray-100 dark:border-white/10 text-2xs text-on-surface-muted">
                    <span *ngIf="turn.intent" class="badge bg-brand-100 dark:bg-brand-500/20 text-brand-700 dark:text-brand-300">
                      {{ turn.intent }}
                    </span>
                    <span *ngIf="turn.amount" class="badge bg-success-100 dark:bg-success-500/20 text-success-700 dark:text-success-300">
                      💰 ₹{{ turn.amount | number }}
                    </span>
                    <span *ngIf="turn.days" class="badge bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300">
                      📅 {{ turn.days }} days
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ─── KEYPAD / DTMF MODE ───────────────────────────────────── -->
        <div *ngIf="requestMode === 'keypad'" class="animate-fade-in space-y-4">
          <p class="text-sm text-on-surface-muted">
            Simulates a feature-phone DTMF IVR menu.
          </p>
          <div class="flex gap-8 flex-wrap">
            <div class="grid grid-cols-3 gap-2 max-w-[200px]">
              <button *ngFor="let d of dtmfKeys"
                      class="h-12 rounded-xl font-mono font-bold text-lg
                             bg-white/60 dark:bg-white/10 border border-gray-200 dark:border-white/10
                             hover:bg-brand-50 dark:hover:bg-brand-500/15 hover:border-brand-300
                             active:scale-90 transition-all duration-150"
                      (click)="pressDtmf(d)">
                {{ d }}
              </button>
            </div>
            <div class="text-xs text-on-surface-muted space-y-1.5 pt-1">
              <p class="font-semibold text-on-surface mb-2">Menu options</p>
              <p>1 — Check balance</p>
              <p>2 — Credit score</p>
              <p>3 — Loan status</p>
              <p>4 — Request loan</p>
              <p>5 — Repayment schedule</p>
              <p>6 — Make repayment</p>
              <p>0 — Help</p>
            </div>
          </div>

          <div *ngIf="voiceReply()" class="glass-panel p-4 text-sm animate-fade-in max-w-lg">
            <p class="font-medium text-on-surface mb-1">🤖 {{ voiceReply()!.reply_text }}</p>
            <p class="text-xs text-on-surface-muted">Intent: {{ voiceReply()!.intent }}</p>
          </div>
        </div>
      </div>

      <!-- ══ MY LOANS ══════════════════════════════════════════════════════ -->
      <div class="glass-card p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h2 class="section-title">My loans</h2>
            <p class="section-subtitle">{{ loans().length }} total · {{ activeLoans().length }} active</p>
          </div>
          <button class="btn-ghost text-xs" (click)="refresh()">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none"
                 viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581
                       m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            Refresh
          </button>
        </div>

        <app-spinner *ngIf="loansLoading()" mode="page" label="Loading loans…"></app-spinner>

        <ng-container *ngIf="!loansLoading()">
          <app-empty-state *ngIf="!loans().length"
            icon="📋" title="No loans yet"
            subtitle="Use the form above to request your first loan.">
          </app-empty-state>

          <div *ngIf="loans().length" class="space-y-4">
            <div *ngFor="let l of loans()" class="glass-panel p-4 glass-card-hover">
              <!-- Loan header -->
              <div class="flex flex-wrap items-start justify-between gap-3 mb-3">
                <div>
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-bold text-xl text-on-surface">₹{{ l.amount | number }}</span>
                    <app-status-badge [value]="l.status" type="status" [dot]="true"></app-status-badge>
                    <app-status-badge *ngIf="l.risk_category" [value]="l.risk_category" type="risk"></app-status-badge>
                  </div>
                  <p class="text-xs text-on-surface-muted mt-0.5">
                    {{ l.purpose || 'General purpose' }} · {{ l.duration_days }}d · 10% interest
                  </p>
                </div>
                <div class="flex gap-2 flex-shrink-0 flex-wrap">
                  <button
                    *ngIf="l.status === 'ACTIVE' || l.status === 'LATE'"
                    class="btn-primary text-xs px-3 py-1.5"
                    (click)="openRepayModal(l)"
                  >💸 Repay</button>
                  <button
                    *ngIf="l.status === 'ACTIVE' || l.status === 'LATE'"
                    class="btn-secondary text-xs px-3 py-1.5"
                    (click)="openScheduleModal(l)"
                  >📅 Schedule</button>
                  <button
                    class="btn-secondary text-xs px-3 py-1.5"
                    (click)="openBlockchainModal(l)"
                  >🔗 On-Chain Proof</button>
                </div>
              </div>

              <!-- Loan lifecycle timeline (collapsed for non-active/terminal loans) -->
              <div *ngIf="showTimeline(l)" class="mb-3">
                <div class="flex items-center gap-0 overflow-x-auto pb-1 scrollbar-thin">
                  <ng-container *ngFor="let ts of timelineSteps(l); let last = last">
                    <div class="flex flex-col items-center gap-1 flex-shrink-0 min-w-[52px]">
                      <div [ngClass]="ts.dotClass" class="transition-all duration-300"></div>
                      <span class="text-2xs text-center text-on-surface-muted max-w-[52px] leading-tight">
                        {{ ts.label }}
                      </span>
                    </div>
                    <div *ngIf="!last"
                         class="timeline-line flex-1 min-w-[16px]"
                         [ngClass]="ts.lineClass">
                    </div>
                  </ng-container>
                </div>
              </div>

              <!-- Progress bars -->
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <app-progress-bar
                  *ngIf="l.status !== 'REJECTED'"
                  [pct]="(l.amount_funded / l.amount) * 100"
                  color="brand"
                  [height]="5"
                  [showLabel]="true"
                  label="Funded"
                  [subLabel]="'₹' + (l.amount_funded | number:'1.0-0')"
                  [subLabelRight]="'of ₹' + (l.amount | number:'1.0-0')"
                ></app-progress-bar>
                <app-progress-bar
                  *ngIf="l.status === 'ACTIVE' || l.status === 'LATE' || l.status === 'REPAID'"
                  [pct]="(l.amount_repaid / l.total_due) * 100"
                  [color]="l.status === 'LATE' ? 'warning' : 'success'"
                  [height]="5"
                  [showLabel]="true"
                  label="Repaid"
                  [subLabel]="'₹' + (l.amount_repaid | number:'1.0-0')"
                  [subLabelRight]="'of ₹' + (l.total_due | number:'1.2-2')"
                ></app-progress-bar>
              </div>

              <!-- Footer meta -->
              <div class="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-gray-100 dark:border-white/5 text-xs text-on-surface-muted">
                <span>Created {{ l.created_at | date:'mediumDate' }}</span>
                <span *ngIf="l.due_date">· Due <strong [class.text-danger-600]="isOverdue(l)">{{ l.due_date | date:'mediumDate' }}</strong></span>
                <span *ngIf="l.status === 'REJECTED'" class="text-danger-600 dark:text-danger-400">
                  Rejected: {{ l.rejection_reason }}
                </span>
              </div>
            </div>
          </div>
        </ng-container>
      </div>
    </div>

    <!-- ══ REPAYMENT MODAL ═══════════════════════════════════════════════ -->
    <app-modal
      [open]="repayModal()"
      title="Make a repayment"
      [subtitle]="repayingLoan() ? 'Loan · ₹' + repayingLoan()!.amount : ''"
      (close)="closeRepayModal()"
    >
      <div *ngIf="repayingLoan()" class="space-y-4">
        <!-- Repayment summary -->
        <div class="glass-panel p-4 space-y-2 text-sm">
          <div class="flex justify-between">
            <span class="text-on-surface-muted">Total due</span>
            <span class="font-bold">₹{{ repayingLoan()!.total_due | number:'1.2-2' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-on-surface-muted">Already repaid</span>
            <span>₹{{ repayingLoan()!.amount_repaid | number:'1.2-2' }}</span>
          </div>
          <div class="flex justify-between border-t border-gray-200 dark:border-white/10 pt-2">
            <span class="font-medium">Remaining</span>
            <span class="font-bold text-brand-600 dark:text-brand-400">
              ₹{{ remaining() | number:'1.2-2' }}
            </span>
          </div>
          <div class="flex justify-between items-center bg-gray-50 dark:bg-white/5 p-2.5 rounded-lg mt-2 text-xs border border-gray-200 dark:border-white/10">
            <span class="text-on-surface-muted">Your Bank Wallet Balance:</span>
            <span class="font-bold text-sm" [class.text-emerald-600]="walletBalance() >= repayAmt" [class.text-danger-600]="walletBalance() < repayAmt">
              ₹{{ walletBalance() | number:'1.2-2' }}
            </span>
          </div>
        </div>

        <!-- Warning if wallet balance is less than repayAmt -->
        <div *ngIf="walletBalance() < repayAmt" class="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-700 dark:text-amber-300 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span>⚠️</span>
            <span>Balance insufficient (Need ₹{{ repayAmt | number:'1.0-0' }})</span>
          </div>
          <button type="button" (click)="closeRepayModal(); openDepositModal()" class="text-brand-600 dark:text-brand-400 font-bold underline hover:no-underline ml-2">
            + Deposit Now
          </button>
        </div>

        <!-- Amount input -->
        <div>
          <label class="input-label" for="repay-amt">Repayment amount (₹)</label>
          <input id="repay-amt" type="number" class="input-field"
                 [class.input-field-error]="repayTouched && (!repayAmtValid || walletBalance() < repayAmt)"
                 [(ngModel)]="repayAmt" name="repay-amt"
                 [max]="remaining()"
                 (blur)="repayTouched = true"
                 placeholder="Enter amount" />
          <p *ngIf="repayTouched && repayAmt <= 0" class="input-error"><span>⚠</span> Amount must be positive</p>
          <p *ngIf="repayTouched && repayAmt > remaining() + 0.001" class="input-error">
            <span>⚠</span> Cannot exceed remaining amount (₹{{ remaining() | number:'1.2-2' }})
          </p>
          <p *ngIf="repayTouched && walletBalance() < repayAmt" class="input-error">
            <span>⚠</span> Insufficient wallet balance. Please deposit funds first.
          </p>
        </div>

        <!-- Quick-fill buttons -->
        <div class="flex gap-2 flex-wrap">
          <button type="button" class="btn-secondary text-xs px-3 py-1.5"
                  (click)="repayAmt = remaining()">Pay all</button>
          <button type="button" class="btn-secondary text-xs px-3 py-1.5"
                  (click)="repayAmt = round(remaining() * 0.5)">50%</button>
          <button type="button" class="btn-secondary text-xs px-3 py-1.5"
                  (click)="repayAmt = round(remaining() * 0.25)">25%</button>
        </div>

        <div class="flex gap-3 pt-2">
          <button class="btn-secondary flex-1" (click)="closeRepayModal()">Cancel</button>
          <button class="btn-primary flex-1 py-3" (click)="submitRepayment()" [disabled]="submitting() || walletBalance() < repayAmt">
            <app-spinner *ngIf="submitting()" mode="inline" size="sm"></app-spinner>
            {{ submitting() ? 'Processing…' : '💸 Confirm payment' }}
          </button>
        </div>
      </div>
    </app-modal>


    <!-- ══ SCHEDULE MODAL ════════════════════════════════════════════════ -->
    <app-modal
      [open]="scheduleModal()"
      title="Repayment schedule"
      [subtitle]="scheduleLoan() ? 'Loan #' + scheduleLoan()!.id.slice(-6) : ''"
      (close)="scheduleModal.set(false)"
    >
      <div>
        <app-spinner *ngIf="scheduleLoading()" mode="page" label="Loading schedule…"></app-spinner>

        <app-empty-state *ngIf="!scheduleLoading() && !schedule().length"
          icon="📅" title="No schedule available"
          subtitle="Schedule is generated once the loan is active.">
        </app-empty-state>

        <div *ngIf="!scheduleLoading() && schedule().length" class="space-y-2 max-h-80 overflow-y-auto scrollbar-thin pr-1">
          <div *ngFor="let entry of schedule()"
               class="flex items-center justify-between p-3 rounded-xl border transition-all"
               [ngClass]="{
                 'border-success-500/30 bg-success-50 dark:bg-success-500/10': entry.status === 'paid',
                 'border-danger-500/30 bg-danger-50 dark:bg-danger-500/10': entry.status === 'overdue',
                 'border-brand-200 dark:border-brand-500/20 bg-brand-50 dark:bg-brand-500/8': entry.status === 'due',
                 'border-gray-200 dark:border-white/10': entry.status === 'upcoming'
               }">
            <div class="flex items-center gap-3">
              <span class="text-lg">
                {{ entry.status === 'paid' ? '✅' : entry.status === 'overdue' ? '🔴' : entry.status === 'due' ? '🟡' : '⬜' }}
              </span>
              <div>
                <p class="text-sm font-medium">Payment {{ entry.payment_number }}</p>
                <p class="text-xs text-on-surface-muted">Due {{ entry.due_date | date:'mediumDate' }}</p>
              </div>
            </div>
            <div class="text-right">
              <p class="font-semibold text-sm">₹{{ entry.total | number:'1.2-2' }}</p>
              <p class="text-xs text-on-surface-muted capitalize">{{ entry.status }}</p>
            </div>
          </div>
        </div>
      </div>
    </app-modal>

    <!-- ══ BLOCKCHAIN VERIFICATION MODAL ═══════════════════════════════ -->
    <app-modal
      [open]="blockchainModal()"
      title="Blockchain Verification & Cryptographic Proof"
      [subtitle]="blockchainLoan() ? 'Loan #' + blockchainLoan()!.id.slice(-6) + ' · ₹' + (blockchainLoan()!.amount | number) : ''"
      (close)="closeBlockchainModal()"
    >
      <div *ngIf="blockchainLoan()" class="p-2">
        <app-blockchain-verification [loanId]="blockchainLoan()!.id"></app-blockchain-verification>
      </div>
    </app-modal>

    <!-- ══ WALLET DEPOSIT MODAL ═════════════════════════════════════ -->
    <app-modal
      [open]="depositModal()"

      title="Deposit Funds to Bank Wallet"
      subtitle="Add funds to your FinLend digital bank account for repayments"
      (close)="closeDepositModal()"
    >
      <div class="space-y-4">
        <div>
          <label class="input-label" for="deposit-amt">Deposit Amount (₹)</label>
          <div class="relative mt-1">
            <span class="absolute inset-y-0 left-0 pl-3 flex items-center text-on-surface-muted">₹</span>
            <input
              id="deposit-amt"
              type="number"
              class="input-field pl-7"
              [(ngModel)]="depositAmt"
              min="100"
              max="100000"
              placeholder="e.g. 2000"
            />
          </div>
        </div>
        <div class="flex gap-2">
          <button (click)="depositAmt = 1000" class="btn-xs border border-gray-200 dark:border-white/10 rounded px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-white/5">₹1,000</button>
          <button (click)="depositAmt = 2500" class="btn-xs border border-gray-200 dark:border-white/10 rounded px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-white/5">₹2,500</button>
          <button (click)="depositAmt = 5000" class="btn-xs border border-gray-200 dark:border-white/10 rounded px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-white/5">₹5,000</button>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button (click)="closeDepositModal()" class="btn-secondary">Cancel</button>
          <button (click)="submitDeposit()" [disabled]="depositAmt <= 0 || walletActionLoading()" class="btn-primary">
            {{ walletActionLoading() ? 'Depositing...' : 'Confirm Deposit' }}
          </button>
        </div>
      </div>
    </app-modal>

    <!-- ══ WALLET WITHDRAW MODAL ════════════════════════════════════════ -->
    <app-modal
      [open]="withdrawModal()"
      title="Withdraw from Bank Wallet"
      subtitle="Transfer funds from your wallet to external bank account"
      (close)="closeWithdrawModal()"
    >
      <div class="space-y-4">
        <div class="glass-panel p-3 text-sm flex justify-between">
          <span class="text-on-surface-muted">Available Balance:</span>
          <span class="font-bold text-emerald-600">₹{{ walletBalance() | number:'1.2-2' }}</span>
        </div>
        <div>
          <label class="input-label" for="withdraw-amt">Withdraw Amount (₹)</label>
          <div class="relative mt-1">
            <span class="absolute inset-y-0 left-0 pl-3 flex items-center text-on-surface-muted">₹</span>
            <input
              id="withdraw-amt"
              type="number"
              class="input-field pl-7"
              [(ngModel)]="withdrawAmt"
              min="100"
              [max]="walletBalance()"
              placeholder="Amount to withdraw"
            />
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button (click)="closeWithdrawModal()" class="btn-secondary">Cancel</button>
          <button (click)="submitWithdraw()" [disabled]="withdrawAmt <= 0 || withdrawAmt > walletBalance() || walletActionLoading()" class="btn-primary">
            {{ walletActionLoading() ? 'Processing...' : 'Transfer Funds' }}
          </button>
        </div>
      </div>
    </app-modal>

    <!-- ══ CREDIT SCORE EXPLANATION MODAL (TOP-LEVEL, FULL VIEWPORT) ══ -->
    <app-modal
      [open]="creditExplanationModal()"
      title="Credit Score Explanation & AI Transparency"
      [subtitle]="creditExplanationData() ? 'Score: ' + creditExplanationData()!.credit_score + ' · ' + creditExplanationData()!.risk_category : ''"
      (close)="closeCreditExplanationModal()"
    >
      <div class="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
        <app-spinner *ngIf="creditExplanationLoading()" mode="page" label="Analyzing your credit score with SHAP AI..."></app-spinner>

        <div *ngIf="creditExplanationError()" class="text-center py-6 space-y-3">
          <div class="text-4xl">⚠️</div>
          <p class="text-sm text-on-surface-muted">{{ creditExplanationError() }}</p>
          <button class="btn-primary text-sm" (click)="loadCreditExplanation()">
            Try Again
          </button>
        </div>

        <div *ngIf="!creditExplanationLoading() && !creditExplanationError() && creditExplanationData()" class="space-y-4 animate-fade-in">
          <!-- Overall Assessment -->
          <div class="bg-brand-50 dark:bg-brand-500/10 rounded-xl p-4 border border-brand-200/50 dark:border-brand-500/20">
            <p class="text-xs uppercase tracking-wider font-semibold text-brand-600 dark:text-brand-400 mb-1">Overall AI Assessment</p>
            <p class="text-sm leading-relaxed text-on-surface">{{ creditExplanationData()!.explanation }}</p>
          </div>

          <!-- Factors List -->
          <div *ngIf="creditExplanationData()!.factors && creditExplanationData()!.factors.length > 0">
            <h4 class="font-semibold text-sm mb-3">Key Factors Influencing Your Score</h4>
            <div class="space-y-2.5">
              <div
                *ngFor="let factor of creditExplanationData()!.factors"
                class="p-3.5 rounded-xl border border-gray-100 dark:border-white/5 bg-gray-50/80 dark:bg-white/[0.03]"
              >
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-sm font-medium">{{ factor.feature }}</span>
                  <span class="text-xs font-mono font-semibold text-on-surface">{{ factor.current_value }}</span>
                </div>
                <!-- Importance progress bar -->
                <div class="w-full bg-gray-200 dark:bg-white/10 rounded-full h-2">
                  <div
                    class="h-2 rounded-full transition-all"
                    [style.width.%]="factor.importance * 100"
                    [ngClass]="{
                      'bg-emerald-500': factor.impact === 'positive',
                      'bg-rose-500': factor.impact === 'negative',
                      'bg-gray-400': factor.impact === 'neutral'
                    }"
                  ></div>
                </div>
                <div class="flex items-center justify-between mt-1.5">
                  <span
                    class="text-2xs px-2 py-0.5 rounded-full font-medium"
                    [ngClass]="{
                      'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300': factor.impact === 'positive',
                      'bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300': factor.impact === 'negative',
                      'bg-gray-100 dark:bg-white/10 text-on-surface-muted': factor.impact === 'neutral'
                    }"
                  >
                    {{ factor.impact === 'positive' ? '👍 Positive' : factor.impact === 'negative' ? '👎 Negative' : '➖ Neutral' }}
                  </span>
                  <span class="text-2xs text-on-surface-muted">
                    {{ (factor.importance * 100).toFixed(0) }}% impact weight
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Recommendations -->
          <div *ngIf="creditExplanationData()!.recommendations && creditExplanationData()!.recommendations.length > 0">
            <h4 class="font-semibold text-sm mb-2.5">📈 How to Improve Your Score</h4>
            <div class="space-y-2">
              <div
                *ngFor="let rec of creditExplanationData()!.recommendations"
                class="flex items-start gap-2.5 p-3 rounded-lg bg-emerald-50/50 dark:bg-emerald-500/5 border border-emerald-500/10 text-xs text-on-surface"
              >
                <span class="text-emerald-600 dark:text-emerald-400 text-sm">💡</span>
                <span>{{ rec }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </app-modal>
  `,
})
export class BorrowerDashboardComponent implements OnInit, OnDestroy {
  credit = signal<CreditScore | null>(null);
  loans  = signal<Loan[]>([]);
  creditLoading = signal(true);
  loansLoading  = signal(true);
  submitting    = signal(false);
  listening     = signal(false);

  // Credit explanation modal
  creditExplanationModal = signal(false);
  creditExplanationLoading = signal(false);
  creditExplanationError = signal<string | null>(null);
  creditExplanationData = signal<any | null>(null);

  // Real-time wallet balance
  walletBalance = signal<number>(0);
  depositModal = signal(false);
  withdrawModal = signal(false);
  depositAmt = 1000;
  withdrawAmt = 500;
  walletActionLoading = signal(false);


  // Blockchain modal
  blockchainModal = signal(false);
  blockchainLoan  = signal<Loan | null>(null);

  // Chat conversation history
  chatHistory = signal<Array<{
    role: 'user' | 'assistant';
    text: string;
    intent?: string;
    amount?: any;
    days?: any;
    time: string;
  }>>([]);

  // ── Hands-Free Continuous Live Call Mode ──────────────────────────
  isCallActive = signal(false);
  callState = signal<'idle' | 'listening' | 'processing' | 'speaking'>('idle');
  callSeconds = signal(0);
  isMuted = signal(false);
  liveSpeechText = signal('');
  currentSpeechResponse = signal('');
  private callTimer: any = null;
  private silenceTimer: any = null;
  private callRecognition: any = null;
  private currentAudio: HTMLAudioElement | null = null;

  callDuration = computed(() => {
    const total = this.callSeconds();
    const mins = Math.floor(total / 60).toString().padStart(2, '0');
    const secs = (total % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  });

  quickPrompts = computed(() => {
    const lang = this.selectedLanguage();
    if (lang === 'hi') {
      return [
        'मुझे ₹500 का लोन चुकाना है',
        'मेरा लोन पूरा भरें',
        'मेरा लोन स्टेटस क्या है?',
        'मुझे ₹5,000 का 60 दिन का लोन चाहिए',
        'मेरा क्रेडिट स्कोर क्या है?'
      ];
    } else if (lang === 'te') {
      return [
        'నా లోన్ 500 రూపాయలు కట్టాలి',
        'నా పూర్తి లోన్ చెల్లించండి',
        'నా లోన్ స్టేటస్ ఏమిటి?',
        'నాకు ₹5,000 లోన్ 60 రోజుల కోసం కావాలి',
        'నా క్రెడిట్ స్కోర్ ఎంత?'
      ];
    }
    return [
      'I want to repay 500 rupees',
      'Repay my active loan in full',
      'What is my loan status?',
      'I need a loan of ₹5,000 for 60 days',
      'Check my credit score'
    ];
  });

  // Loan request wizard
  requestMode: RequestMode = 'voice';  // Changed default to voice
  wizardStep = signal<WizardStep>(1);
  wAmount   = 1000;
  wDuration = 30;
  wPurpose  = '';
  wTouched  = { amount: false };

  // Voice
  voiceText  = '';
  voiceReply = signal<VoiceResponse | null>(null);
  sessionId  = crypto.randomUUID();
  private recognition: any;
  private synthesis: any;
  selectedLanguage = signal<'en' | 'hi' | 'te'>('en');
  
  // Language voice mapping
  private languageVoiceMap = {
    'en': 'en-IN',
    'hi': 'hi-IN',
    'te': 'te-IN'
  };

  // Repay modal
  repayModal    = signal(false);
  repayingLoan  = signal<Loan | null>(null);
  repayAmt      = 0;
  repayTouched  = false;

  // Schedule modal
  scheduleModal   = signal(false);
  scheduleLoan    = signal<Loan | null>(null);
  schedule        = signal<ScheduleEntry[]>([]);
  scheduleLoading = signal(false);

  readonly quickAmounts = [500, 1000, 2000, 5000, 10000];
  readonly durationOptions = [
    { days: 15, label: '2 weeks' },
    { days: 30, label: '1 month' },
    { days: 60, label: '2 months' },
    { days: 90, label: '3 months' },
    { days: 180, label: '6 months' },
    { days: 365, label: '1 year' },
  ];
  readonly dtmfKeys = ['1','2','3','4','5','6','7','8','9','*','0','#'];
  readonly modes = [
    { id: 'voice'  as RequestMode, label: 'Voice',  icon: '🎙️' },  // Voice first
    { id: 'wizard' as RequestMode, label: 'Form', icon: '📝' },
    { id: 'keypad' as RequestMode, label: 'Keypad', icon: '📞' },
  ];
  
  readonly languages = [
    { code: 'en' as const, label: 'English', flag: '🇬🇧' },
    { code: 'hi' as const, label: 'हिंदी', flag: '🇮🇳' },
    { code: 'te' as const, label: 'తెలుగు', flag: '🇮🇳' },
  ];

  activeLoans = computed(() => this.loans().filter(l => l.status === 'ACTIVE' || l.status === 'LATE'));

  scorePercent = computed(() => {
    const s = this.credit()?.credit_score ?? 300;
    return ((s - 300) / 550) * 100;
  });

  scoreColor = computed((): 'brand' | 'success' | 'warning' | 'danger' => {
    const s = this.credit()?.credit_score ?? 300;
    if (s >= 750) return 'success';
    if (s >= 650) return 'brand';
    if (s >= 500) return 'warning';
    return 'danger';
  });

  get amountValid(): boolean {
    const limit = this.credit()?.borrowing_limit ?? Infinity;
    return this.wAmount > 0 && this.wAmount <= limit;
  }

  remaining = computed(() => {
    const l = this.repayingLoan();
    if (!l) return 0;
    return Math.max(0, Math.round((l.total_due - l.amount_repaid) * 100) / 100);
  });

  get repayAmtValid(): boolean {
    return this.repayAmt > 0 && this.repayAmt <= this.remaining() + 0.001;
  }

  private unsubStatusChange?: () => void;
  private unsubLoanFunded?: () => void;
  private unsubWallet?: () => void;

  constructor(
    private api: ApiService,
    private toast: ToastService,
    private realtime: RealtimeService
  ) {}

  ngOnInit() {
    this.refresh();

    // Listen to real-time events for live dashboard updates
    this.unsubStatusChange = this.realtime.subscribe('loan_status_change', (data: any) => {
      this.toast.info('Loan Update', `Status updated: ${data?.new_status || 'changed'}`);
      this.refresh();
    });

    this.unsubLoanFunded = this.realtime.subscribe('loan_funded', (data: any) => {
      this.toast.success('Loan Funded!', `Investor funded your loan!`);
      this.refresh();
    });

    this.unsubWallet = this.realtime.subscribe('wallet_balance_updated', (data: any) => {
      if (data?.wallet_balance !== undefined) {
        this.walletBalance.set(data.wallet_balance);
      } else if (data?.balance !== undefined) {
        this.walletBalance.set(data.balance);
      }
      if (data?.message) {
        this.toast.info('Bank Wallet Update', data.message);
      }
      this.refresh();
    });
  }

  ngOnDestroy() {
    this.endLiveCall();
    this.stopSpeaking();
    this.recognition?.stop();
    this.unsubStatusChange?.();
    this.unsubLoanFunded?.();
    this.unsubWallet?.();
  }

  openDepositModal() {
    this.depositAmt = 1000;
    this.depositModal.set(true);
  }

  closeDepositModal() {
    this.depositModal.set(false);
  }

  submitDeposit() {
    if (this.depositAmt <= 0) return;
    this.walletActionLoading.set(true);
    this.api.depositWallet(this.depositAmt).subscribe({
      next: (res) => {
        this.walletActionLoading.set(false);
        this.walletBalance.set(res.balance ?? res.wallet_balance);
        this.depositModal.set(false);
        this.toast.success('Funds Deposited', `₹${this.depositAmt} added to your digital bank wallet!`);
      },
      error: (err) => {
        this.walletActionLoading.set(false);
        this.toast.error('Deposit Failed', err?.error?.detail || 'Failed to deposit funds');
      }
    });
  }

  openWithdrawModal() {
    this.withdrawAmt = Math.min(500, Math.max(100, this.walletBalance()));
    this.withdrawModal.set(true);
  }

  closeWithdrawModal() {
    this.withdrawModal.set(false);
  }

  submitWithdraw() {
    if (this.withdrawAmt <= 0 || this.withdrawAmt > this.walletBalance()) {
      this.toast.error('Invalid Amount', 'Withdrawal amount exceeds wallet balance.');
      return;
    }
    this.walletActionLoading.set(true);
    this.api.withdrawWallet(this.withdrawAmt).subscribe({
      next: (res) => {
        this.walletActionLoading.set(false);
        this.walletBalance.set(res.balance ?? res.wallet_balance);
        this.withdrawModal.set(false);
        this.toast.success('Transfer Successful', `₹${this.withdrawAmt} transferred from wallet.`);
      },
      error: (err) => {
        this.walletActionLoading.set(false);
        this.toast.error('Withdrawal Failed', err?.error?.detail || 'Failed to transfer funds');
      }
    });
  }

  openBlockchainModal(loan: Loan) {
    this.blockchainLoan.set(loan);
    this.blockchainModal.set(true);
  }

  closeBlockchainModal() {
    this.blockchainModal.set(false);
    this.blockchainLoan.set(null);
  }

  openCreditExplanationModal() {
    this.creditExplanationModal.set(true);
    this.loadCreditExplanation();
  }

  closeCreditExplanationModal() {
    this.creditExplanationModal.set(false);
  }

  loadCreditExplanation() {
    this.creditExplanationLoading.set(true);
    this.creditExplanationError.set(null);
    const lang = this.selectedLanguage() || 'en';
    this.api.explainCreditScore(lang).subscribe({
      next: (res) => {
        this.creditExplanationLoading.set(false);
        const rawFactors = res.factors || res.top_factors || [];
        const factors = rawFactors.map((f: any) => ({
          feature: f.display_name || f.feature,
          importance: typeof f.importance === 'number' ? f.importance : (f.shap_value ? Math.min(1.0, Math.abs(f.shap_value)) : 0.5),
          current_value: f.current_value !== undefined ? f.current_value : (f.value !== undefined ? f.value : '—'),
          impact: f.impact || 'neutral',
        }));
        this.creditExplanationData.set({
          credit_score: res.credit_score,
          risk_category: res.risk_category,
          explanation: res.explanation,
          recommendations: res.recommendations || [],
          factors,
        });
      },
      error: (err) => {
        this.creditExplanationLoading.set(false);
        this.creditExplanationError.set(err?.error?.detail || 'Unable to load credit score explanation');
      }
    });
  }

  selectQuickPrompt(prompt: string) {
    this.voiceText = prompt;
    this.sendVoiceText();
  }

  refresh() {
    this.creditLoading.set(true);
    this.loansLoading.set(true);
    this.api.me().subscribe({
      next: (user) => {
        this.walletBalance.set(user.wallet_balance ?? 0);
      },
      error: () => {},
    });
    this.api.myCreditScore().subscribe({
      next:  (c) => { this.credit.set(c); this.creditLoading.set(false); },
      error: ()  => { this.creditLoading.set(false); },
    });
    this.api.listLoans({ mine: true }).subscribe({
      next:  (ls) => { this.loans.set(ls); this.loansLoading.set(false); },
      error: ()   => { this.loansLoading.set(false); },
    });
  }


  // ── Wizard ──────────────────────────────────────────────────────────
  wizStep(s: number): string {
    if (s < this.wizardStep()) return 'wizard-step-done';
    if (s === this.wizardStep()) return 'wizard-step-active';
    return 'wizard-step-inactive';
  }

  wizNext() {
    if (this.wizardStep() === 1) {
      this.wTouched.amount = true;
      if (!this.amountValid) return;
      this.wizardStep.set(2);
    } else if (this.wizardStep() === 2) {
      this.wizardStep.set(3);
    }
  }

  submitLoan() {
    this.submitting.set(true);
    this.api.requestLoan({
      amount: this.wAmount,
      duration_days: this.wDuration,
      purpose: this.wPurpose || undefined,
      source: 'web',
    }).subscribe({
      next: (loan) => {
        this.submitting.set(false);
        this.wizardStep.set(1);
        this.wAmount = 1000; this.wDuration = 30; this.wPurpose = '';
        this.wTouched.amount = false;
        this.toast.success('Loan requested!', `₹${loan.amount} — Status: ${loan.status}`);
        this.refresh();
      },
      error: (err) => {
        this.submitting.set(false);
        this.toast.error('Request failed', err?.error?.detail ?? 'Something went wrong');
      },
    });
  }

  // ── Voice & Autonomous Agent ──────────────────────────────────────────
  sendVoiceText() {
    if (!this.voiceText.trim()) return;
    const sentText = this.voiceText.trim();
    this.submitting.set(true);

    // Record user speech in chat thread
    this.chatHistory.update(h => [...h, {
      role: 'user',
      text: sentText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }]);

    this.voiceText = '';
    
    // Use Groq-powered voice API (FREE, intelligent) with selected language
    this.api.voiceTurn(sentText, this.sessionId, this.selectedLanguage()).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.voiceReply.set(res);

        // Record assistant response in chat thread
        this.chatHistory.update(h => [...h, {
          role: 'assistant',
          text: res.reply_text,
          intent: res.intent,
          amount: res.entities?.amount,
          days: res.entities?.duration_days,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
        
        if (res.action_taken === 'LOAN_REPAID' || res.action_taken === 'LOAN_CREATED') {
          this.toast.success('Agent Executed Action', res.reply_text);
        }

        // Auto-play TTS response
        this.speakResponse(res.reply_text, this.selectedLanguage());
        this.refresh();
      },
      error: (err) => {
        this.submitting.set(false);
        this.toast.error('Voice error', err?.error?.detail ?? 'Voice request failed');
      },
    });
  }
  
  speakResponse(text: string, language: 'en' | 'hi' | 'te', onEnd?: () => void) {
    if (!text) {
      onEnd?.();
      return;
    }

    this.stopSpeaking();
    
    // Primary: High-fidelity Free TTS streaming (guarantees native Telugu, Hindi, English audio even on Windows with no voice pack)
    try {
      const clean = encodeURIComponent(text.replace(/[*#]/g, '').trim());
      const audioUrl = `/api/voice/tts?text=${clean}&language=${language}`;
      const audio = new Audio(audioUrl);
      this.currentAudio = audio;

      let handled = false;
      const done = () => {
        if (!handled) {
          handled = true;
          this.currentAudio = null;
          onEnd?.();
        }
      };

      audio.onended = done;
      audio.onerror = () => {
        this.fallbackBrowserTTS(text, language, done);
      };

      const p = audio.play();
      if (p !== undefined) {
        p.catch(() => {
          this.fallbackBrowserTTS(text, language, done);
        });
      }
    } catch (_) {
      this.fallbackBrowserTTS(text, language, onEnd);
    }
  }

  private fallbackBrowserTTS(text: string, language: 'en' | 'hi' | 'te', onEnd?: () => void) {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = this.languageVoiceMap[language];
      utterance.rate = 0.95; // Natural spoken rate
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      
      const voices = window.speechSynthesis.getVoices();
      const nativeVoice = voices.find(v => v.lang.startsWith(this.languageVoiceMap[language]));
      if (nativeVoice) {
        utterance.voice = nativeVoice;
      }

      utterance.onend = () => onEnd?.();
      utterance.onerror = () => onEnd?.();
      window.speechSynthesis.speak(utterance);
    } else {
      onEnd?.();
    }
  }
  
  stopSpeaking() {
    if (this.currentAudio) {
      try {
        this.currentAudio.pause();
        this.currentAudio.currentTime = 0;
      } catch (_) {}
      this.currentAudio = null;
    }
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }
  
  changeLanguage(lang: 'en' | 'hi' | 'te') {
    this.selectedLanguage.set(lang);
    this.stopSpeaking();
    if (this.isCallActive() && this.callState() === 'listening') {
      this.listenCallTurn();
    }
  }
  
  getPlaceholder(): string {
    const placeholders = {
      en: 'Ask anything... (e.g., "I want to repay my loan 500", "What is my loan status?", "I need 5000 for 30 days")',
      hi: 'कुछ भी पूछें... (उदाहरण: "मुझे 500 रुपये का लोन चुकाना है", "लोन स्टेटस क्या है?", "5000 का 30 दिन का लोन चाहिए")',
      te: 'ఏదైనా అడగండి... (ఉదాహరణ: "నా లోన్ 500 రూపాయలు కట్టాలి", "నా లోన్ స్టేటస్ ఏమిటి?", "5000 రూపాయల 30 రోజుల లోన్ కావాలి")'
    };
    return placeholders[this.selectedLanguage()];
  }

  pressDtmf(digit: string) {
    this.api.dtmfTurn(digit, this.sessionId).subscribe({
      next:  (res) => { 
        this.voiceReply.set(res); 
        this.speakResponse(res.reply_text, this.selectedLanguage());
        this.refresh(); 
      },
      error: (err) => this.toast.error('DTMF error', err?.error?.detail ?? 'Failed'),
    });
  }

  // ── Hands-Free Continuous Live Phone Call Mode ────────────────────────
  startLiveCall() {
    this.isCallActive.set(true);
    this.callSeconds.set(0);
    this.isMuted.set(false);
    this.liveSpeechText.set('');
    this.currentSpeechResponse.set('');

    // Start live timer
    clearInterval(this.callTimer);
    this.callTimer = setInterval(() => {
      this.callSeconds.update(s => s + 1);
    }, 1000);

    // Warm greeting from AI Agent
    const greetings = {
      en: "Hello! I am your FinLend Voice Agent. How can I help you today? You can say repay my loan, check loan status, or request a new loan.",
      hi: "नमस्ते! मैं आपका फिनलैंड वॉइस एजेंट हूँ। आज मैं आपकी कैसे सहायता करूँ? आप लोन चुका सकते हैं, स्टेटस चेक कर सकते हैं या नया लोन ले सकते हैं।",
      te: "నమస్కారం! నేను మీ ఫిన్లెండ్ వాయిస్ ఏజెంట్‌ని. ఈరోజు నేను మీకు ఎలా సహాయపడగలను? మీరు లోన్ చెల్లించవచ్చు, స్టేటస్ చెక్ చేయవచ్చు లేదా కొత్త లోన్ తీసుకోవచ్చు."
    };

    const welcomeMsg = greetings[this.selectedLanguage()];
    this.currentSpeechResponse.set(welcomeMsg);
    this.callState.set('speaking');

    this.speakResponse(welcomeMsg, this.selectedLanguage(), () => {
      if (this.isCallActive()) {
        this.listenCallTurn();
      }
    });
  }

  listenCallTurn() {
    if (!this.isCallActive() || this.isMuted()) return;

    const SR = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
    if (!SR) {
      this.toast.warning('Not supported', 'Speech recognition unavailable in this browser.');
      this.endLiveCall();
      return;
    }

    this.callState.set('listening');
    this.liveSpeechText.set('');

    try {
      this.callRecognition?.stop();
    } catch (_) {}

    this.callRecognition = new SR();
    this.callRecognition.lang = this.languageVoiceMap[this.selectedLanguage()];
    this.callRecognition.continuous = true;
    this.callRecognition.interimResults = true;

    this.callRecognition.onresult = (e: any) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = 0; i < e.results.length; i++) {
        const transcript = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interimTranscript += transcript;
        }
      }

      const currentText = (finalTranscript + interimTranscript).trim();
      this.liveSpeechText.set(currentText);

      // Reset silence debounce timer: 1.3s pause triggers autonomous execution
      clearTimeout(this.silenceTimer);
      if (currentText.length > 2) {
        this.silenceTimer = setTimeout(() => {
          this.processCallTurn(currentText);
        }, 1300);
      }
    };

    this.callRecognition.onerror = (err: any) => {
      if (this.isCallActive() && this.callState() === 'listening') {
        setTimeout(() => {
          if (this.isCallActive() && this.callState() === 'listening') {
            try { this.callRecognition?.start(); } catch (_) {}
          }
        }, 1000);
      }
    };

    this.callRecognition.onend = () => {
      if (this.isCallActive() && this.callState() === 'listening' && !this.isMuted()) {
        setTimeout(() => {
          if (this.isCallActive() && this.callState() === 'listening') {
            try { this.callRecognition?.start(); } catch (_) {}
          }
        }, 400);
      }
    };

    try {
      this.callRecognition.start();
    } catch (_) {}
  }

  processCallTurn(spokenText: string) {
    if (!this.isCallActive() || this.callState() === 'processing' || this.callState() === 'speaking') return;

    clearTimeout(this.silenceTimer);
    try {
      this.callRecognition?.stop();
    } catch (_) {}

    this.callState.set('processing');

    // Add to chat history
    this.chatHistory.update(h => [...h, {
      role: 'user',
      text: spokenText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }]);

    this.api.voiceTurn(spokenText, this.sessionId, this.selectedLanguage()).subscribe({
      next: (res) => {
        this.voiceReply.set(res);
        this.currentSpeechResponse.set(res.reply_text);

        this.chatHistory.update(h => [...h, {
          role: 'assistant',
          text: res.reply_text,
          intent: res.intent,
          amount: res.entities?.amount,
          days: res.entities?.duration_days,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);

        if (res.action_taken === 'LOAN_REPAID' || res.action_taken === 'LOAN_CREATED') {
          this.toast.success('Action Executed', res.reply_text);
          this.refresh();
        }

        // If user said goodbye or hang up, end the call after speaking response
        if (res.end_call) {
          this.callState.set('speaking');
          this.speakResponse(res.reply_text, this.selectedLanguage(), () => {
            this.endLiveCall();
          });
        } else {
          // Autonomous continuous loop: speak response, then immediately listen again hands-free!
          this.callState.set('speaking');
          this.speakResponse(res.reply_text, this.selectedLanguage(), () => {
            if (this.isCallActive()) {
              this.listenCallTurn();
            }
          });
        }
      },
      error: (err) => {
        const errorMsg = "I couldn't hear that clearly. Could you please repeat?";
        this.currentSpeechResponse.set(errorMsg);
        this.callState.set('speaking');
        this.speakResponse(errorMsg, this.selectedLanguage(), () => {
          if (this.isCallActive()) {
            this.listenCallTurn();
          }
        });
      }
    });
  }

  toggleMute() {
    this.isMuted.update(m => !m);
    if (this.isMuted()) {
      clearTimeout(this.silenceTimer);
      try { this.callRecognition?.stop(); } catch (_) {}
      this.toast.info('Microphone Muted', 'Agent will not hear you while muted.');
    } else {
      this.toast.info('Microphone Unmuted', 'Agent listening...');
      this.listenCallTurn();
    }
  }

  endLiveCall() {
    this.isCallActive.set(false);
    this.callState.set('idle');
    clearInterval(this.callTimer);
    clearTimeout(this.silenceTimer);
    try {
      this.callRecognition?.stop();
    } catch (_) {}
    this.stopSpeaking();
    this.liveSpeechText.set('');
    this.currentSpeechResponse.set('');
  }

  // ── Single-Turn Voice Mic Button ──────────────────────────────────────
  startListening() {
    const SR = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
    if (!SR) {
      this.toast.warning('Not supported', 'Speech recognition unavailable in this browser. Type instead.');
      return;
    }
    this.recognition = new SR();
    this.recognition.lang = this.languageVoiceMap[this.selectedLanguage()];
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    
    this.recognition.onresult = (e: any) => {
      let finalTranscript = '';
      let interimTranscript = '';
      
      for (let i = 0; i < e.results.length; i++) {
        const transcript = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interimTranscript += transcript;
        }
      }
      
      this.voiceText = (finalTranscript + interimTranscript).trim();
    };
    
    this.recognition.onerror = () => {
      this.listening.set(false);
      this.toast.error('Speech recognition error', 'Could not recognize speech');
    };
    
    this.recognition.onend = () => {
      this.listening.set(false);
    };
    
    this.recognition.start();
    this.listening.set(true);
  }

  stopListening() {
    this.recognition?.stop();
    this.listening.set(false);
  }

  // ── Repay modal ───────────────────────────────────────────────────────
  openRepayModal(loan: Loan) {
    this.repayingLoan.set(loan);
    this.repayAmt = Math.round((loan.total_due - loan.amount_repaid) * 100) / 100;
    this.repayTouched = false;
    this.repayModal.set(true);
  }

  closeRepayModal() {
    this.repayModal.set(false);
    this.repayingLoan.set(null);
  }

  submitRepayment() {
    this.repayTouched = true;
    if (!this.repayAmtValid) return;
    if (this.walletBalance() < this.repayAmt) {
      this.toast.error('Insufficient Wallet Balance', `Your wallet has ₹${this.walletBalance().toFixed(2)}. Please deposit funds first.`);
      return;
    }
    const loan = this.repayingLoan()!;
    this.submitting.set(true);

    this.api.repayLoan(loan.id, this.repayAmt).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.closeRepayModal();
        this.toast.success('Payment recorded!',
          `Credit score: ${res.credit_score} · Limit: ₹${res.borrowing_limit.toLocaleString()}`);
        this.refresh();
      },
      error: (err) => {
        this.submitting.set(false);
        this.toast.error('Payment failed', err?.error?.detail ?? 'Something went wrong');
      },
    });
  }

  // ── Schedule modal ────────────────────────────────────────────────────
  openScheduleModal(loan: Loan) {
    this.scheduleLoan.set(loan);
    this.scheduleModal.set(true);
    this.schedule.set([]);
    this.scheduleLoading.set(true);
    this.api.getLoanSchedule(loan.id).subscribe({
      next:  (s) => { this.schedule.set(s); this.scheduleLoading.set(false); },
      error: ()  => { this.scheduleLoading.set(false); this.toast.error('Could not load schedule'); },
    });
  }

  // ── Timeline helpers ──────────────────────────────────────────────────
  showTimeline(l: Loan): boolean {
    return !['REJECTED', 'DEFAULTED'].includes(l.status);
  }

  timelineSteps(l: Loan) {
    const currentIdx = STATUS_ORDER[l.status] ?? -1;
    return LOAN_TIMELINE_STEPS.map((ts, idx) => ({
      ...ts,
      dotClass: idx < currentIdx
        ? 'timeline-dot-done'
        : idx === currentIdx
          ? 'timeline-dot-active'
          : 'timeline-dot-pending',
      lineClass: idx < currentIdx ? 'bg-brand-400' : 'bg-gray-200 dark:bg-white/10',
    }));
  }

  isOverdue(l: Loan): boolean {
    if (!l.due_date) return false;
    return new Date(l.due_date) < new Date();
  }

  round(n: number): number { return Math.round(n * 100) / 100; }
}
