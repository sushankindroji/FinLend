import {
  Component, OnInit, signal, computed, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { NavbarComponent } from '../../shared/components/navbar.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';
import { ProgressBarComponent } from '../../shared/components/progress-bar.component';
import { LoadingSpinnerComponent } from '../../shared/components/loading-spinner.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import { ModalComponent } from '../../shared/components/modal.component';
import type { User, Loan, Transaction, Analytics, RiskFlag } from '../../core/models';

type AdminTab = 'overview' | 'users' | 'loans' | 'transactions' | 'flags';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Default,
  imports: [
    CommonModule, FormsModule,
    NavbarComponent, StatusBadgeComponent, ProgressBarComponent,
    LoadingSpinnerComponent, EmptyStateComponent, ModalComponent,
  ],
  template: `
    <app-navbar></app-navbar>

    <div class="page-container space-y-6 animate-fade-in-up">

      <!-- ══ KPI CARDS ════════════════════════════════════════════════════ -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div class="stat-card glass-card-hover">
          <span class="stat-label">Total loans</span>
          <span class="stat-value">{{ analytics()?.total_loans ?? '—' }}</span>
        </div>
        <div class="stat-card glass-card-hover">
          <span class="stat-label">Borrowers</span>
          <span class="stat-value">{{ analytics()?.borrower_count ?? '—' }}</span>
        </div>
        <div class="stat-card glass-card-hover">
          <span class="stat-label">Lenders</span>
          <span class="stat-value">{{ analytics()?.lender_count ?? '—' }}</span>
        </div>
        <div class="stat-card glass-card-hover relative overflow-hidden">
          <div *ngIf="openFlagsCount() > 0"
               class="absolute top-2 right-2 w-5 h-5 rounded-full bg-danger-500
                      flex items-center justify-center text-2xs text-white font-bold">
            {{ openFlagsCount() }}
          </div>
          <span class="stat-label">Open flags</span>
          <span class="stat-value"
                [class.text-danger-600]="openFlagsCount() > 0"
                [class.dark:text-danger-400]="openFlagsCount() > 0">
            {{ openFlagsCount() }}
          </span>
        </div>
      </div>



      <!-- ══ OVERVIEW TAB ═════════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'overview'" class="animate-fade-in space-y-4">

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">

          <!-- Loan status distribution -->
          <div class="glass-card p-5">
            <h3 class="section-title mb-4">Loan status distribution</h3>
            <app-spinner *ngIf="analyticsLoading()" mode="page"></app-spinner>
            <div *ngIf="!analyticsLoading()" class="space-y-2.5">
              <div *ngFor="let entry of statusEntries()" class="space-y-1">
                <div class="flex justify-between text-sm">
                  <span class="flex items-center gap-2">
                    <app-status-badge [value]="entry.key" type="status"></app-status-badge>
                  </span>
                  <span class="font-semibold tabular-nums">{{ entry.value }}</span>
                </div>
                <app-progress-bar
                  [pct]="(entry.value / (analytics()?.total_loans || 1)) * 100"
                  color="brand"
                  [height]="4"
                ></app-progress-bar>
              </div>
            </div>
          </div>

          <!-- Risk distribution -->
          <div class="glass-card p-5">
            <h3 class="section-title mb-4">Risk distribution</h3>
            <app-spinner *ngIf="analyticsLoading()" mode="page"></app-spinner>
            <div *ngIf="!analyticsLoading()" class="space-y-3">
              <div *ngFor="let entry of riskEntries()">
                <div class="flex justify-between items-center mb-1">
                  <app-status-badge [value]="entry.key" type="risk"></app-status-badge>
                  <span class="text-sm font-semibold">{{ entry.value }}</span>
                </div>
                <app-progress-bar
                  [pct]="(entry.value / (analytics()?.total_loans || 1)) * 100"
                  [color]="entry.key === 'LOW' ? 'success' : entry.key === 'HIGH' ? 'danger' : 'warning'"
                  [height]="5"
                ></app-progress-bar>
              </div>
              <div class="empty-state py-6" *ngIf="!riskEntries().length">
                <p class="text-sm text-on-surface-muted">No risk data yet</p>
              </div>
            </div>

            <!-- Money stats -->
            <div *ngIf="!analyticsLoading()" class="grid grid-cols-2 gap-3 mt-4 pt-4
                        border-t border-gray-100 dark:border-white/10">
              <div>
                <p class="stat-label">Total funded</p>
                <p class="font-bold text-lg">₹{{ (analytics()?.total_amount_funded ?? 0) | number:'1.0-0' }}</p>
              </div>
              <div>
                <p class="stat-label">Total repaid</p>
                <p class="font-bold text-lg text-success-600 dark:text-success-400">
                  ₹{{ (analytics()?.total_amount_repaid ?? 0) | number:'1.0-0' }}
                </p>
              </div>
            </div>
          </div>

          <!-- Credit score distribution chart -->
          <div class="glass-card p-5 md:col-span-2">
            <h3 class="section-title mb-4">Credit score distribution</h3>
            <div *ngIf="!analyticsLoading()" class="flex items-end gap-2 h-24">
              <div *ngFor="let entry of creditBuckets()" class="flex flex-col items-center gap-1 flex-1">
                <span class="text-xs font-semibold tabular-nums text-on-surface">{{ entry.value }}</span>
                <div class="w-full rounded-t-lg transition-all duration-500"
                     [ngClass]="entry.color"
                     [style.height.px]="bucketHeight(entry.value)">
                </div>
                <span class="text-2xs text-on-surface-muted text-center leading-tight">{{ entry.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ══ USERS TAB ════════════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'users'" class="animate-fade-in">
        <div class="glass-card overflow-hidden">
          <div class="p-5 pb-3 border-b border-gray-100 dark:border-white/10 flex items-center justify-between">
            <h3 class="section-title">All users ({{ users().length }})</h3>
            <div class="relative">
              <input type="search" class="input-field text-sm w-48 pl-8"
                     [(ngModel)]="userSearch" placeholder="Search…" />
              <span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-muted text-sm">🔍</span>
            </div>
          </div>
          <app-spinner *ngIf="usersLoading()" mode="page"></app-spinner>
          <div *ngIf="!usersLoading()" class="overflow-x-auto scrollbar-thin max-h-[500px]">
            <table class="table-base">
              <thead class="sticky top-0 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
                <tr>
                  <th class="table-th">Name</th>
                  <th class="table-th">Email</th>
                  <th class="table-th">Role</th>
                  <th class="table-th">Credit score</th>
                  <th class="table-th">Balance</th>
                  <th class="table-th">Joined</th>
                  <th class="table-th"></th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let u of filteredUsers()" class="table-row-hover">
                  <td class="table-td font-medium">{{ u.name }}</td>
                  <td class="table-td text-on-surface-muted text-xs">{{ u.email }}</td>
                  <td class="table-td">
                    <app-status-badge [value]="u.role" type="role"></app-status-badge>
                  </td>
                  <td class="table-td tabular-nums">{{ u.credit_score ?? '—' }}</td>
                  <td class="table-td">{{ u.lending_balance != null ? ('₹' + (u.lending_balance | number:'1.0-0')) : '—' }}</td>
                  <td class="table-td text-xs text-on-surface-muted">{{ u.created_at | date:'mediumDate' }}</td>
                  <td class="table-td">
                    <button class="btn-ghost text-xs px-2 py-1" (click)="flagUser(u)">🚩 Flag</button>
                  </td>
                </tr>
                <tr *ngIf="!filteredUsers().length">
                  <td colspan="7" class="text-center py-8 text-on-surface-muted text-sm">No users found</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ LOANS TAB ════════════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'loans'" class="animate-fade-in">
        <div class="glass-card overflow-hidden">
          <div class="p-5 pb-3 border-b border-gray-100 dark:border-white/10 flex items-center justify-between flex-wrap gap-3">
            <h3 class="section-title">All loans ({{ loans().length }})</h3>
            <div class="flex gap-2 flex-wrap">
              <select class="input-field text-sm w-40" [(ngModel)]="loanStatusFilter">
                <option value="">All statuses</option>
                <option *ngFor="let s of loanStatuses" [value]="s">{{ s }}</option>
              </select>
              <button class="btn-secondary text-xs" (click)="exportLoansCSV()">📥 Export CSV</button>
            </div>
          </div>
          <app-spinner *ngIf="loansLoading()" mode="page"></app-spinner>
          <div *ngIf="!loansLoading()" class="overflow-x-auto scrollbar-thin max-h-[500px]">
            <table class="table-base">
              <thead class="sticky top-0 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
                <tr>
                  <th class="table-th">ID</th>
                  <th class="table-th">Borrower</th>
                  <th class="table-th">Amount</th>
                  <th class="table-th">Status</th>
                  <th class="table-th">Risk</th>
                  <th class="table-th">Funded</th>
                  <th class="table-th">Created</th>
                  <th class="table-th"></th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let l of filteredLoans()" class="table-row-hover">
                  <td class="table-td font-mono text-xs text-on-surface-muted">#{{ l.id.slice(-6) }}</td>
                  <td class="table-td text-sm">{{ l.borrower_name ?? '—' }}</td>
                  <td class="table-td font-semibold tabular-nums">₹{{ l.amount | number }}</td>
                  <td class="table-td">
                    <app-status-badge [value]="l.status" type="status"></app-status-badge>
                  </td>
                  <td class="table-td">
                    <app-status-badge *ngIf="l.risk_category" [value]="l.risk_category" type="risk"></app-status-badge>
                    <span *ngIf="!l.risk_category" class="text-on-surface-muted text-xs">—</span>
                  </td>
                  <td class="table-td">
                    <app-progress-bar [pct]="(l.amount_funded / l.amount) * 100"
                                      color="brand" [height]="4"></app-progress-bar>
                  </td>
                  <td class="table-td text-xs text-on-surface-muted">{{ l.created_at | date:'mediumDate' }}</td>
                  <td class="table-td">
                    <button class="btn-ghost text-xs px-2 py-1" (click)="flagLoan(l)">🚩 Flag</button>
                  </td>
                </tr>
                <tr *ngIf="!filteredLoans().length">
                  <td colspan="8" class="text-center py-8 text-on-surface-muted text-sm">No loans found</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ TRANSACTIONS TAB ═════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'transactions'" class="animate-fade-in">
        <div class="glass-card overflow-hidden">
          <div class="p-5 pb-3 border-b border-gray-100 dark:border-white/10 flex items-center justify-between flex-wrap gap-3">
            <h3 class="section-title">Blockchain transactions ({{ transactions().length }})</h3>
            <button class="btn-secondary text-xs" (click)="exportTransactionsCSV()">📥 Export CSV</button>
          </div>
          <app-spinner *ngIf="txLoading()" mode="page"></app-spinner>
          <div *ngIf="!txLoading()" class="overflow-x-auto scrollbar-thin max-h-[500px]">
            <table class="table-base">
              <thead class="sticky top-0 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
                <tr>
                  <th class="table-th">Type</th>
                  <th class="table-th">Loan</th>
                  <th class="table-th">Amount</th>
                  <th class="table-th">Chain mode</th>
                  <th class="table-th">Tx hash</th>
                  <th class="table-th">Time</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let t of transactions()" class="table-row-hover">
                  <td class="table-td">
                    <span class="badge"
                          [ngClass]="t.type === 'FUNDING' ? 'badge-brand' : 'badge-success'">
                      {{ t.type === 'FUNDING' ? '💰' : '💸' }} {{ t.type }}
                    </span>
                  </td>
                  <td class="table-td font-mono text-xs text-on-surface-muted">#{{ t.loan_id.slice(-6) }}</td>
                  <td class="table-td font-semibold tabular-nums">₹{{ t.amount | number:'1.2-2' }}</td>
                  <td class="table-td">
                    <app-status-badge [value]="t.chain_mode ?? ''" type="chain"></app-status-badge>
                  </td>
                  <td class="table-td max-w-[180px]">
                    <a *ngIf="t.explorer_url" [href]="t.explorer_url" target="_blank" rel="noopener"
                       class="font-mono text-2xs text-brand-600 dark:text-brand-400 hover:underline truncate block">
                      {{ t.tx_hash }}
                    </a>
                    <span *ngIf="!t.explorer_url"
                          class="font-mono text-2xs text-on-surface-muted truncate block"
                          [title]="t.tx_hash">
                      {{ t.tx_hash ? t.tx_hash.slice(0, 20) + '…' : '—' }}
                    </span>
                  </td>
                  <td class="table-td text-xs text-on-surface-muted">{{ t.created_at | date:'short' }}</td>
                </tr>
                <tr *ngIf="!transactions().length">
                  <td colspan="6" class="text-center py-8 text-on-surface-muted text-sm">No transactions yet</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══ FLAGS TAB ════════════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'flags'" class="animate-fade-in space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="section-title">Fraud & risk flags</h2>
            <p class="section-subtitle">{{ openFlagsCount() }} open · {{ flags().length }} total</p>
          </div>
          <button class="btn-primary text-sm" (click)="createFlagModal.set(true)">
            🚩 Create flag
          </button>
        </div>

        <app-spinner *ngIf="flagsLoading()" mode="page"></app-spinner>
        <app-empty-state *ngIf="!flagsLoading() && !flags().length"
          icon="🚩" title="No flags"
          subtitle="Flag suspicious loans or users for review.">
        </app-empty-state>

        <div *ngIf="!flagsLoading() && flags().length" class="space-y-3">
          <div *ngFor="let f of flags()"
               class="glass-panel p-4 flex items-start gap-4"
               [ngClass]="f.resolved ? 'opacity-60' : ''">
            <div class="flex-shrink-0 text-2xl">
              {{ f.severity === 'CRITICAL' ? '🔴' : f.severity === 'HIGH' ? '🟠' : f.severity === 'MEDIUM' ? '🟡' : '🟢' }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-semibold text-sm text-on-surface">{{ f.flag_type }}</span>
                <span class="badge"
                      [ngClass]="f.severity === 'CRITICAL' ? 'badge-danger'
                                : f.severity === 'HIGH' ? 'badge-warning'
                                : f.severity === 'MEDIUM' ? 'badge-info'
                                : 'badge-gray'">
                  {{ f.severity }}
                </span>
                <span class="badge badge-gray">{{ f.entity_type }}: #{{ f.entity_id.slice(-6) }}</span>
                <span *ngIf="f.resolved" class="badge badge-success">✓ Resolved</span>
              </div>
              <p class="text-xs text-on-surface-muted mt-1">{{ f.reason }}</p>
              <p class="text-xs text-on-surface-muted mt-0.5">{{ f.created_at | date:'medium' }}</p>
            </div>
            <button *ngIf="!f.resolved"
                    class="btn-secondary text-xs px-3 py-1.5 flex-shrink-0"
                    (click)="resolveFlag(f)">
              ✓ Resolve
            </button>
          </div>
        </div>
      </div>

    </div>

    <!-- ══ CREATE FLAG MODAL ════════════════════════════════════════════ -->
    <app-modal
      [open]="createFlagModal()"
      title="Create risk flag"
      subtitle="Flag a loan or user for review"
      (close)="createFlagModal.set(false)"
    >
      <div class="space-y-4">
        <div>
          <label class="input-label">Entity type</label>
          <select class="input-field" [(ngModel)]="newFlag.entity_type">
            <option value="loan">Loan</option>
            <option value="user">User</option>
          </select>
        </div>
        <div>
          <label class="input-label">Entity ID</label>
          <input class="input-field" [(ngModel)]="newFlag.entity_id"
                 placeholder="Paste the full ID" />
        </div>
        <div>
          <label class="input-label">Flag type</label>
          <select class="input-field" [(ngModel)]="newFlag.flag_type">
            <option value="SUSPECTED_FRAUD">Suspected fraud</option>
            <option value="IDENTITY_RISK">Identity risk</option>
            <option value="RAPID_REQUESTS">Rapid loan requests</option>
            <option value="OVERPAYMENT_ATTEMPT">Overpayment attempt</option>
            <option value="UNUSUAL_PATTERN">Unusual pattern</option>
            <option value="MANUAL_REVIEW">Manual review</option>
          </select>
        </div>
        <div>
          <label class="input-label">Severity</label>
          <select class="input-field" [(ngModel)]="newFlag.severity">
            <option value="LOW">Low</option>
            <option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option>
            <option value="CRITICAL">Critical</option>
          </select>
        </div>
        <div>
          <label class="input-label">Reason / notes</label>
          <textarea class="input-field resize-none" rows="3"
                    [(ngModel)]="newFlag.reason"
                    placeholder="Describe why this is being flagged…"></textarea>
        </div>
        <div class="flex gap-3 pt-2">
          <button class="btn-secondary flex-1" (click)="createFlagModal.set(false)">Cancel</button>
          <button class="btn-danger flex-1" (click)="submitFlag()" [disabled]="submittingFlag()">
            <app-spinner *ngIf="submittingFlag()" mode="inline" size="sm"></app-spinner>
            🚩 Create flag
          </button>
        </div>
      </div>
    </app-modal>
  `,
})
export class AdminDashboardComponent implements OnInit {
  analytics  = signal<Analytics | null>(null);
  users      = signal<User[]>([]);
  loans      = signal<Loan[]>([]);
  transactions = signal<Transaction[]>([]);
  flags      = signal<RiskFlag[]>([]);

