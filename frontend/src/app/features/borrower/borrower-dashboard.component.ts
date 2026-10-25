import {
  Component, OnInit, signal, computed, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule, DecimalPipe, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { NavbarComponent } from '../../shared/components/navbar.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';
import { ProgressBarComponent } from '../../shared/components/progress-bar.component';
import { LoadingSpinnerComponent } from '../../shared/components/loading-spinner.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import { ModalComponent } from '../../shared/components/modal.component';
import { EMICalculatorComponent } from '../../shared/components/emi-calculator.component';
import { CreditExplanationComponent } from '../../shared/components/credit-explanation.component';
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
    EMICalculatorComponent, CreditExplanationComponent,
  ],
  template: `
    <app-navbar></app-navbar>

    <div class="page-container space-y-6 animate-fade-in-up">

      <!-- ══ TOP STATS ROW ════════════════════════════════════════════════ -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4" *ngIf="!creditLoading(); else creditSkel">
        <!-- Credit score -->
        <div class="stat-card glass-card-hover relative overflow-hidden">
          <div class="absolute inset-0 bg-gradient-to-br from-brand-500/8 to-transparent rounded-xl2"></div>
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
          <div class="mt-2">
            <app-credit-explanation></app-credit-explanation>
          </div>
        </div>

        <!-- Borrowing limit -->
        <div class="stat-card glass-card-hover">
          <span class="stat-label">Borrowing limit</span>
          <span class="stat-value">₹{{ credit()?.borrowing_limit | number:'1.0-0' }}</span>
          <p class="text-xs text-on-surface-muted mt-1">Based on your credit score tier</p>
          <a routerLink="/borrower/notifications"
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
          
          <!-- Voice Instructions with Examples -->
          <div class="glass-panel p-5 bg-gradient-to-br from-brand/10 to-brand/5">
            <h3 class="text-lg font-semibold text-on-surface mb-2 flex items-center gap-2">
              <span class="text-2xl">🎤</span>
              Speak Naturally
            </h3>
            <p class="text-sm text-on-surface-muted mb-3">
              Tell me what you need. I understand {{ selectedLanguage() === 'hi' ? 'हिंदी' : selectedLanguage() === 'te' ? 'తెలుగు' : 'English' }}.
            </p>
            
            <!-- Example Prompts -->
            <div class="bg-surface/50 rounded-lg p-3 text-xs space-y-1">
              <p class="font-medium text-on-surface mb-2">Examples:</p>
              <p *ngIf="selectedLanguage() === 'en'" class="text-on-surface-muted">
                • "I need a loan of 5000 rupees for 65 days"<br>
                • "Check my credit score"<br>
                • "Show my balance"
              </p>
              <p *ngIf="selectedLanguage() === 'hi'" class="text-on-surface-muted">
                • "मुझे 5000 रुपये का 65 दिन का लोन चाहिए"<br>
                • "मेरा क्रेडिट स्कोर क्या है?"<br>
                • "बैलेंस चेक करें"
              </p>
              <p *ngIf="selectedLanguage() === 'te'" class="text-on-surface-muted">
                • "నాకు 5000 రూపాయల 65 రోజుల లోన్ కావాలి"<br>
                • "నా క్రెడిట్ స్కోర్ ఎంత?"<br>
                • "బ్యాలెన్స్ చెక్ చేయండి"
              </p>
            </div>
          </div>

          <!-- Voice Input Controls -->
          <div class="glass-panel p-6 space-y-4">
            
            <!-- Large Microphone Button -->
            <div class="flex flex-col items-center justify-center gap-3">
              <button
                *ngIf="!listening()"
                (click)="startListening()"
                class="w-24 h-24 rounded-full bg-gradient-to-br from-brand to-brand-dark text-white shadow-xl hover:scale-105 transition-transform flex items-center justify-center"
                title="Click to speak">
                <span class="text-5xl">🎙️</span>
              </button>
              
              <button
                *ngIf="listening()"
                (click)="stopListening()"
                class="w-24 h-24 rounded-full bg-red-500 text-white shadow-xl animate-pulse flex items-center justify-center"
                title="Click to stop">
                <span class="text-5xl">⏸️</span>
              </button>
              
              <p class="text-sm font-medium text-center" [class.text-red-600]="listening()" [class.animate-pulse]="listening()">
                {{ listening() ? '🎤 Listening... Speak now!' : 'Tap microphone to speak' }}
              </p>
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
              class="btn-primary w-full text-lg py-4 font-semibold" 
              (click)="sendVoiceText()" 
              [disabled]="submitting() || !voiceText.trim()">
              <app-spinner *ngIf="submitting()" mode="inline" size="sm"></app-spinner>
              <span *ngIf="!submitting()">{{ selectedLanguage() === 'hi' ? '🗣️ भेजें' : selectedLanguage() === 'te' ? '🗣️ పంపండి' : '🗣️ Send Message' }}</span>
            </button>
          </div>

          <!-- Voice Response Card -->
          <div *ngIf="voiceReply()" class="glass-panel p-6 space-y-4 text-base animate-fade-in border-2 border-brand/30">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 font-semibold text-on-surface text-lg">
                <span class="text-2xl">🤖</span> 
                <span>{{ selectedLanguage() === 'hi' ? 'सहायक का जवाब' : selectedLanguage() === 'te' ? 'సహాయకుడి సమాధానం' : 'Assistant Response' }}</span>
              </div>
              <button (click)="stopSpeaking()" class="text-on-surface-muted hover:text-on-surface text-sm">
                🔇 Stop Audio
              </button>
            </div>
            
            <p class="leading-relaxed text-lg">{{ voiceReply()!.reply_text }}</p>
            
            <!-- Metadata -->
            <div class="flex flex-wrap gap-3 text-sm text-on-surface-muted pt-3 border-t border-gray-200 dark:border-white/10">
              <span>💬 <strong>{{ voiceReply()!.intent }}</strong></span>
              <span>·</span>
              <span>📝 {{ voiceReply()!.transcript }}</span>
              <span *ngIf="voiceReply()!.entities?.amount">·</span>
              <span *ngIf="voiceReply()!.entities?.amount">💰 ₹{{ voiceReply()!.entities.amount }}</span>
              <span *ngIf="voiceReply()!.entities?.duration_days">·</span>
              <span *ngIf="voiceReply()!.entities?.duration_days">📅 {{ voiceReply()!.entities.duration_days }} days</span>
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
                <div class="flex gap-2 flex-shrink-0">
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
        </div>

        <!-- Amount input -->
        <div>
          <label class="input-label" for="repay-amt">Repayment amount (₹)</label>
          <input id="repay-amt" type="number" class="input-field"
                 [class.input-field-error]="repayTouched && !repayAmtValid"
                 [(ngModel)]="repayAmt" name="repay-amt"
                 [max]="remaining()"
                 (blur)="repayTouched = true"
                 placeholder="Enter amount" />
          <p *ngIf="repayTouched && repayAmt <= 0" class="input-error"><span>⚠</span> Amount must be positive</p>
          <p *ngIf="repayTouched && repayAmt > remaining() + 0.001" class="input-error">
            <span>⚠</span> Cannot exceed remaining amount (₹{{ remaining() | number:'1.2-2' }})
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
          <button class="btn-primary flex-1 py-3" (click)="submitRepayment()" [disabled]="submitting()">
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
  `,
})
export class BorrowerDashboardComponent implements OnInit {
  credit = signal<CreditScore | null>(null);
  loans  = signal<Loan[]>([]);
  creditLoading = signal(true);
  loansLoading  = signal(true);
  submitting    = signal(false);
  listening     = signal(false);

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

