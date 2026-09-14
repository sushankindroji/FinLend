import {
  Component, Input, OnInit, signal, ChangeDetectionStrategy
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';
import { ApiService } from '../../core/services/api.service';
import { StatusBadgeComponent } from './status-badge.component';

interface NavLink { label: string; path: string; icon: string; }

const ICONS = {
  home: 'M3 10.5 12 3l9 7.5M5.5 9.5V21h13V9.5M9 21v-6h6v6',
  loans: 'M7 3.5h8l3 3V21H6V3.5h9M9 12h6M9 16h6',
  bell: 'M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  market: 'M4 6h16l-1.5 11h-13L4 6Zm3-3 2 3m6-3-2 3M8 20a1 1 0 1 0 0 2 1 1 0 0 0 0-2Zm8 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
  portfolio: 'M4 19V9m5 10V5m5 14v-7m5 7V3',
  users: 'M16 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2m8-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8 10v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  money: 'M3 7h18v12H3zM7 7V5h10v2M12 11v4m-2-2h4',
  flag: 'm5 4 14 3-4 6 4 6-14-3V4Z',
};

const BORROWER_LINKS: NavLink[] = [
  { label: 'Dashboard', path: '/borrower', icon: ICONS.home },
  { label: 'My Loans', path: '/borrower/loans', icon: ICONS.loans },
];
const LENDER_LINKS: NavLink[] = [
  { label: 'Dashboard', path: '/lender', icon: ICONS.home },
  { label: 'Marketplace', path: '/lender/marketplace', icon: ICONS.market },
  { label: 'Portfolio', path: '/lender/portfolio', icon: ICONS.portfolio },
];
const ADMIN_LINKS: NavLink[] = [
  { label: 'Overview', path: '/admin', icon: ICONS.home },
  { label: 'Users', path: '/admin/users', icon: ICONS.users },
  { label: 'Loans', path: '/admin/loans', icon: ICONS.money },
  { label: 'Flags', path: '/admin/flags', icon: ICONS.flag },
];

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="fl-nav" aria-label="Primary navigation">
      <div class="fl-nav-shell">
        <a [routerLink]="homeLink" class="fl-brand" aria-label="FinLend home">
          <span class="fl-brand-mark">F</span>
          <span class="fl-brand-name">FinLend</span>
        </a>

        <div class="fl-nav-links">
          <a *ngFor="let link of navLinks"
             [routerLink]="link.path"
             routerLinkActive="is-active"
             [routerLinkActiveOptions]="{ exact: link.path === homeLink }"
             class="fl-nav-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path [attr.d]="link.icon"></path>
            </svg>
            <span>{{ link.label }}</span>
          </a>
        </div>

        <div class="fl-nav-actions">
          <a [routerLink]="notifLink" class="fl-nav-icon" aria-label="Notifications" title="Notifications">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                 stroke-linecap="round" stroke-linejoin="round"><path [attr.d]="ICONS.bell"></path></svg>
            <span *ngIf="unreadCount() > 0" class="fl-notif-dot">{{ unreadCount() > 9 ? '9+' : unreadCount() }}</span>
          </a>
          <button class="fl-nav-icon" (click)="theme.toggle()"
                  [attr.aria-label]="theme.isDark() ? 'Switch to light mode' : 'Switch to dark mode'">
            <svg *ngIf="!theme.isDark()" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>
            <svg *ngIf="theme.isDark()" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 15.3A8.5 8.5 0 0 1 8.7 3.5 8.5 8.5 0 1 0 20.5 15.3Z"/></svg>
          </button>

          <div class="fl-user-chip">
            <span class="fl-avatar">{{ initials() }}</span>
            <span class="fl-user-copy">
              <strong>{{ userName() || 'Account' }}</strong>
              <small>{{ role }}</small>
            </span>
          </div>
          <button class="fl-logout" (click)="logout()">Sign out</button>
        </div>
      </div>
    </nav>
  `,
  styles: [`
    .fl-nav{position:sticky;top:14px;z-index:70;padding:0 14px}
    .fl-nav-shell{max-width:1180px;height:68px;margin:auto;display:flex;align-items:center;gap:12px;padding:0 10px 0 14px;border:1px solid var(--fl-border);border-radius:22px;background:rgba(255,255,255,.67);backdrop-filter:blur(28px) saturate(180%);-webkit-backdrop-filter:blur(28px) saturate(180%);box-shadow:0 16px 55px rgba(34,47,83,.10),inset 0 1px 0 rgba(255,255,255,.8);animation:navIn .45s cubic-bezier(.2,.75,.25,1)}
    :host-context(.dark) .fl-nav-shell{background:rgba(17,22,35,.74);box-shadow:0 20px 70px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.06)}
    .fl-brand{display:flex;align-items:center;gap:10px;padding:7px 10px 7px 4px;color:var(--fl-on-surface);flex-shrink:0}
    .fl-brand-mark{width:34px;height:34px;border-radius:12px;display:grid;place-items:center;color:#fff;font-weight:750;background:linear-gradient(145deg,#527eff,#2857dc);box-shadow:0 8px 20px rgba(53,103,246,.28),inset 0 1px 0 rgba(255,255,255,.35)}
    .fl-brand-name{font-size:15px;font-weight:720;letter-spacing:-.02em}
    .fl-nav-links{display:flex;align-items:center;gap:3px;flex:1}
    .fl-nav-link{display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:13px;color:var(--fl-on-surface-muted);font-size:12px;font-weight:620;transition:all .22s ease}
    .fl-nav-link svg{width:16px;height:16px;opacity:.8}
    .fl-nav-link:hover{color:var(--fl-on-surface);background:rgba(255,255,255,.55)}
    :host-context(.dark) .fl-nav-link:hover{background:rgba(255,255,255,.06)}
    .fl-nav-link.is-active{color:var(--fl-brand);background:rgba(53,103,246,.095);box-shadow:inset 0 0 0 1px rgba(53,103,246,.06)}
    .fl-nav-link.is-active svg{opacity:1}
    .fl-nav-actions{display:flex;align-items:center;gap:4px;margin-left:auto}
    .fl-nav-icon{position:relative;width:38px;height:38px;border:1px solid transparent;border-radius:12px;background:transparent;color:var(--fl-on-surface-muted);display:grid;place-items:center;cursor:pointer;transition:all .2s ease}
    .fl-nav-icon svg{width:18px;height:18px}
    .fl-nav-icon:hover{background:rgba(255,255,255,.62);border-color:var(--fl-border);color:var(--fl-on-surface);transform:translateY(-1px)}
    :host-context(.dark) .fl-nav-icon:hover{background:rgba(255,255,255,.07)}
    .fl-notif-dot{position:absolute;top:3px;right:3px;min-width:15px;height:15px;padding:0 3px;border-radius:99px;display:grid;place-items:center;background:#e15a65;color:#fff;font-size:8px;font-weight:800;border:2px solid rgba(255,255,255,.8)}
    .fl-user-chip{display:flex;align-items:center;gap:8px;padding:4px 7px 4px 9px;margin-left:3px;border-left:1px solid var(--fl-border-soft)}
    .fl-avatar{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;color:#3159c7;background:rgba(53,103,246,.10);font-size:11px;font-weight:750}
    .fl-user-copy{display:flex;flex-direction:column;line-height:1.1;min-width:55px}.fl-user-copy strong{font-size:11px;max-width:90px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.fl-user-copy small{font-size:9px;color:var(--fl-on-surface-muted);margin-top:3px;text-transform:capitalize}
    .fl-logout{border:0;background:transparent;color:var(--fl-on-surface-muted);font-size:11px;font-weight:650;padding:8px 9px;border-radius:10px;cursor:pointer;transition:.2s ease}.fl-logout:hover{color:var(--fl-danger);background:rgba(217,75,87,.07)}
    @keyframes navIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
    @media(max-width:900px){.fl-nav-link span{display:none}.fl-nav-link{padding:10px}.fl-user-copy,.fl-logout{display:none}.fl-nav-shell{height:62px}.fl-user-chip{border-left:0;padding-left:3px}}
    @media(max-width:560px){.fl-nav{top:8px;padding:0 8px}.fl-nav-shell{border-radius:18px;padding-left:8px}.fl-brand-name{display:none}.fl-nav-links{gap:0}.fl-nav-link{padding:9px}.fl-nav-link svg{width:17px;height:17px}.fl-nav-actions{gap:0}}
  `],
})
export class NavbarComponent {
  @Input() set title(_: string) {}
  unreadCount = signal(0);
  userName = signal('');

  constructor(
    readonly theme: ThemeService,
    private auth: AuthService,
    private api: ApiService,
    private router: Router,
  ) {}
  ngOnInit() {
    this.api.me().subscribe({ next: u => this.userName.set(u.name ?? ''), error: () => {} });
    this.api.getNotifications(true).subscribe({ next: n => this.unreadCount.set(n.length), error: () => {} });
  }
  get role(): string { return this.auth.role() ?? ''; }
  get navLinks(): NavLink[] {
    const r=this.auth.role();
    if(r==='borrower') return BORROWER_LINKS;
    if(r==='lender') return LENDER_LINKS;
    if(r==='admin') return ADMIN_LINKS;
    return [];
  }
  get homeLink(): string { return `/${this.auth.role() ?? ''}`; }
  get notifLink(): string { return `/${this.auth.role() ?? ''}/notifications`; }
  initials(): string {
    const n=this.userName();
    if(!n) return (this.auth.role() ?? '?')[0].toUpperCase();
    return n.split(' ').slice(0,2).map(w=>w[0]).join('').toUpperCase();
  }
  logout(){this.auth.logout();this.router.navigate(['/login']);}
  readonly ICONS = ICONS;
}