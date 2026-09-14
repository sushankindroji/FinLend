import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="min-h-dvh flex items-center justify-center px-4">
      <div class="glass-card max-w-sm w-full p-10 text-center animate-scale-in space-y-4">
        <div class="text-7xl animate-float">🌊</div>
        <h1 class="text-3xl font-bold text-on-surface">404</h1>
        <p class="font-semibold text-on-surface">Page not found</p>
        <p class="text-sm text-on-surface-muted">
          This page doesn't exist or you don't have access to it.
        </p>
        <a
          [routerLink]="auth.isLoggedIn() ? '/' + (auth.role() ?? '') : '/login'"
          class="btn-primary inline-flex mx-auto"
        >
          ← Go home
        </a>
      </div>
    </div>
  `,
})
export class NotFoundComponent {
  constructor(readonly auth: AuthService) {}
}
