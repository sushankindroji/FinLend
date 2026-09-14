import {
  Component, OnInit, signal, computed, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule } from '@angular/common';
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
import type { User, Loan, Transaction, AutoInvestPrefs } from '../../core/models';

type DashTab = 'marketplace' | 'portfolio' | 'auto-invest';

@Component({
  selector: 'app-lender-dashboard',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Default,
  imports: [
    CommonModule, FormsModule, RouterLink,
    NavbarComponent, StatusBadgeComponent, ProgressBarComponent,
    LoadingSpinnerComponent, EmptyStateComponent, ModalComponent,
  ],
  template: `
    <app-navbar></app-navbar>

    <div class="page-container space-y-6 animate-fade-in-up">

      <!-- ══ STATS ROW ═══════════════════════════════════════════════════ -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div class="stat-card glass-card-hover relative overflow-hidden">
          <div class="absolute inset-0 bg-gradient-to-br from-success-500/8 to-transparent rounded-xl2"></div>
          <span class="stat-label">Available balance</span>
          <span class="stat-value text-success-600 dark:text-success-400">
            ₹{{ (me()?.lending_balance ?? 0) | number:'1.0-0' }}
          </span>
          <p class="text-xs text-on-surface-muted">Simulated demo funds</p>
        </div>

        <div class="stat-card glass-card-hover">
          <span class="stat-label">Total invested</span>
          <span class="stat-value">₹{{ totalInvested() | number:'1.0-0' }}</span>
          <p class="text-xs text-success-600 dark:text-success-400 mt-0.5">
            +₹{{ totalExpectedReturn() | number:'1.0-0' }} expected
          </p>
        </div>

        <div class="stat-card glass-card-hover">
          <span class="stat-label">Active investments</span>
          <span class="stat-value">{{ activeInvestments().length }}</span>
          <p class="text-xs text-on-surface-muted mt-0.5">
            {{ completedInvestments().length }} completed
          </p>
        </div>

        <div class="stat-card glass-card-hover">
          <span class="stat-label">Avg. return rate</span>
          <span class="stat-value">10%</span>
          <p class="text-xs text-on-surface-muted mt-0.5">Fixed platform rate</p>
        </div>
      </div>

      <!-- ══ TAB BAR ══════════════════════════════════════════════════════ -->
      <div class="flex gap-1 bg-gray-100 dark:bg-white/10 p-1 rounded-xl self-start">
        <button *ngFor="let t of tabs"
                class="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200"
                [ngClass]="activeTab === t.id
                  ? 'bg-white dark:bg-white/15 shadow-soft text-on-surface'
                  : 'text-on-surface-muted hover:text-on-surface'"
                (click)="activeTab = t.id">
          {{ t.icon }} {{ t.label }}
          <span *ngIf="t.id === 'marketplace' && marketplace().length"
                class="ml-1 badge badge-brand text-2xs">
            {{ marketplace().length }}
          </span>
        </button>
      </div>

      <!-- ══ MARKETPLACE TAB ══════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'marketplace'" class="animate-fade-in space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="section-title">Loan marketplace</h2>
            <p class="section-subtitle">{{ marketplace().length }} loans open for funding</p>
          </div>
          <!-- Filter by risk -->
          <div class="flex gap-1 bg-gray-100 dark:bg-white/10 p-1 rounded-xl">
            <button *ngFor="let f of riskFilters"
                    class="px-3 py-1 rounded-lg text-xs font-medium transition-all duration-200"
                    [ngClass]="riskFilter === f
                      ? 'bg-white dark:bg-white/15 shadow-soft text-on-surface'
                      : 'text-on-surface-muted hover:text-on-surface'"
                    (click)="riskFilter = f">
              {{ f }}
            </button>
          </div>
        </div>

        <app-spinner *ngIf="marketLoading()" mode="page" label="Loading marketplace…"></app-spinner>

        <app-empty-state *ngIf="!marketLoading() && !filteredMarketplace().length"
          icon="🛒" title="No loans available"
          subtitle="Check back soon — new loan requests appear here automatically.">
        </app-empty-state>

        <div *ngIf="!marketLoading()" class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div *ngFor="let l of filteredMarketplace()"
               class="glass-panel p-4 glass-card-hover flex flex-col gap-3">
            <!-- Header -->
            <div class="flex items-start justify-between">
              <div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-xl font-bold text-on-surface">₹{{ l.amount | number }}</span>
                  <span class="text-sm text-on-surface-muted">/ {{ l.duration_days }}d</span>
                </div>
                <p class="text-xs text-on-surface-muted mt-0.5">
                  {{ l.borrower_name ?? 'Anonymous' }} · {{ l.purpose || 'General' }}
                </p>
              </div>
              <div class="flex flex-col gap-1 items-end">
                <app-status-badge [value]="l.status" type="status"></app-status-badge>
                <app-status-badge *ngIf="l.risk_category" [value]="l.risk_category" type="risk" [dot]="true"></app-status-badge>
              </div>
            </div>

            <!-- Funding progress -->
            <div>
              <div class="flex justify-between text-xs text-on-surface-muted mb-1.5">
                <span>₹{{ l.amount_funded | number }} funded</span>
                <span>₹{{ l.amount - l.amount_funded | number }} remaining</span>
              </div>
              <app-progress-bar
                [pct]="(l.amount_funded / l.amount) * 100"
                color="brand"
                [height]="6"
              ></app-progress-bar>
            </div>

            <!-- Returns preview -->
            <div class="flex gap-3 text-xs bg-success-50 dark:bg-success-500/10
                        rounded-xl p-3 border border-success-500/20">
              <span class="text-success-600 dark:text-success-400">💹</span>
              <div>
                <span class="font-medium text-on-surface">10% return</span>
                <span class="text-on-surface-muted"> · if fully repaid on time</span>
              </div>
            </div>

            <!-- Fund input -->
            <div class="flex gap-2 mt-auto">
              <input
                type="number"
                class="input-field w-32 text-sm"
                [placeholder]="'Max ₹' + (l.amount - l.amount_funded | number)"
                [(ngModel)]="fundAmounts[l.id]"
                [max]="l.amount - l.amount_funded"
                min="1"
              />
              <button class="btn-primary flex-1 text-sm"
                      (click)="fund(l)"
                      [disabled]="submitting()">
                <app-spinner *ngIf="submitting()" mode="inline" size="xs"></app-spinner>
                💰 Fund
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ══ PORTFOLIO TAB ════════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'portfolio'" class="animate-fade-in space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="section-title">My portfolio</h2>
            <p class="section-subtitle">{{ investments().length }} total investments</p>
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

        <!-- Portfolio analytics cards -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4" *ngIf="investments().length">
          <div class="glass-card p-4 space-y-1">
            <p class="stat-label">Capital deployed</p>
            <p class="stat-value">₹{{ totalInvested() | number:'1.0-0' }}</p>
          </div>
          <div class="glass-card p-4 space-y-1">
            <p class="stat-label">Expected returns</p>
            <p class="stat-value text-success-600 dark:text-success-400">
              +₹{{ totalExpectedReturn() | number:'1.0-0' }}
            </p>
          </div>
          <div class="glass-card p-4 space-y-1">
            <p class="stat-label">ROI projection</p>
            <p class="stat-value">{{ portfolioROI() | number:'1.1-1' }}%</p>
          </div>
        </div>

        <!-- Returns over time chart (SVG bar chart) -->
        <div *ngIf="monthlyReturns().length" class="glass-card p-6">
          <h3 class="section-title mb-4">Returns over time</h3>
          <div class="flex items-end gap-1 h-32 overflow-x-auto scrollbar-thin pb-1">
            <div *ngFor="let m of monthlyReturns()"
                 class="flex flex-col items-center gap-1 flex-shrink-0 min-w-[36px]">
              <span class="text-2xs text-on-surface-muted">
                ₹{{ m.amount | number:'1.0-0' }}
              </span>
              <div
                class="w-7 rounded-t-lg bg-brand-400 dark:bg-brand-500 transition-all duration-500
                       hover:bg-brand-500 dark:hover:bg-brand-400 cursor-default"
                [style.height.px]="barHeight(m.amount)"
                [title]="m.label + ': ₹' + m.amount"
              ></div>
              <span class="text-2xs text-on-surface-muted">{{ m.label }}</span>
            </div>
          </div>
          <p class="text-xs text-on-surface-muted mt-2">
            Monthly funding activity (simulated data based on your investments)
          </p>
        </div>

        <!-- Investments table -->
        <div class="glass-card overflow-hidden">
          <div class="p-5 pb-3 border-b border-gray-100 dark:border-white/10">
            <h3 class="section-title">Investment details</h3>
          </div>
          <app-spinner *ngIf="portfolioLoading()" mode="page" label="Loading portfolio…"></app-spinner>
          <app-empty-state *ngIf="!portfolioLoading() && !investments().length"
            icon="📈" title="No investments yet"
            subtitle="Go to the Marketplace tab and fund your first loan.">
          </app-empty-state>

          <div *ngIf="!portfolioLoading() && investments().length"
               class="overflow-x-auto scrollbar-thin">
            <table class="table-base">
              <thead>
                <tr>
                  <th class="table-th">Loan</th>
                  <th class="table-th">Invested</th>
                  <th class="table-th">Expected return</th>
                  <th class="table-th">Tx hash</th>
                  <th class="table-th">Date</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let tx of investments()" class="table-row-hover">
                  <td class="table-td">
                    <span class="font-mono text-xs text-on-surface-muted">
                      #{{ tx.loan_id.slice(-6) }}
                    </span>
                  </td>
                  <td class="table-td font-semibold">₹{{ tx.amount | number:'1.2-2' }}</td>
                  <td class="table-td text-success-600 dark:text-success-400 font-medium">
                    ₹{{ tx.expected_return | number:'1.2-2' }}
                  </td>
                  <td class="table-td">
                    <span class="font-mono text-2xs text-on-surface-muted max-w-[120px] truncate block"
                          [title]="tx.tx_hash">
                      {{ tx.tx_hash ? tx.tx_hash.slice(0, 14) + '…' : '—' }}
                    </span>
                  </td>
                  <td class="table-td text-xs text-on-surface-muted">
                    {{ tx.created_at | date:'mediumDate' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Export button -->
        <div *ngIf="investments().length" class="flex justify-end gap-2">
          <button class="btn-secondary text-sm" (click)="exportCSV()">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none"
                 viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5
                       a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414
                       a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
            Export CSV
          </button>
        </div>
      </div>

      <!-- ══ AUTO-INVEST TAB ══════════════════════════════════════════════ -->
      <div *ngIf="activeTab === 'auto-invest'" class="animate-fade-in">
        <div class="glass-card p-6 max-w-xl space-y-6">
          <div>
            <h2 class="section-title">Auto-invest preferences</h2>
            <p class="section-subtitle">
              When enabled, FinLend automatically funds loans matching your criteria.
            </p>
          </div>

          <app-spinner *ngIf="prefsLoading()" mode="page" label="Loading preferences…"></app-spinner>

          <div *ngIf="!prefsLoading()" class="space-y-5">
            <!-- Enable toggle -->
            <div class="flex items-center justify-between p-4 rounded-xl border
                        border-gray-200 dark:border-white/10">
              <div>
                <p class="font-semibold text-on-surface">Enable auto-invest</p>
                <p class="text-xs text-on-surface-muted mt-0.5">
                  Automatically deploy capital when matching loans appear
                </p>
              </div>
              <button
                class="relative w-11 h-6 rounded-full transition-all duration-300 focus-ring flex-shrink-0"
                [ngClass]="prefs().enabled ? 'bg-brand-500' : 'bg-gray-300 dark:bg-white/20'"
                (click)="toggleAutoInvest()"
                [attr.aria-checked]="prefs().enabled"
                role="switch"
              >
                <span class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all duration-300"
                      [ngClass]="prefs().enabled ? 'left-5' : 'left-0.5'">
                </span>
              </button>
            </div>

            <div [ngClass]="prefs().enabled ? '' : 'opacity-50 pointer-events-none'"
                 class="space-y-4 transition-opacity duration-300">

              <!-- Max per loan -->
              <div>
                <label class="input-label">Max amount per loan (₹)</label>
                <input type="number" class="input-field"
                       [value]="prefs().max_per_loan"
                       (input)="setPref('max_per_loan', +$any($event.target).value)"
                       min="100" step="100" />
                <p class="input-hint">Maximum you'll invest in any single loan</p>
              </div>

              <!-- Min credit score -->
              <div>
                <label class="input-label">Minimum borrower credit score</label>
                <input type="number" class="input-field"
                       [value]="prefs().min_credit_score"
                       (input)="setPref('min_credit_score', +$any($event.target).value)"
                       min="300" max="850" step="50" />
                <div class="flex justify-between text-xs text-on-surface-muted mt-1">
                  <span>300 (high-risk allowed)</span>
                  <span>850 (excellent only)</span>
                </div>
              </div>

              <!-- Risk tolerance -->
              <div>
                <label class="input-label">Risk tolerance</label>
                <div class="grid grid-cols-4 gap-2">
                  <button *ngFor="let r of riskOptions"
                          type="button"
                          class="p-2.5 rounded-xl border text-center text-sm transition-all duration-200"
                          [ngClass]="prefs().risk_tolerance === r.value
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300 font-semibold'
                            : 'border-gray-200 dark:border-white/10 text-on-surface-muted hover:border-brand-300'"
                          (click)="setPref('risk_tolerance', r.value)">
                    <div>{{ r.icon }}</div>
                    <div class="text-xs mt-0.5">{{ r.label }}</div>
                  </button>
                </div>
              </div>

              <!-- Max duration -->
              <div>
                <label class="input-label">Maximum loan duration (days)</label>
                <input type="number" class="input-field"
                       [value]="prefs().max_duration_days"
                       (input)="setPref('max_duration_days', +$any($event.target).value)"
                       min="7" max="365" step="7" />
              </div>
            </div>

            <!-- Save button -->
            <div class="flex gap-3 pt-2 border-t border-gray-100 dark:border-white/10">
              <button class="btn-primary" (click)="savePrefs()" [disabled]="savingPrefs()">
                <app-spinner *ngIf="savingPrefs()" mode="inline" size="sm"></app-spinner>
                {{ savingPrefs() ? 'Saving…' : '💾 Save preferences' }}
              </button>
              <p *ngIf="prefs().updated_at" class="text-xs text-on-surface-muted self-center">
                Last saved {{ prefs().updated_at | date:'short' }}
              </p>
            </div>
          </div>
        </div>
      </div>

    </div>
  `,
})
export class LenderDashboardComponent implements OnInit {
  me           = signal<User | null>(null);
  marketplace  = signal<Loan[]>([]);
  investments  = signal<Transaction[]>([]);
  prefs        = signal<AutoInvestPrefs>({
    enabled: false,
    max_per_loan: 1000,
    min_credit_score: 500,
    risk_tolerance: 'MEDIUM',
    max_duration_days: 90,
  });

