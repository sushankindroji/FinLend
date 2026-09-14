import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-spinner',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- Inline spinner -->
    <span *ngIf="mode==='inline'"
          class="inline-block rounded-full border-2 border-current border-t-transparent animate-spin"
          [class]="sizeClass()"
          role="status" aria-label="Loading">
    </span>

    <!-- Full overlay spinner -->
    <div *ngIf="mode==='overlay'"
         class="fixed inset-0 z-100 flex items-center justify-center
                bg-black/30 dark:bg-black/50 backdrop-blur-sm animate-fade-in">
      <div class="glass-card p-8 flex flex-col items-center gap-4 animate-scale-in">
        <div class="w-10 h-10 rounded-full border-4 border-brand-200
                    border-t-brand-500 animate-spin-slow"></div>
        <p *ngIf="label" class="text-sm text-on-surface-muted font-medium">{{ label }}</p>
      </div>
    </div>

    <!-- Page-level centered spinner -->
    <div *ngIf="mode==='page'"
         class="flex flex-col items-center justify-center py-24 animate-fade-in gap-4">
      <div class="w-10 h-10 rounded-full border-4 border-brand-200
                  border-t-brand-500 animate-spin-slow"></div>
      <p *ngIf="label" class="text-sm text-on-surface-muted font-medium">{{ label }}</p>
    </div>
  `,
})
export class LoadingSpinnerComponent {
  @Input() mode: 'inline' | 'overlay' | 'page' = 'inline';
  @Input() size: 'xs' | 'sm' | 'md' | 'lg' = 'md';
  @Input() label = '';

  sizeClass(): string {
    return { xs: 'w-3 h-3', sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-7 h-7' }[this.size];
  }
}