  analyticsLoading = signal(true);
  usersLoading     = signal(false);
  loansLoading     = signal(false);
  txLoading        = signal(false);
  flagsLoading     = signal(false);

  activeTab: AdminTab = 'overview';
  userSearch = '';
  loanStatusFilter = '';
  createFlagModal = signal(false);
  submittingFlag  = signal(false);

  newFlag: Partial<RiskFlag> = {
    entity_type: 'loan',
    entity_id: '',
    flag_type: 'SUSPECTED_FRAUD',
    severity: 'MEDIUM',
    reason: '',
  };

  readonly loanStatuses = [
    'REQUESTED','CREDIT_CHECK','APPROVED','REJECTED',
    'OPEN_FOR_FUNDING','PARTIALLY_FUNDED','FUNDED',
    'ACTIVE','LATE','REPAID','DEFAULTED',
  ];

  openFlagsCount = computed(() => this.flags().filter(f => !f.resolved).length);

  statusEntries = computed(() =>
    Object.entries(this.analytics()?.loan_status_distribution ?? {})
      .map(([key, value]) => ({ key, value }))
      .sort((a, b) => b.value - a.value)
  );

  riskEntries = computed(() =>
    Object.entries(this.analytics()?.risk_distribution ?? {})
      .map(([key, value]) => ({ key, value }))
  );