  marketLoading   = signal(true);
  portfolioLoading = signal(true);
  prefsLoading    = signal(true);
  submitting      = signal(false);
  savingPrefs     = signal(false);

  activeTab: DashTab = 'marketplace';
  riskFilter = 'ALL';
  fundAmounts: Record<string, number> = {};

  readonly tabs = [
    { id: 'marketplace' as DashTab, label: 'Marketplace', icon: '🛒' },
    { id: 'portfolio'   as DashTab, label: 'Portfolio',   icon: '📈' },
    { id: 'auto-invest' as DashTab, label: 'Auto-invest', icon: '🤖' },
  ];

  readonly riskFilters = ['ALL', 'LOW', 'MEDIUM', 'HIGH'];

  readonly riskOptions = [
    { value: 'LOW',    label: 'Low',    icon: '🟢' },
    { value: 'MEDIUM', label: 'Med',    icon: '🟡' },
    { value: 'HIGH',   label: 'High',   icon: '🔴' },
    { value: 'ALL',    label: 'Any',    icon: '⚪' },
  ];

  totalInvested = computed(() =>
    this.investments().reduce((s, t) => s + t.amount, 0)
  );

  totalExpectedReturn = computed(() =>
    this.investments().reduce((s, t) => s + (t.expected_return ?? t.amount * 1.1), 0) - this.totalInvested()
  );

