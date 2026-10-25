import { Component, Input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { LoadingSpinnerComponent } from './loading-spinner.component';
import { ModalComponent } from './modal.component';

interface CreditExplanation {
  credit_score: number;
  risk_category: string;
  factors: Array<{
    feature: string;
    importance: number;
    current_value: any;
    impact: string;
  }>;
  recommendations: string[];
  explanation: string;
}

@Component({
  selector: 'app-credit-explanation',
  standalone: true,
  imports: [CommonModule, LoadingSpinnerComponent, ModalComponent],
  template: `
    <button
      class="btn-secondary text-xs px-3 py-1.5"
      (click)="openModal()"
    >
      💡 Explain My Score
    </button>

    <app-modal
      [open]="modalOpen()"
      title="Credit Score Explanation"
      [subtitle]="explanation() ? 'Score: ' + explanation()!.credit_score + ' · ' + explanation()!.risk_category : ''"
      (close)="closeModal()"
    >
      <div class="space-y-4">
        <app-spinner *ngIf="loading()" mode="page" label="Analyzing your credit score..."></app-spinner>

        <!-- Error state -->
        <div *ngIf="error()" class="text-center py-6 space-y-3">
          <div class="text-4xl">⚠️</div>
          <p class="text-sm text-on-surface-muted">{{ error() }}</p>
          <button class="btn-primary text-sm" (click)="loadExplanation()">
            Try Again
          </button>
        </div>

        <!-- Explanation content -->
        <div *ngIf="!loading() && !error() && explanation()" class="space-y-4 animate-fade-in">
          <!-- Summary -->
          <div class="bg-brand-50 dark:bg-brand-500/10 rounded-xl p-4">
            <p class="text-sm text-on-surface-muted mb-2">Overall Assessment</p>
            <p class="text-sm leading-relaxed">{{ explanation()!.explanation }}</p>
          </div>

          <!-- Feature importance -->
          <div *ngIf="explanation()!.factors && explanation()!.factors.length > 0">
            <h4 class="font-semibold text-sm mb-3">Key Factors Affecting Your Score</h4>
            <div class="space-y-2">
              <div
                *ngFor="let factor of explanation()!.factors"
                class="flex items-center gap-3 p-3 rounded-lg bg-gray-50 dark:bg-white/5"
              >
                <div class="flex-1">
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-sm font-medium">{{ formatFeatureName(factor.feature) }}</span>
                    <span class="text-xs font-mono text-on-surface-muted">{{ factor.current_value }}</span>
                  </div>
                  <!-- Importance bar -->
                  <div class="w-full bg-gray-200 dark:bg-white/10 rounded-full h-1.5">
                    <div
                      class="h-1.5 rounded-full transition-all"
                      [style.width.%]="factor.importance * 100"
                      [ngClass]="{
                        'bg-success-500': factor.impact === 'positive',
                        'bg-danger-500': factor.impact === 'negative',
                        'bg-gray-400': factor.impact === 'neutral'
                      }"
                    ></div>
                  </div>
                  <div class="flex items-center gap-2 mt-1">
                    <span
                      class="text-2xs px-2 py-0.5 rounded-full"
                      [ngClass]="{
                        'bg-success-100 dark:bg-success-500/20 text-success-700 dark:text-success-300': factor.impact === 'positive',
                        'bg-danger-100 dark:bg-danger-500/20 text-danger-700 dark:text-danger-300': factor.impact === 'negative',
                        'bg-gray-100 dark:bg-white/10 text-on-surface-muted': factor.impact === 'neutral'
                      }"
                    >
                      {{ factor.impact === 'positive' ? '👍 Positive' : factor.impact === 'negative' ? '👎 Negative' : '➖ Neutral' }}
                    </span>
                    <span class="text-2xs text-on-surface-muted">
                      {{ (factor.importance * 100).toFixed(1) }}% importance
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Recommendations -->
          <div *ngIf="explanation()!.recommendations && explanation()!.recommendations.length > 0">
            <h4 class="font-semibold text-sm mb-3">📈 How to Improve Your Score</h4>
            <ul class="space-y-2">
              <li
                *ngFor="let rec of explanation()!.recommendations"
                class="flex items-start gap-2 text-sm"
              >
                <span class="text-brand-500 mt-0.5">•</span>
                <span>{{ rec }}</span>
              </li>
            </ul>
          </div>

          <!-- Demo mode notice -->
          <div *ngIf="isDemoMode()" class="text-xs text-on-surface-muted bg-gray-50 dark:bg-white/5 rounded-lg p-3 border border-gray-200 dark:border-white/10">
            <strong>Demo Mode:</strong> This explanation is generated using rule-based logic. In production with trained SHAP models, you would see actual feature contributions from your data.
          </div>
        </div>
      </div>
    </app-modal>
  `,
})
export class CreditExplanationComponent {
  @Input() loanId?: string; // If provided, explains loan decision instead of credit score

  modalOpen = signal(false);
  loading = signal(false);
  error = signal<string | null>(null);
  explanation = signal<CreditExplanation | null>(null);

  constructor(
    private api: ApiService,
    private toast: ToastService
  ) {}

  openModal() {
    this.modalOpen.set(true);
    this.loadExplanation();
  }

  closeModal() {
    this.modalOpen.set(false);
  }

  loadExplanation() {
    this.loading.set(true);
    this.error.set(null);

    const request$ = this.loanId
      ? this.api.explainLoanDecision(this.loanId, 'en')
      : this.api.explainCreditScore('en');

    request$.subscribe({
      next: (res) => {
        this.loading.set(false);
        this.explanation.set(res);
      },
      error: (err) => {
        this.loading.set(false);
        const errorMsg = err?.error?.detail || 'Unable to load explanation';
        
        // Check for specific SHAP model errors
        if (errorMsg.includes('SHAP') || errorMsg.includes('model') || errorMsg.includes('explainer')) {
          this.error.set('AI explainability model not available. Running in demo mode with rule-based explanations.');
        } else {
          this.error.set(errorMsg);
        }
      },
    });
  }

  formatFeatureName(feature: string): string {
    return feature
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  isDemoMode(): boolean {
    // Check if explanation contains indicators of demo/rule-based mode
    const exp = this.explanation();
    return exp?.explanation?.includes('rule-based') || 
           exp?.explanation?.includes('demo') ||
           exp?.explanation?.includes('simulation') || false;
  }
}
