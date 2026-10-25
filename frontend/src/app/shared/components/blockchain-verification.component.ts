import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { LoadingSpinnerComponent } from './loading-spinner.component';

interface BlockchainTransaction {
  type: string;
  tx_hash?: string;
  amount: number;
  timestamp: string;
  verified: boolean;
  chain_mode: string;
}

interface VerificationResult {
  loan_verified: boolean;
  transactions: BlockchainTransaction[];
  on_chain: boolean;
  chain_mode: string;
  message: string;
}

@Component({
  selector: 'app-blockchain-verification',
  standalone: true,
  imports: [CommonModule, LoadingSpinnerComponent],
  template: `
    <div class="space-y-4">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-lg">🔗</span>
          <h3 class="font-semibold text-sm">Blockchain Verification</h3>
        </div>
        <button
          class="btn-ghost text-xs"
          (click)="refresh()"
          [disabled]="loading()"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none"
               viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581
                     m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Refresh
        </button>
      </div>

      <!-- Loading state -->
      <app-spinner *ngIf="loading()" mode="page" label="Verifying on blockchain..."></app-spinner>

      <!-- Error state -->
      <div *ngIf="error() && !loading()" class="text-center py-6 space-y-3">
        <div class="text-4xl">⚠️</div>
        <p class="text-sm text-on-surface-muted">{{ error() }}</p>
        <button class="btn-secondary text-sm" (click)="loadVerification()">
          Try Again
        </button>
      </div>

      <!-- Verification result -->
      <div *ngIf="!loading() && !error() && verification()" class="space-y-3 animate-fade-in">
        <!-- Status card -->
        <div
          class="p-4 rounded-xl border"
          [ngClass]="{
            'border-success-500/30 bg-success-50 dark:bg-success-500/10': verification()!.loan_verified,
            'border-warning-500/30 bg-warning-50 dark:bg-warning-500/10': !verification()!.loan_verified
          }"
        >
          <div class="flex items-center gap-3 mb-2">
            <span class="text-2xl">
              {{ verification()!.loan_verified ? '✅' : '⚠️' }}
            </span>
            <div>
              <p class="font-semibold text-sm">
                {{ verification()!.loan_verified ? 'Verified on Blockchain' : 'Verification Pending' }}
              </p>
              <p class="text-xs text-on-surface-muted">{{ verification()!.message }}</p>
            </div>
          </div>

          <!-- Chain mode badge -->
          <div class="flex items-center gap-2 mt-3">
            <span class="text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-white/10 font-mono">
              {{ verification()!.chain_mode }}
            </span>
            <span
              *ngIf="verification()!.on_chain"
              class="text-xs px-2 py-1 rounded-full bg-brand-100 dark:bg-brand-500/20 text-brand-700 dark:text-brand-300"
            >
              🌐 On-Chain
            </span>
            <span
              *ngIf="!verification()!.on_chain"
              class="text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-white/10 text-on-surface-muted"
            >
              📋 Simulated
            </span>
          </div>
        </div>

        <!-- Transactions list -->
        <div *ngIf="verification()!.transactions && verification()!.transactions.length > 0">
          <h4 class="font-semibold text-xs text-on-surface-muted mb-2 uppercase tracking-wide">
            Transaction History
          </h4>
          <div class="space-y-2">
            <div
              *ngFor="let tx of verification()!.transactions"
              class="p-3 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10"
            >
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="text-sm">
                    {{ tx.type === 'FUNDING' ? '💰' : '💸' }}
                  </span>
                  <span class="text-sm font-medium">{{ formatType(tx.type) }}</span>
                </div>
                <span class="font-semibold text-sm">₹{{ tx.amount | number:'1.2-2' }}</span>
              </div>

              <!-- Transaction hash -->
              <div *ngIf="tx.tx_hash" class="mt-2 pt-2 border-t border-gray-200 dark:border-white/10">
                <div class="flex items-center gap-2">
                  <span class="text-2xs text-on-surface-muted">TX Hash:</span>
                  <code class="text-2xs font-mono bg-white dark:bg-black/20 px-2 py-1 rounded flex-1 truncate">
                    {{ tx.tx_hash }}
                  </code>
                  <button
                    class="text-2xs text-brand-600 dark:text-brand-400 hover:underline"
                    (click)="copyHash(tx.tx_hash!)"
                  >
                    Copy
                  </button>
                </div>
              </div>

              <!-- Metadata -->
              <div class="flex items-center gap-3 mt-2 text-2xs text-on-surface-muted">
                <span>{{ tx.timestamp | date:'short' }}</span>
                <span>•</span>
                <span
                  class="px-2 py-0.5 rounded-full"
                  [ngClass]="{
                    'bg-success-100 dark:bg-success-500/20 text-success-700 dark:text-success-300': tx.verified,
                    'bg-warning-100 dark:bg-warning-500/20 text-warning-700 dark:text-warning-300': !tx.verified
                  }"
                >
                  {{ tx.verified ? '✓ Verified' : '⏳ Pending' }}
                </span>
                <span>•</span>
                <span class="font-mono">{{ tx.chain_mode }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- No transactions -->
        <div
          *ngIf="!verification()!.transactions || verification()!.transactions.length === 0"
          class="text-center py-6 text-sm text-on-surface-muted"
        >
          <div class="text-4xl mb-2">📋</div>
          <p>No blockchain transactions yet</p>
        </div>

        <!-- Info notice -->
        <div class="text-xs text-on-surface-muted bg-gray-50 dark:bg-white/5 rounded-lg p-3 border border-gray-200 dark:border-white/10">
          <strong>Note:</strong> Blockchain verification provides immutable proof of all funding and repayment transactions.
          {{ verification()!.chain_mode === 'LOCAL_SIMULATION' ? 
             'Currently running in simulation mode. In production, all transactions would be recorded on a real blockchain network.' :
             'All transactions are recorded on the blockchain and can be independently verified.' }}
        </div>
      </div>
    </div>
  `,
})
export class BlockchainVerificationComponent implements OnInit {
  @Input() loanId!: string;

  loading = signal(false);
  error = signal<string | null>(null);
  verification = signal<VerificationResult | null>(null);

  constructor(
    private api: ApiService,
    private toast: ToastService
  ) {}

  ngOnInit() {
    if (this.loanId) {
      this.loadVerification();
    }
  }

  refresh() {
    this.loadVerification();
  }

  loadVerification() {
    if (!this.loanId) {
      this.error.set('No loan ID provided');
      return;
    }

    this.loading.set(true);
    this.error.set(null);

    this.api.verifyLoan(this.loanId).subscribe({
      next: (res) => {
        this.loading.set(false);
        this.verification.set(res);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err?.error?.detail || 'Failed to verify blockchain transactions');
      },
    });
  }

  formatType(type: string): string {
    return type.charAt(0) + type.slice(1).toLowerCase();
  }

  copyHash(hash: string) {
    navigator.clipboard.writeText(hash).then(() => {
      this.toast.success('Copied!', 'Transaction hash copied to clipboard');
    }).catch(() => {
      this.toast.error('Copy failed', 'Unable to copy to clipboard');
    });
  }
}
