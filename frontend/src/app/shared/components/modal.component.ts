import {
  Component, Input, Output, EventEmitter,
  HostListener, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-modal',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      *ngIf="open"
      class="modal-backdrop animate-fade-in"
      (click)="onBackdropClick($event)"
      role="dialog"
      [attr.aria-label]="title"
      aria-modal="true"
    >
      <div class="modal-box" (click)="$event.stopPropagation()">
        <!-- Header -->
        <div class="flex items-start justify-between mb-5">
          <div>
            <h2 class="text-lg font-semibold text-on-surface">{{ title }}</h2>
            <p *ngIf="subtitle" class="text-sm text-on-surface-muted mt-0.5">{{ subtitle }}</p>
          </div>
          <button
            class="btn-icon ml-3 flex-shrink-0"
            (click)="close.emit()"
            aria-label="Close modal"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none"
                 viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <!-- Body (projected) -->
        <ng-content></ng-content>
      </div>
    </div>
  `,
})
export class ModalComponent {
  @Input() open = false;
  @Input() title = '';
  @Input() subtitle = '';
  @Input() closeOnBackdrop = true;
  @Output() close = new EventEmitter<void>();

  onBackdropClick(e: MouseEvent) {
    if (this.closeOnBackdrop) this.close.emit();
  }

  @HostListener('document:keydown.escape')
  onEsc() {
    if (this.open) this.close.emit();
  }
}
