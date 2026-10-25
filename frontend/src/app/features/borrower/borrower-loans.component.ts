/**
 * Borrower /loans sub-page — shows all loans with filtering, credit history,
 * and links to the repayment schedule. The dashboard handles the request wizard;
 * this page is purely read + repay.
 */
import {
  Component, OnInit, signal, computed, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { NavbarComponent } from '../../shared/components/navbar.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';
import { ProgressBarComponent } from '../../shared/components/progress-bar.component';
import { LoadingSpinnerComponent } from '../../shared/components/loading-spinner.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import { ModalComponent } from '../../shared/components/modal.component';
import { BlockchainVerificationComponent } from '../../shared/components/blockchain-verification.component';
import { CreditExplanationComponent } from '../../shared/components/credit-explanation.component';
import type { Loan, ScheduleEntry, CreditHistoryEntry } from '../../core/models';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-borrower-loans',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Default,
  imports: [
    CommonModule, FormsModule, RouterLink,
    NavbarComponent, StatusBadgeComponent, ProgressBarComponent,
    LoadingSpinnerComponent, EmptyStateComponent, ModalComponent,
    BlockchainVerificationComponent, CreditExplanationComponent,
  ],
  template: `
    <app-navbar></app-navbar>

    <div class="page-container space-y-5 animate-fade-in-up">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 class="text-2xl font-semibold text-on-surface">My loans</h1>
          <p class="text-sm text-on-surface-muted mt-0.5">{{ loans().length }} total</p>
        </div>
        <div class="flex gap-2 flex-wrap">
          <select class="input-field text-sm w-40" [(ngModel)]="statusFilter">
            <option value="">All statuses</option>
            <option *ngFor="let s of statuses" [value]="s">{{ s }}</option>
          </select>
          <a routerLink="/borrower" class="btn-primary text-sm">+ New request</a>
        </div>
      </div>

      <app-spinner *ngIf="loading()" mode="page" label="Loading loans…"></app-spinner>
      <app-empty-state *ngIf="!loading() && !filtered().length"
        icon="📋" title="No loans" subtitle="Your loan history will appear here.">
      </app-empty-state>

      <div *ngIf="!loading() && filtered().length" class="space-y-3">
        <div *ngFor="let l of filtered()" class="glass-card p-5 glass-card-hover">
          <div class="flex flex-wrap items-start justify-between gap-3 mb-3">
            <div>
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-bold text-xl">₹{{ l.amount | number }}</span>
                <app-status-badge [value]="l.status" type="status" [dot]="true"></app-status-badge>
                <app-status-badge *ngIf="l.risk_category" [value]="l.risk_category" type="risk"></app-status-badge>
              </div>
              <p class="text-xs text-on-surface-muted mt-0.5">{{ l.purpose || 'General' }} · {{ l.duration_days }} days</p>
            </div>
            <div class="flex gap-2">
              <button *ngIf="l.status === 'ACTIVE' || l.status === 'LATE'"
                      class="btn-primary text-xs" (click)="openRepay(l)">💸 Repay</button>
              <button *ngIf="l.status === 'ACTIVE' || l.status === 'LATE'"
                      class="btn-secondary text-xs" (click)="openSchedule(l)">📅 Schedule</button>
              <button class="btn-secondary text-xs" (click)="openBlockchain(l)">🔗 Verify</button>
              <app-credit-explanation *ngIf="l.status === 'REJECTED'" [loanId]="l.id"></app-credit-explanation>
            </div>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <app-progress-bar [pct]="(l.amount_funded / l.amount) * 100"
                              color="brand" [height]="5" [showLabel]="true" label="Funded"
                              [subLabel]="'₹' + (l.amount_funded | number:'1.0-0')"
                              [subLabelRight]="'of ₹' + (l.amount | number:'1.0-0')">
            </app-progress-bar>
            <app-progress-bar *ngIf="l.amount_repaid > 0 || l.status === 'ACTIVE' || l.status === 'LATE' || l.status === 'REPAID'"
                              [pct]="(l.amount_repaid / l.total_due) * 100"
                              [color]="l.status === 'LATE' ? 'warning' : 'success'"
                              [height]="5" [showLabel]="true" label="Repaid"
                              [subLabel]="'₹' + (l.amount_repaid | number:'1.2-2')"
                              [subLabelRight]="'of ₹' + (l.total_due | number:'1.2-2')">
            </app-progress-bar>
          </div>
          <div class="flex flex-wrap gap-3 mt-3 pt-3 border-t border-gray-100 dark:border-white/5 text-xs text-on-surface-muted">
            <span>Created {{ l.created_at | date:'mediumDate' }}</span>
            <span *ngIf="l.due_date">Due {{ l.due_date | date:'mediumDate' }}</span>
            <span class="text-success-600 dark:text-success-400" *ngIf="l.status === 'REPAID'">✓ Fully repaid</span>
            <span class="text-danger-600 dark:text-danger-400" *ngIf="l.status === 'DEFAULTED'">⚠ Defaulted</span>
          </div>
        </div>
      </div>

      <!-- Credit history section -->
      <div class="glass-card p-5" *ngIf="creditHistory().length">
        <h2 class="section-title mb-4">Credit score history</h2>
        <div class="space-y-2 max-h-64 overflow-y-auto scrollbar-thin pr-1">
          <div *ngFor="let h of creditHistory()" class="flex items-center gap-4 text-sm p-3 rounded-xl
               border border-gray-100 dark:border-white/10">
            <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                 [ngClass]="h.credit_score > h.previous_score ? 'bg-success-500' : h.credit_score < h.previous_score ? 'bg-danger-500' : 'bg-gray-400'">
              {{ h.credit_score > h.previous_score ? '↑' : h.credit_score < h.previous_score ? '↓' : '=' }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-bold">{{ h.credit_score }}</span>
                <span class="text-xs text-on-surface-muted">
                  ({{ h.credit_score > h.previous_score ? '+' : '' }}{{ h.credit_score - h.previous_score }})
                </span>
                <span class="text-2xs text-on-surface-muted">{{ h.events.join(', ') }}</span>
              </div>
              <p class="text-xs text-on-surface-muted truncate">{{ h.reason }}</p>
            </div>
            <span class="text-xs text-on-surface-muted flex-shrink-0">{{ h.created_at | date:'mediumDate' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Repay modal -->
    <app-modal [open]="repayModal()" title="Make a repayment" (close)="repayModal.set(false)">
      <div *ngIf="repayingLoan()" class="space-y-4">
        <div class="glass-panel p-4 text-sm space-y-2">
          <div class="flex justify-between"><span class="text-on-surface-muted">Remaining</span>
            <span class="font-bold text-brand-600 dark:text-brand-400">₹{{ remaining() | number:'1.2-2' }}</span>
          </div>
        </div>
        <div>
          <label class="input-label">Amount (₹)</label>
          <input type="number" class="input-field" [(ngModel)]="repayAmt"
                 [max]="remaining()" min="0.01" placeholder="Enter amount" />
        </div>
        <div class="flex gap-2">
          <button class="btn-secondary text-xs" (click)="repayAmt = remaining()">Pay all</button>
          <button class="btn-secondary text-xs" (click)="repayAmt = round(remaining() * 0.5)">50%</button>
        </div>
        <div class="flex gap-3">
          <button class="btn-secondary flex-1" (click)="repayModal.set(false)">Cancel</button>
          <button class="btn-primary flex-1" (click)="submitRepay()" [disabled]="submitting()">
            <app-spinner *ngIf="submitting()" mode="inline" size="sm"></app-spinner>
            Confirm
          </button>
        </div>
      </div>
    </app-modal>

    <!-- Schedule modal -->
    <app-modal [open]="scheduleModal()" title="Repayment schedule" (close)="scheduleModal.set(false)">
      <app-spinner *ngIf="schedLoading()" mode="page"></app-spinner>
      <div *ngIf="!schedLoading()" class="space-y-2 max-h-80 overflow-y-auto scrollbar-thin pr-1">
        <div *ngFor="let e of schedule()"
             class="flex justify-between items-center p-3 rounded-xl border"
             [ngClass]="{
               'border-success-500/30 bg-success-50 dark:bg-success-500/10': e.status === 'paid',
               'border-danger-500/30 bg-danger-50 dark:bg-danger-500/10': e.status === 'overdue',
               'border-brand-200 dark:border-brand-500/20 bg-brand-50 dark:bg-brand-500/8': e.status === 'due',
               'border-gray-200 dark:border-white/10': e.status === 'upcoming'
             }">
          <div class="flex items-center gap-3">
            <span>{{ e.status === 'paid' ? '✅' : e.status === 'overdue' ? '🔴' : e.status === 'due' ? '🟡' : '⬜' }}</span>
            <div>
              <p class="text-sm font-medium">Payment {{ e.payment_number }}</p>
              <p class="text-xs text-on-surface-muted">{{ e.due_date | date:'mediumDate' }}</p>
            </div>
          </div>
          <div class="text-right">
            <p class="font-semibold text-sm">₹{{ e.total | number:'1.2-2' }}</p>
            <p class="text-xs text-on-surface-muted capitalize">{{ e.status }}</p>
          </div>
        </div>
      </div>
    </app-modal>

    <!-- Blockchain verification modal -->
    <app-modal
      [open]="blockchainModal()"
      title="Blockchain Verification"
      [subtitle]="blockchainLoan() ? 'Loan #' + blockchainLoan()!.id.slice(-6) : ''"
      (close)="blockchainModal.set(false)"
    >
      <app-blockchain-verification
        *ngIf="blockchainLoan()"
        [loanId]="blockchainLoan()!.id"
      ></app-blockchain-verification>
    </app-modal>
  `,
})
export class BorrowerLoansComponent implements OnInit {
  loans         = signal<Loan[]>([]);
  creditHistory = signal<CreditHistoryEntry[]>([]);
  loading       = signal(true);
  submitting    = signal(false);
  statusFilter  = '';

