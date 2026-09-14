import { Routes } from '@angular/router';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  // Root redirect
  { path: '', redirectTo: 'login', pathMatch: 'full' },

  // ── Auth ──────────────────────────────────────────────────────────────
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login.component').then((m) => m.LoginComponent),
    title: 'Sign in · FinLend',
  },
  {
    path: 'register',
    loadComponent: () =>
      import('./features/auth/register.component').then((m) => m.RegisterComponent),
    title: 'Create account · FinLend',
  },

  // ── Borrower ──────────────────────────────────────────────────────────
  {
    path: 'borrower',
    canActivate: [roleGuard(['borrower'])],
    loadComponent: () =>
      import('./features/borrower/borrower-dashboard.component')
        .then((m) => m.BorrowerDashboardComponent),
    title: 'Dashboard · FinLend',
  },
  {
    path: 'borrower/loans',
    canActivate: [roleGuard(['borrower'])],
    loadComponent: () =>
      import('./features/borrower/borrower-loans.component')
        .then((m) => m.BorrowerLoansComponent),
    title: 'My loans · FinLend',
  },
  {
    path: 'borrower/notifications',
    canActivate: [roleGuard(['borrower'])],
    loadComponent: () =>
      import('./features/shared-pages/notifications.component')
        .then((m) => m.NotificationsComponent),
    title: 'Notifications · FinLend',
  },

  // ── Lender ────────────────────────────────────────────────────────────
  {
    path: 'lender',
    canActivate: [roleGuard(['lender'])],
    loadComponent: () =>
      import('./features/lender/lender-dashboard.component')
        .then((m) => m.LenderDashboardComponent),
    title: 'Dashboard · FinLend',
  },
  {
    path: 'lender/marketplace',
    canActivate: [roleGuard(['lender'])],
    loadComponent: () =>
      import('./features/lender/lender-dashboard.component')
        .then((m) => m.LenderDashboardComponent),
    title: 'Marketplace · FinLend',
  },
  {
    path: 'lender/portfolio',
    canActivate: [roleGuard(['lender'])],
    loadComponent: () =>
      import('./features/lender/lender-dashboard.component')
        .then((m) => m.LenderDashboardComponent),
    title: 'Portfolio · FinLend',
  },
  {
    path: 'lender/notifications',
    canActivate: [roleGuard(['lender'])],
    loadComponent: () =>
      import('./features/shared-pages/notifications.component')
        .then((m) => m.NotificationsComponent),
    title: 'Notifications · FinLend',
  },

  // ── Admin ─────────────────────────────────────────────────────────────
  {
    path: 'admin',
    canActivate: [roleGuard(['admin'])],
    loadComponent: () =>
      import('./features/admin/admin-dashboard.component')
        .then((m) => m.AdminDashboardComponent),
    title: 'Admin overview · FinLend',
  },
  {
    path: 'admin/users',
    canActivate: [roleGuard(['admin'])],
    loadComponent: () =>
      import('./features/admin/admin-dashboard.component')
        .then((m) => m.AdminDashboardComponent),
    title: 'Users · FinLend Admin',
  },
  {
    path: 'admin/loans',
    canActivate: [roleGuard(['admin'])],
    loadComponent: () =>
      import('./features/admin/admin-dashboard.component')
        .then((m) => m.AdminDashboardComponent),
    title: 'Loans · FinLend Admin',
  },
  {
    path: 'admin/flags',
    canActivate: [roleGuard(['admin'])],
    loadComponent: () =>
      import('./features/admin/admin-dashboard.component')
        .then((m) => m.AdminDashboardComponent),
    title: 'Risk flags · FinLend Admin',
  },
  {
    path: 'admin/notifications',
    canActivate: [roleGuard(['admin'])],
    loadComponent: () =>
      import('./features/shared-pages/notifications.component')
        .then((m) => m.NotificationsComponent),
    title: 'Notifications · FinLend Admin',
  },

  // ── Fallback (404) ────────────────────────────────────────────────────
  {
    path: '**',
    loadComponent: () =>
      import('./features/shared-pages/not-found.component')
        .then((m) => m.NotFoundComponent),
    title: 'Not found · FinLend',
  },
];
