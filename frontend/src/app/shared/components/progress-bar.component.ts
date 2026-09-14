import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-progress-bar',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="w-full">
      <!-- Label row -->
      <div *ngIf="showLabel" class="flex justify-between items-center mb-1.5">
        <span class="text-xs font-medium text-on-surface-muted">{{ label }}</span>
        <span class="text-xs font-semibold text-on-surface">{{ pct | number:'1.0-0' }}%</span>
      </div>
      <!-- Track -->
      <div class="progress-track" [style.height.px]="height">
        <div
          class="progress-fill"
          [style.width.%]="clampedPct"
          [ngClass]="colorClass"
          [style.height.px]="height"
        ></div>
      </div>
      <!-- Sub-label row -->
      <div *ngIf="subLabel" class="flex justify-between mt-1">
        <span class="text-xs text-on-surface-muted">{{ subLabel }}</span>
        <span *ngIf="subLabelRight" class="text-xs text-on-surface-muted">{{ subLabelRight }}</span>
      </div>
    </div>
  `,
})
export class ProgressBarComponent {
  @Input() pct = 0;
  @Input() color: 'brand' | 'success' | 'warning' | 'danger' | 'info' = 'brand';
  @Input() height = 6;
  @Input() showLabel = false;
  @Input() label = '';
  @Input() subLabel = '';
  @Input() subLabelRight = '';

  get clampedPct(): number {
    return Math.max(0, Math.min(100, this.pct));
  }

  get colorClass(): string {
    const map: Record<string, string> = {
      brand:   'bg-brand-500',
      success: 'bg-success-500',
      warning: 'bg-warning-500',
      danger:  'bg-danger-500',
      info:    'bg-info-500',
    };
    return map[this.color] ?? 'bg-brand-500';
  }
}