  activeInvestments = computed(() =>
    this.investments().filter(t => t.type === 'FUNDING')
  );

  completedInvestments = computed(() =>
    this.investments().filter(t => (t as any).loan_status === 'REPAID')
  );

  portfolioROI = computed(() => {
    const inv = this.totalInvested();
    if (!inv) return 0;
    return (this.totalExpectedReturn() / inv) * 100;
  });

  filteredMarketplace = computed(() => {
    if (this.riskFilter === 'ALL') return this.marketplace();
    return this.marketplace().filter(l => l.risk_category === this.riskFilter);
  });

  monthlyReturns = computed(() => {
    // Group investments by month for the bar chart
    const map = new Map<string, number>();
    for (const tx of this.investments()) {
      const d = new Date(tx.created_at);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      const label = d.toLocaleString('default', { month: 'short', year: '2-digit' });
      map.set(key, (map.get(key) ?? 0) + tx.amount);
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([key, amount]) => ({
        label: new Date(key + '-01').toLocaleString('default', { month: 'short', year: '2-digit' }),
        amount,
      }));
  });

  barHeight(amount: number): number {
    const maxAmt = Math.max(...this.monthlyReturns().map(m => m.amount), 1);
    return Math.max(4, (amount / maxAmt) * 96);
  }

  constructor(private api: ApiService, private toast: ToastService) {}