  repayModal   = signal(false);
  repayingLoan = signal<Loan | null>(null);
  repayAmt     = 0;

  scheduleModal = signal(false);
  schedule      = signal<ScheduleEntry[]>([]);
  schedLoading  = signal(false);

  blockchainModal = signal(false);
  blockchainLoan  = signal<Loan | null>(null);

  remaining = computed(() => {
    const l = this.repayingLoan();
    if (!l) return 0;
    return Math.max(0, Math.round((l.total_due - l.amount_repaid) * 100) / 100);
  });

  readonly statuses = ['ACTIVE','LATE','REPAID','DEFAULTED','OPEN_FOR_FUNDING','PARTIALLY_FUNDED','REJECTED'];

  filtered = computed(() =>
    this.statusFilter
      ? this.loans().filter(l => l.status === this.statusFilter)
      : this.loans()
  );

  constructor(private api: ApiService, private toast: ToastService) {}

  ngOnInit() {
    this.api.listLoans({ mine: true }).subscribe({
      next:  (ls) => { this.loans.set(ls); this.loading.set(false); },
      error: ()   => { this.loading.set(false); },
    });
    this.api.myCreditScore().subscribe({
      next: (c) => this.creditHistory.set(c.history ?? []),
      error: () => {},
    });
  }

  openRepay(l: Loan) {
    this.repayingLoan.set(l);
    this.repayAmt = Math.round((l.total_due - l.amount_repaid) * 100) / 100;
    this.repayModal.set(true);
  }

  submitRepay() {
    const l = this.repayingLoan()!;
    if (!this.repayAmt || this.repayAmt <= 0) return;
    this.submitting.set(true);
    this.api.repayLoan(l.id, this.repayAmt).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.repayModal.set(false);
        this.toast.success('Payment recorded', `Credit: ${res.credit_score} · Limit: ₹${res.borrowing_limit.toLocaleString()}`);
        this.api.listLoans({ mine: true }).subscribe(ls => this.loans.set(ls));
      },
      error: (err) => {
        this.submitting.set(false);
        this.toast.error('Payment failed', err?.error?.detail ?? 'Error');
      },
    });
  }

  openSchedule(l: Loan) {
    this.scheduleModal.set(true);
    this.schedule.set([]);
    this.schedLoading.set(true);
    this.api.getLoanSchedule(l.id).subscribe({
      next:  (s) => { this.schedule.set(s); this.schedLoading.set(false); },
      error: ()  => { this.schedLoading.set(false); },
    });
  }

  openBlockchain(l: Loan) {
    this.blockchainLoan.set(l);
    this.blockchainModal.set(true);
  }

  round(n: number) { return Math.round(n * 100) / 100; }
}
