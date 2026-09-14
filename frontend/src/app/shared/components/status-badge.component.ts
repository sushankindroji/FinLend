import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';

/** Maps loan status strings → CSS class. */
const STATUS_CLASSES: Record<string, string> = {
  REQUESTED:        'badge-gray',
  CREDIT_CHECK:     'badge-info',
  APPROVED:         'badge-success',
  REJECTED:         'badge-danger',
  OPEN_FOR_FUNDING: 'badge-brand',
  PARTIALLY_FUNDED: 'badge-warning',
  FUNDED:           'badge-success',
  ACTIVE:           'badge-brand',
  LATE:             'badge-warning',
  REPAID:           'badge-success',
  DEFAULTED:        'badge-danger',
};

/** Maps risk category → CSS class. */
const RISK_CLASSES: Record<string, string> = {
  LOW:    'badge-success',
  MEDIUM: 'badge-warning',
  HIGH:   'badge-danger',
};

/** Maps role → CSS class. */
const ROLE_CLASSES: Record<string, string> = {
  borrower: 'badge-brand',
  lender:   'badge-success',
  admin:    'badge-gray',
};

/** Maps blockchain mode → CSS class. */
const CHAIN_CLASSES: Record<string, string> = {
  ON_CHAIN:         'badge-success',
  LOCAL_SIMULATION: 'badge-gray',
  DISABLED:         'badge-danger',
};

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="badge" [ngClass]="cssClass" [title]="value">
      <span *ngIf="dot" class="w-1.5 h-1.5 rounded-full bg-current opacity-80"></span>
      {{ label || value }}
    </span>
  `,
})
export class StatusBadgeComponent {
  @Input() value = '';
  @Input() type: 'status' | 'risk' | 'role' | 'chain' = 'status';
  @Input() label = '';   // override display text
  @Input() dot = false;  // show dot indicator

  get cssClass(): string {
    const map = {
      status: STATUS_CLASSES,
      risk:   RISK_CLASSES,
      role:   ROLE_CLASSES,
      chain:  CHAIN_CLASSES,
    }[this.type];
    return map?.[this.value] ?? 'badge-gray';
  }
}