  ngOnInit() {
    this.refresh();
    this.api.getAutoInvest().subscribe({
      next:  (p) => { this.prefs.set(p); this.prefsLoading.set(false); },
      error: ()  => { this.prefsLoading.set(false); },
    });
  }

  refresh() {
    this.marketLoading.set(true);
    this.portfolioLoading.set(true);

    this.api.me().subscribe({ next: (u) => this.me.set(u), error: () => {} });

    this.api.listLoans().subscribe({
      next:  (ls) => { this.marketplace.set(ls); this.marketLoading.set(false); },
      error: ()   => { this.marketLoading.set(false); },
    });

    this.api.myTransactions().subscribe({
      next:  (txs) => { this.investments.set(txs.filter(t => t.type === 'FUNDING')); this.portfolioLoading.set(false); },
      error: ()    => { this.portfolioLoading.set(false); },
    });
  }

  fund(loan: Loan) {
    const amount = this.fundAmounts[loan.id];
    if (!amount || amount <= 0) {
      this.toast.warning('Invalid amount', 'Enter a positive amount to fund.');
      return;
    }
    const remaining = loan.amount - loan.amount_funded;
    if (amount > remaining + 1e-6) {
      this.toast.warning('Amount too large', `Maximum fundable is ₹${remaining.toFixed(2)}`);
      return;
    }

    this.submitting.set(true);
    this.api.fundLoan(loan.id, amount).subscribe({
      next: (res) => {
        this.submitting.set(false);
        delete this.fundAmounts[loan.id];
        const newStatus = res.loan.status;
        this.toast.success(
          'Funding recorded!',
          `₹${amount.toLocaleString()} committed · Loan is now ${newStatus}`
        );
        this.refresh();
      },
      error: (err) => {
        this.submitting.set(false);
        this.toast.error('Funding failed', err?.error?.detail ?? 'Something went wrong');
      },
    });
  }

  savePrefs() {
    this.savingPrefs.set(true);
    this.api.updateAutoInvest(this.prefs()).subscribe({
      next: (saved) => {
        this.savingPrefs.set(false);
        this.prefs.set(saved);
        this.toast.success('Preferences saved', 'Auto-invest settings updated.');
      },
      error: (err) => {
        this.savingPrefs.set(false);
        this.toast.error('Save failed', err?.error?.detail ?? 'Could not save preferences');
      },
    });
  }

  /** Helper called from template to patch a single pref field (avoids arrow fns in templates). */
  toggleAutoInvest() {
    this.prefs.update(p => ({ ...p, enabled: !p.enabled }));
  }

  setPref(key: keyof AutoInvestPrefs, value: unknown) {
    this.prefs.update(p => ({ ...p, [key]: value }));
  }

  exportCSV() {
    this.api.exportTransactions('csv').subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `finlend-transactions-${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        this.toast.success('Export ready', 'Your transaction history CSV has been downloaded.');
      },
      error: () => this.toast.error('Export failed', 'Could not generate CSV export'),
    });
  }
}
