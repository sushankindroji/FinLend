import { Component, Input, Output, EventEmitter, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { LoadingSpinnerComponent } from './loading-spinner.component';

interface EMIResult {
  emi: number;
  total_payment: number;
  total_interest: number;
  schedule: Array<{
    payment_number: number;
    principal: number;
    interest: number;
    total: number;
    balance: number;
  }>;
}

@Component({
  selector: 'app-emi-calculator',
  standalone: true,
  imports: [CommonModule, FormsModule, LoadingSpinnerComponent],
  template: `
    <div class="glass-panel p-4 space-y-4">
      <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">🧮</span>
        <h3 class="font-semibold text-on-surface">EMI Calculator</h3>
      </div>

      <!-- Input form -->
      <div class="space-y-3">
        <div>
          <label class="input-label">Principal Amount (₹)</label>
          <input
            type="number"
            class="input-field"
            [(ngModel)]="principal"
            [disabled]="lockPrincipal"
            min="100"
            step="100"
            (ngModelChange)="onInputChange()"
          />
        </div>

        <div>
          <label class="input-label">Interest Rate (% per year)</label>
          <input
            type="number"
            class="input-field"
            [(ngModel)]="annualRate"
            min="0"
            max="100"
            step="0.1"
            (ngModelChange)="onInputChange()"
          />
        </div>

        <div>
          <label class="input-label">Duration (days)</label>
          <input
            type="number"
            class="input-field"
            [(ngModel)]="tenureDays"
            [disabled]="lockDuration"
            min="1"
            step="1"
            (ngModelChange)="onInputChange()"
          />
          <div class="flex gap-2 mt-2 flex-wrap">
            <button
              *ngFor="let d of quickDurations"
              type="button"
              class="px-2 py-1 rounded-lg border text-xs transition-all"
              [ngClass]="tenureDays === d.days
                ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
                : 'border-gray-200 dark:border-white/10 text-on-surface-muted hover:border-brand-300'"
              (click)="tenureDays = d.days; onInputChange()"
            >
              {{ d.label }}
            </button>
          </div>
        </div>

        <div>
          <label class="input-label">Repayment Method</label>
          <select class="input-field" [(ngModel)]="repaymentMethod" (ngModelChange)="onInputChange()">
            <option value="reducing_balance">Reducing Balance (Standard EMI)</option>
            <option value="flat_rate">Flat Rate</option>
            <option value="bullet_payment">Bullet Payment</option>
          </select>
        </div>

        <button
          class="btn-primary w-full"
          (click)="calculate()"
          [disabled]="calculating() || !isValid()"
        >
          <app-spinner *ngIf="calculating()" mode="inline" size="sm"></app-spinner>
          {{ calculating() ? 'Calculating...' : 'Calculate EMI' }}
        </button>
      </div>

      <!-- Results -->
      <div *ngIf="result()" class="space-y-3 animate-fade-in">
        <div class="bg-brand-50 dark:bg-brand-500/10 rounded-xl p-4 space-y-2">
          <div class="flex justify-between items-baseline">
            <span class="text-sm text-on-surface-muted">Monthly EMI</span>
            <span class="text-2xl font-bold text-brand-600 dark:text-brand-400">
              ₹{{ result()!.emi | number:'1.2-2' }}
            </span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-on-surface-muted">Total Interest</span>
            <span class="font-semibold">₹{{ result()!.total_interest | number:'1.2-2' }}</span>
          </div>
          <div class="flex justify-between text-sm border-t border-brand-200 dark:border-brand-500/20 pt-2">
            <span class="font-medium">Total Payment</span>
            <span class="font-bold">₹{{ result()!.total_payment | number:'1.2-2' }}</span>
          </div>
        </div>

        <!-- Schedule toggle -->
        <button
          class="text-xs text-brand-600 dark:text-brand-400 font-medium hover:underline"
          (click)="showSchedule.set(!showSchedule())"
        >
          {{ showSchedule() ? '▼ Hide' : '▶ Show' }} Payment Schedule
        </button>

        <!-- Payment schedule -->
        <div *ngIf="showSchedule() && result()!.schedule.length > 0" class="space-y-1 max-h-60 overflow-y-auto scrollbar-thin animate-fade-in">
          <div
            *ngFor="let entry of result()!.schedule"
            class="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-white/5 text-xs"
          >
            <div class="flex items-center gap-3 flex-1">
              <span class="font-mono text-on-surface-muted">{{ entry.payment_number }}</span>
              <div class="flex flex-col">
                <span class="font-medium">₹{{ entry.total | number:'1.2-2' }}</span>
                <span class="text-2xs text-on-surface-muted">
                  P: ₹{{ entry.principal | number:'1.0-0' }} • I: ₹{{ entry.interest | number:'1.0-0' }}
                </span>
              </div>
            </div>
            <span class="text-on-surface-muted">Bal: ₹{{ entry.balance | number:'1.0-0' }}</span>
          </div>
        </div>

        <!-- Explanation button -->
        <button
          class="btn-secondary w-full text-xs"
          (click)="explainCalculation()"
          [disabled]="explaining()"
        >
          <app-spinner *ngIf="explaining()" mode="inline" size="sm"></app-spinner>
          {{ explaining() ? 'Loading...' : '📖 Explain this calculation' }}
        </button>

        <!-- Explanation -->
        <div *ngIf="explanation()" class="text-xs text-on-surface-muted bg-gray-50 dark:bg-white/5 rounded-lg p-3 animate-fade-in">
          {{ explanation() }}
        </div>
      </div>

      <!-- Error message -->
      <div *ngIf="error()" class="text-xs text-danger-600 dark:text-danger-400 bg-danger-50 dark:bg-danger-500/10 rounded-lg p-3">
        {{ error() }}
      </div>
    </div>
  `,
  styles: [`
    .scrollbar-thin::-webkit-scrollbar {
      width: 4px;
    }
    .scrollbar-thin::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 4px;
    }
  `]
})
export class EMICalculatorComponent {
  @Input() lockPrincipal = false;
  @Input() lockDuration = false;
  @Output() calculated = new EventEmitter<EMIResult>();

  principal = 10000;
  annualRate = 10;
  tenureDays = 30;
  repaymentMethod = 'reducing_balance';

  calculating = signal(false);
  explaining = signal(false);
  result = signal<EMIResult | null>(null);
  explanation = signal<string | null>(null);
  error = signal<string | null>(null);
  showSchedule = signal(false);

  readonly quickDurations = [
    { days: 30, label: '1M' },
    { days: 60, label: '2M' },
    { days: 90, label: '3M' },
    { days: 180, label: '6M' },
    { days: 365, label: '1Y' },
  ];

  constructor(
    private api: ApiService,
    private toast: ToastService
  ) {}

  isValid(): boolean {
    return this.principal > 0 && this.annualRate >= 0 && this.tenureDays > 0;
  }

  onInputChange() {
    // Clear results when inputs change
    this.result.set(null);
    this.explanation.set(null);
    this.error.set(null);
  }

  calculate() {
    if (!this.isValid()) {
      this.error.set('Please enter valid values for all fields');
      return;
    }

    this.calculating.set(true);
    this.error.set(null);

    this.api.calculateEMI({
      principal: this.principal,
      annual_rate: this.annualRate,
      tenure_days: this.tenureDays,
      repayment_method: this.repaymentMethod,
    }).subscribe({
      next: (res) => {
        this.calculating.set(false);
        this.result.set(res);
        this.calculated.emit(res);
      },
      error: (err) => {
        this.calculating.set(false);
        this.error.set(err?.error?.detail || 'Calculation failed. Please try again.');
        this.toast.error('Calculation failed', err?.error?.detail || 'Unknown error');
      },
    });
  }

  explainCalculation() {
    if (!this.result()) return;

    this.explaining.set(true);

    this.api.explainEMI({
      principal: this.principal,
      annual_rate: this.annualRate,
      tenure_days: this.tenureDays,
      repayment_method: this.repaymentMethod,
    }, 'en').subscribe({
      next: (res) => {
        this.explaining.set(false);
        this.explanation.set(res.explanation || 'No explanation available');
      },
      error: (err) => {
        this.explaining.set(false);
        this.toast.error('Explanation failed', err?.error?.detail || 'Unable to fetch explanation');
      },
    });
  }
}
