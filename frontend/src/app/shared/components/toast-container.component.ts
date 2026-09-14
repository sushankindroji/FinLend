import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToastService } from '../../core/services/toast.service';

@Component({
  selector: 'app-toast-container',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toast-container" aria-live="polite" aria-atomic="false">
      <div
        *ngFor="let t of toast.toasts(); trackBy: trackId"
        class="pointer-events-auto flex items-start gap-3 px-4 py-3.5 rounded-xl2
               shadow-glass-md min-w-[280px] max-w-sm border
               transition-all duration-300"
        [class]="cardClass(t.type)"
        [class.animate-toast-in]="!t.leaving"
        [class.animate-toast-out]="t.leaving"
        role="alert"
      >
        <!-- Icon -->
        <span class="text-lg flex-shrink-0 mt-0.5">{{ icon(t.type) }}</span>
        <!-- Body -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold leading-snug">{{ t.title }}</p>
          <p *ngIf="t.message" class="text-xs mt-0.5 opacity-80">{{ t.message }}</p>
        </div>
        <!-- Dismiss -->
        <button
          class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-lg
                 opacity-50 hover:opacity-100 transition-opacity text-xs font-bold"
          (click)="toast.dismiss(t.id)"
          aria-label="Dismiss"
        >✕</button>
      </div>
    </div>
  `,
})
export class ToastContainerComponent {
  constructor(readonly toast: ToastService) {}

  trackId(_: number, t: any) { return t.id; }

  icon(type: string): string {
    return { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' }[type] ?? '🔔';
  }

  cardClass(type: string): string {
    const map: Record<string, string> = {
      success: 'bg-success-50 dark:bg-success-500/15 border-success-500/30 text-success-800 dark:text-success-200',
      error:   'bg-danger-50  dark:bg-danger-500/15  border-danger-500/30  text-danger-800  dark:text-danger-200',
      warning: 'bg-warning-50 dark:bg-warning-500/15 border-warning-500/30 text-warning-800 dark:text-warning-200',
      info:    'bg-info-50    dark:bg-info-500/15    border-info-500/30    text-info-800    dark:text-info-200',
    };
    return map[type] ?? map['info'];
  }
}