  constructor(private api: ApiService, private toast: ToastService) {}

  ngOnInit() { this.refresh(); }

  refresh() {
    this.creditLoading.set(true);
    this.loansLoading.set(true);
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

  // ── Voice ────────────────────────────────────────────────────────────
  sendVoiceText() {
    if (!this.voiceText.trim()) return;
    this.submitting.set(true);
    // Use enhanced voice API with multilingual support
    this.api.enhancedVoice({
      text: this.voiceText,
      language: this.selectedLanguage(),
      session_id: this.sessionId,
    }).subscribe({
      next: (res) => {
        this.submitting.set(false);
        // Map enhanced response to VoiceResponse format
        this.voiceReply.set({
          transcript: res.transcript || this.voiceText,
          intent: res.intent || 'unknown',
          entities: res.entities || {},
          reply_text: res.reply_text || res.response || 'Request processed',
          audio_available: res.audio_available || false,
          session_id: res.session_id || this.sessionId,
        });
        
        // Auto-play TTS response
        this.speakResponse(res.reply_text || res.response || '', this.selectedLanguage());
        
        this.voiceText = '';
        this.refresh();
      },
      error: (err) => {
        this.submitting.set(false);
        this.toast.error('Voice error', err?.error?.detail ?? 'Voice request failed');
      },
    });
  }
  
  speakResponse(text: string, language: 'en' | 'hi' | 'te') {
    if (!text) return;
    
    // Use browser's Web Speech API for TTS
    if ('speechSynthesis' in window) {
      // Cancel any ongoing speech
      window.speechSynthesis.cancel();
      
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = this.languageVoiceMap[language];
      utterance.rate = 0.9; // Slightly slower for clarity
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      
      // Try to find a native voice for the language
      const voices = window.speechSynthesis.getVoices();
      const nativeVoice = voices.find(v => v.lang.startsWith(this.languageVoiceMap[language]));
      if (nativeVoice) {
        utterance.voice = nativeVoice;
      }
      
      window.speechSynthesis.speak(utterance);
    }
  }
  
  stopSpeaking() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }
  
  changeLanguage(lang: 'en' | 'hi' | 'te') {
    this.selectedLanguage.set(lang);
    this.stopSpeaking();
  }
  
  getPlaceholder(): string {
    const placeholders = {
      en: 'Or type your message here... (e.g., "I need 5000 rupees loan for 30 days")',
      hi: 'या यहाँ टाइप करें... (उदाहरण: "मुझे 5000 रुपये का 30 दिन का लोन चाहिए")',
      te: 'లేదా ఇక్కడ టైప్ చేయండి... (ఉదాహరణ: "నాకు 5000 రూపాయల 30 రోజుల లోన్ కావాలి")'
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
    
    // BUG FIX: Use proper change detection for live transcript updates
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
      
      // Update the text field in real-time - this shows LIVE words as you speak
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
    // BUG FIX: Only stop recording, DON'T auto-send
    // User must click "Send Message" button to submit
    this.recognition?.stop();
    this.listening.set(false);
    // REMOVED: this.sendVoiceText(); - This was causing auto-send bug
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
