import {
  Component, OnInit, signal, computed, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { AuthService } from '../../core/services/auth.service';
import { NavbarComponent } from '../../shared/components/navbar.component';
import { LoadingSpinnerComponent } from '../../shared/components/loading-spinner.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import type { Notification, NotificationType } from '../../core/models';

const NOTIF_ICONS: Record<NotificationType, string> = {
  LOAN_APPROVED:       '✅',
  LOAN_REJECTED:       '❌',
  LOAN_FUNDED:         '💰',
  LOAN_ACTIVE:         '🔄',
  REPAYMENT_RECEIVED:  '💸',
  LOAN_REPAID:         '🏆',
  LOAN_LATE:           '⚠️',
  LOAN_DEFAULTED:      '🔴',
  CREDIT_UPDATED:      '📊',
  AUTO_INVEST:         '🤖',
  SYSTEM:              '🔔',
};

@Component({
  selector: 'app-notifications',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Default,
  imports: [CommonModule, NavbarComponent, LoadingSpinnerComponent, EmptyStateComponent],
  template: `
    <app-navbar></app-navbar>

    <div class="page-container-sm space-y-5 animate-fade-in-up">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-on-surface">Notifications</h1>
          <p class="text-sm text-on-surface-muted mt-0.5">
            {{ unreadCount() }} unread · {{ notifications().length }} total
          </p>
        </div>
        <div class="flex gap-2">
          <button class="btn-secondary text-sm"
                  *ngIf="unreadCount() > 0"
                  (click)="markAllRead()">
            ✓ Mark all read
          </button>
          <button class="btn-ghost text-sm" (click)="refresh()">Refresh</button>
        </div>
      </div>

      <!-- Filter tabs -->
      <div class="flex gap-1 bg-gray-100 dark:bg-white/10 p-1 rounded-xl self-start">
        <button *ngFor="let f of filters"
                class="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200"
                [ngClass]="activeFilter === f.id
                  ? 'bg-white dark:bg-white/15 shadow-soft text-on-surface'
                  : 'text-on-surface-muted hover:text-on-surface'"
                (click)="activeFilter = f.id">
          {{ f.label }}
          <span *ngIf="f.id === 'unread' && unreadCount() > 0"
                class="ml-1 badge badge-danger text-2xs">{{ unreadCount() }}</span>
        </button>
      </div>

      <app-spinner *ngIf="loading()" mode="page" label="Loading notifications…"></app-spinner>

      <app-empty-state *ngIf="!loading() && !filtered().length"
        icon="🔔"
        title="All caught up"
        subtitle="No notifications to show here.">
      </app-empty-state>

      <!-- Notification list -->
      <div *ngIf="!loading() && filtered().length" class="space-y-2">
        <div *ngFor="let n of filtered(); trackBy: trackId"
             class="glass-panel p-4 flex items-start gap-4 cursor-pointer
                    transition-all duration-200 hover:shadow-glass"
             [ngClass]="n.read ? 'opacity-70' : ''"
             (click)="markRead(n)">
          <!-- Icon -->
          <div class="flex-shrink-0 w-10 h-10 rounded-2xl flex items-center justify-center text-xl
                      transition-all duration-200"
               [ngClass]="n.read
                 ? 'bg-gray-100 dark:bg-white/10'
                 : 'bg-brand-50 dark:bg-brand-500/20 shadow-brand-glow'">
            {{ notifIcon(n.type) }}
          </div>
          <!-- Content -->
          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-2">
              <p class="text-sm font-semibold text-on-surface">{{ n.title }}</p>
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <span *ngIf="!n.read"
                      class="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0"></span>
                <span class="text-xs text-on-surface-muted whitespace-nowrap">
                  {{ n.created_at | date:'short' }}
                </span>
              </div>
            </div>
            <p class="text-sm text-on-surface-muted mt-0.5">{{ n.body }}</p>
            <a *ngIf="n.loan_id"
               [href]="'/' + auth.role() + '/loans/' + n.loan_id"
               class="text-xs text-brand-600 dark:text-brand-400 hover:underline mt-1 block"
               (click)="$event.stopPropagation()">
              View loan →
            </a>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class NotificationsComponent implements OnInit {
  notifications = signal<Notification[]>([]);
  loading       = signal(true);
  activeFilter  = 'all';

  readonly filters = [
    { id: 'all',    label: 'All' },
    { id: 'unread', label: 'Unread' },
  ];

  unreadCount = computed(() => this.notifications().filter(n => !n.read).length);

  filtered = computed(() =>
    this.activeFilter === 'unread'
      ? this.notifications().filter(n => !n.read)
      : this.notifications()
  );

  constructor(
    private api: ApiService,
    private toast: ToastService,
    readonly auth: AuthService,
  ) {}

  ngOnInit() { this.refresh(); }

  refresh() {
    this.loading.set(true);
    this.api.getNotifications().subscribe({
      next:  (ns) => { this.notifications.set(ns); this.loading.set(false); },
      error: ()   => { this.loading.set(false); },
    });
  }

  markRead(n: Notification) {
    if (n.read) return;
    this.api.markNotificationRead(n.id).subscribe({
      next: () =>
        this.notifications.update(ns =>
          ns.map(x => x.id === n.id ? { ...x, read: true } : x)
        ),
      error: () => {},
    });
  }

  markAllRead() {
    this.api.markAllNotificationsRead().subscribe({
      next: () => {
        this.notifications.update(ns => ns.map(n => ({ ...n, read: true })));
        this.toast.success('All caught up', 'All notifications marked as read.');
      },
      error: () => this.toast.error('Failed to update notifications'),
    });
  }

  notifIcon(type: NotificationType | string): string {
    return NOTIF_ICONS[type as NotificationType] ?? '🔔';
  }

  trackId(_: number, n: Notification) { return n.id; }
}