  creditBuckets = computed(() => {
    const dist = this.analytics()?.credit_score_distribution ?? {};
    return [
      { key: '300',  label: '300–499\n(High risk)',  color: 'bg-danger-400',  value: dist['300']  ?? 0 },
      { key: '500',  label: '500–649\n(Medium)',      color: 'bg-warning-400', value: dist['500']  ?? 0 },
      { key: '650',  label: '650–749\n(Low risk)',    color: 'bg-brand-400',   value: dist['650']  ?? 0 },
      { key: '750',  label: '750–850\n(Excellent)',   color: 'bg-success-400', value: dist['750']  ?? 0 },
    ];
  });

  bucketHeight(v: number): number {
    const max = Math.max(...this.creditBuckets().map(b => b.value), 1);
    return Math.max(4, (v / max) * 72);
  }

  filteredUsers = computed(() => {
    const q = this.userSearch.toLowerCase();
    if (!q) return this.users();
    return this.users().filter(u =>
      u.name.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q)
    );
  });

  filteredLoans = computed(() => {
    if (!this.loanStatusFilter) return this.loans();
    return this.loans().filter(l => l.status === this.loanStatusFilter);
  });

  constructor(
    private api: ApiService,
    private toast: ToastService,
    private route: ActivatedRoute,
  ) {}

  ngOnInit() {
    // Determine which tab to show based on current route
    this.route.url.subscribe((segments) => {
      if (segments.length > 1) {
        const tabPath = segments[1].path;
        if (tabPath === 'users') this.activeTab = 'users';
        else if (tabPath === 'loans') this.activeTab = 'loans';
        else if (tabPath === 'flags') this.activeTab = 'flags';
        else this.activeTab = 'overview';
      } else {
        this.activeTab = 'overview';
      }
      this.switchTab(this.activeTab);
    });
    this.loadOverview();
    this.loadFlags();
  }

  switchTab(tab: AdminTab) {
    this.activeTab = tab;
    if (tab === 'users'        && !this.users().length)        this.loadUsers();
    if (tab === 'loans'        && !this.loans().length)        this.loadLoans();
    if (tab === 'transactions' && !this.transactions().length) this.loadTransactions();
    if (tab === 'flags')       this.loadFlags();
  }

  loadOverview() {
    this.analyticsLoading.set(true);
    this.api.adminAnalytics().subscribe({
      next:  (a) => { this.analytics.set(a); this.analyticsLoading.set(false); },
      error: ()  => { this.analyticsLoading.set(false); },
    });
  }

  loadUsers() {
    this.usersLoading.set(true);
    this.api.adminUsers().subscribe({
      next:  (u) => { this.users.set(u); this.usersLoading.set(false); },
      error: ()  => { this.usersLoading.set(false); },
    });
  }

  loadLoans() {
    this.loansLoading.set(true);
    this.api.adminLoans().subscribe({
      next:  (ls) => { this.loans.set(ls); this.loansLoading.set(false); },
      error: ()   => { this.loansLoading.set(false); },
    });
  }

  loadTransactions() {
    this.txLoading.set(true);
    this.api.adminTransactions().subscribe({
      next:  (txs) => { this.transactions.set(txs); this.txLoading.set(false); },
      error: ()    => { this.txLoading.set(false); },
    });
  }

  loadFlags() {
    this.flagsLoading.set(true);
    this.api.adminFlags().subscribe({
      next:  (fl) => { this.flags.set(fl); this.flagsLoading.set(false); },
      error: ()   => { this.flagsLoading.set(false); },
    });
  }

  flagUser(u: User) {
    this.newFlag = { entity_type: 'user', entity_id: u.id, flag_type: 'MANUAL_REVIEW', severity: 'MEDIUM', reason: '' };
    this.createFlagModal.set(true);
  }

  flagLoan(l: Loan) {
    this.newFlag = { entity_type: 'loan', entity_id: l.id, flag_type: 'SUSPECTED_FRAUD', severity: 'MEDIUM', reason: '' };
    this.createFlagModal.set(true);
  }

  submitFlag() {
    if (!this.newFlag.entity_id || !this.newFlag.reason) {
      this.toast.warning('Incomplete', 'Fill in Entity ID and Reason.');
      return;
    }
    this.submittingFlag.set(true);
    this.api.createFlag(this.newFlag).subscribe({
      next: (f) => {
        this.submittingFlag.set(false);
        this.createFlagModal.set(false);
        this.flags.update(fl => [f, ...fl]);
        this.toast.success('Flag created', `${f.flag_type} · ${f.severity}`);
        this.newFlag = { entity_type: 'loan', entity_id: '', flag_type: 'SUSPECTED_FRAUD', severity: 'MEDIUM', reason: '' };
      },
      error: (err) => {
        this.submittingFlag.set(false);
        this.toast.error('Failed to create flag', err?.error?.detail ?? 'Unknown error');
      },
    });
  }

  resolveFlag(f: RiskFlag) {
    this.api.resolveFlag(f.id).subscribe({
      next: (updated) => {
        this.flags.update(fl => fl.map(x => x.id === updated.id ? updated : x));
        this.toast.success('Flag resolved', `${f.flag_type} marked as resolved.`);
      },
      error: (err) => this.toast.error('Failed to resolve', err?.error?.detail ?? 'Unknown error'),
    });
  }

  exportLoansCSV() {
    this.api.adminExport('csv', 'loans').subscribe({
      next: (blob) => this._downloadBlob(blob, 'finlend-loans.csv'),
      error: () => this.toast.error('Export failed'),
    });
  }

  exportTransactionsCSV() {
    this.api.adminExport('csv', 'transactions').subscribe({
      next: (blob) => this._downloadBlob(blob, 'finlend-transactions.csv'),
      error: () => this.toast.error('Export failed'),
    });
  }

  private _downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    this.toast.success('Export ready', `${filename} downloaded.`);
  }
}
