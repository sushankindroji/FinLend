import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ToastService } from '../../core/services/toast.service';
import { LoadingSpinnerComponent } from '../../shared/components/loading-spinner.component';
import { ToastContainerComponent } from '../../shared/components/toast-container.component';

@Component({
  selector:'app-login', standalone:true,
  imports:[CommonModule,FormsModule,RouterLink,LoadingSpinnerComponent,ToastContainerComponent],
  template:`
    <app-toast-container></app-toast-container>
    
    <!-- Theme Toggle Button (Top Right) -->
    <button 
      class="theme-toggle-btn"
      (click)="toggleTheme()"
      [attr.aria-label]="isDark() ? 'Switch to light mode' : 'Switch to dark mode'">
      <svg *ngIf="!isDark()" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
      </svg>
      <svg *ngIf="isDark()" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    </button>
    
    <main class="auth-shell">
      <div class="auth-ambient auth-ambient-a"></div><div class="auth-ambient auth-ambient-b"></div>
      <section class="auth-showcase">
        <div class="auth-showcase-inner">
          <div class="auth-logo"><span>F</span><strong>FinLend</strong></div>
          <div class="auth-hero">
            <span class="eyebrow">PRIVATE LENDING, SIMPLIFIED</span>
            <h1>Move money with<br><em>more confidence.</em></h1>
            <p>A focused lending experience for borrowers, lenders and the teams that keep every transaction moving.</p>
          </div>
          <div class="auth-orbit">
            <div class="orbit-card orbit-card-main"><span class="orbit-kicker">AVAILABLE LIMIT</span><strong>₹2,50,000</strong><small>Based on your credit profile</small></div>
            <div class="orbit-card orbit-card-mini"><span class="orbit-check">✓</span><div><strong>10.0%</strong><small>Fixed platform rate</small></div></div>
          </div>
          <div class="auth-trust"><span>SECURE</span><i></i><span>TRANSPARENT</span><i></i><span>BUILT FOR TRUST</span></div>
        </div>
      </section>
      <section class="auth-form-side">
        <div class="auth-form-wrap">
          <div class="auth-mobile-brand"><span>F</span><strong>FinLend</strong></div>
          <div class="auth-heading"><span class="eyebrow">WELCOME BACK</span><h2>Sign in</h2><p>Access your FinLend workspace.</p></div>
          <form (ngSubmit)="submit()" #loginForm="ngForm" novalidate class="auth-form">
            <div>
              <label class="input-label" for="email">Email address</label>
              <input id="email" name="email" type="email" class="input-field" [class.input-field-error]="emailTouched && !email" [(ngModel)]="email" required (blur)="emailTouched=true" autocomplete="email" placeholder="you@example.com"/>
              <p *ngIf="emailTouched && !email" class="input-error">Email is required</p>
            </div>
            <div>
              <div class="auth-field-head"><label class="input-label mb-0" for="password">Password</label></div>
              <div class="relative"><input id="password" name="password" [type]="showPw?'text':'password'" class="input-field pr-11" [class.input-field-error]="pwTouched && !password" [(ngModel)]="password" required (blur)="pwTouched=true" autocomplete="current-password" placeholder="Enter your password"/>
              <button type="button" class="password-toggle" (click)="showPw=!showPw" [attr.aria-label]="showPw?'Hide password':'Show password'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/></svg></button></div>
              <p *ngIf="pwTouched && !password" class="input-error">Password is required</p>
            </div>
            <button class="btn-primary w-full py-3.5 text-sm" type="submit" [disabled]="loading()"><app-spinner *ngIf="loading()" mode="inline" size="sm"></app-spinner>{{loading()?'Signing in…':'Continue to FinLend'}}</button>
          </form>
          <div class="auth-divider"><span>Demo access</span></div>
          <div class="demo-grid">
            <button *ngFor="let demo of demoAccounts" type="button" class="demo-chip" (click)="fillDemo(demo)">
              <span>{{demo.label}}</span><small>Use demo account</small>
            </button>
          </div>
          <p class="auth-footer">New to FinLend? <a routerLink="/register">Create an account</a></p>
          <p class="auth-disclaimer">Academic prototype · no real money involved</p>
        </div>
      </section>
    </main>
  `,
  styles:[`
    .theme-toggle-btn{position:fixed;top:20px;right:20px;z-index:100;width:44px;height:44px;border-radius:12px;border:1px solid var(--fl-border-soft);background:rgba(255,255,255,.8);backdrop-filter:blur(10px);color:var(--fl-on-surface);display:grid;place-items:center;cursor:pointer;transition:all .2s ease;box-shadow:0 4px 12px rgba(0,0,0,.05)}:host-context(.dark) .theme-toggle-btn{background:rgba(255,255,255,.08)}.theme-toggle-btn:hover{transform:translateY(-2px);border-color:var(--fl-brand);box-shadow:0 6px 16px rgba(53,103,246,.15)}
    .auth-shell{min-height:100dvh;display:grid;grid-template-columns:1.05fr .95fr;position:relative;overflow:hidden;background:var(--fl-bg)}
    .auth-showcase{display:flex;align-items:center;padding:7vh clamp(36px,6vw,100px);position:relative;overflow:hidden;background:linear-gradient(145deg,rgba(232,238,255,.92),rgba(248,246,255,.68))}
    :host-context(.dark) .auth-showcase{background:linear-gradient(145deg,#0d1426,#101524)}
    .auth-showcase-inner{max-width:570px;width:100%;margin:auto;position:relative;z-index:2}.auth-logo,.auth-mobile-brand{display:flex;align-items:center;gap:10px;color:var(--fl-on-surface)}.auth-logo span,.auth-mobile-brand span{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(145deg,#527eff,#2857dc);color:#fff;font-weight:800;box-shadow:0 10px 25px rgba(53,103,246,.25)}.auth-logo strong{font-size:16px}
    .auth-hero{margin-top:14vh}.eyebrow{font-size:9px;font-weight:800;letter-spacing:.18em;color:var(--fl-brand)}.auth-hero h1{font-size:clamp(42px,5vw,68px);line-height:.99;letter-spacing:-.055em;margin:18px 0;color:var(--fl-on-surface);font-weight:720}.auth-hero h1 em{font-style:normal;color:#5375d9}.auth-hero p{max-width:450px;color:var(--fl-on-surface-muted);font-size:15px;line-height:1.7}
    .auth-orbit{height:190px;position:relative;margin-top:8vh}.orbit-card{position:absolute;border:1px solid rgba(255,255,255,.78);background:rgba(255,255,255,.5);backdrop-filter:blur(25px);box-shadow:0 24px 60px rgba(45,59,100,.11);border-radius:22px}:host-context(.dark) .orbit-card{background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.1)}.orbit-card-main{width:280px;padding:20px;transform:rotate(-4deg);left:4%}.orbit-kicker{display:block;font-size:9px;letter-spacing:.13em;color:var(--fl-on-surface-muted);font-weight:750}.orbit-card-main strong{display:block;font-size:30px;letter-spacing:-.04em;margin:8px 0 3px}.orbit-card-main small,.orbit-card-mini small{font-size:10px;color:var(--fl-on-surface-muted)}.orbit-card-mini{right:8%;bottom:0;padding:13px 16px;display:flex;gap:10px;align-items:center;transform:rotate(3deg)}.orbit-card-mini strong{display:block;font-size:15px}.orbit-check{width:30px;height:30px;border-radius:10px;background:rgba(22,155,98,.12);color:#159462;display:grid;place-items:center;font-weight:800}.auth-trust{display:flex;align-items:center;gap:10px;color:var(--fl-on-surface-muted);font-size:8px;font-weight:750;letter-spacing:.13em}.auth-trust i{width:3px;height:3px;border-radius:50%;background:currentColor;opacity:.45}
    .auth-ambient{position:absolute;border-radius:50%;filter:blur(1px);pointer-events:none}.auth-ambient-a{width:500px;height:500px;background:rgba(90,127,255,.16);top:-250px;left:-180px}.auth-ambient-b{width:450px;height:450px;background:rgba(190,151,255,.13);right:-180px;bottom:-200px}
    .auth-form-side{display:flex;align-items:center;justify-content:center;padding:42px;position:relative;background:rgba(255,255,255,.38);border-left:1px solid var(--fl-border-soft)}:host-context(.dark) .auth-form-side{background:rgba(10,13,21,.35)}.auth-form-wrap{width:min(100%,410px)}.auth-mobile-brand{display:none}.auth-heading h2{font-size:34px;letter-spacing:-.045em;margin:9px 0 4px;font-weight:720}.auth-heading p{font-size:13px;color:var(--fl-on-surface-muted);margin:0 0 30px}.auth-form{display:flex;flex-direction:column;gap:20px}.auth-field-head{margin-bottom:8px}.password-toggle{position:absolute;right:11px;top:50%;transform:translateY(-50%);width:28px;height:28px;border:0;background:none;color:var(--fl-on-surface-muted);display:grid;place-items:center;cursor:pointer}.password-toggle svg{width:17px}.auth-divider{display:flex;align-items:center;gap:12px;margin:25px 0 13px;color:var(--fl-on-surface-muted);font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}.auth-divider:before,.auth-divider:after{content:"";height:1px;background:var(--fl-border-soft);flex:1}.demo-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.demo-chip{border:1px solid var(--fl-border-soft);background:rgba(255,255,255,.45);border-radius:14px;padding:11px 7px;cursor:pointer;color:var(--fl-on-surface);transition:.2s ease}:host-context(.dark) .demo-chip{background:rgba(255,255,255,.04)}.demo-chip:hover{border-color:rgba(53,103,246,.25);background:rgba(53,103,246,.06);transform:translateY(-2px)}.demo-chip span{display:block;font-size:11px;font-weight:700}.demo-chip small{display:block;margin-top:4px;font-size:8px;color:var(--fl-on-surface-muted)}.auth-footer{text-align:center;color:var(--fl-on-surface-muted);font-size:12px;margin:24px 0 0}.auth-footer a{color:var(--fl-brand);font-weight:700}.auth-disclaimer{text-align:center;color:var(--fl-on-surface-muted);opacity:.55;font-size:9px;margin-top:32px}
    @media(max-width:820px){.auth-shell{grid-template-columns:1fr}.auth-showcase{display:none}.auth-form-side{min-height:100dvh;border:0;padding:28px 20px}.auth-mobile-brand{display:flex;margin-bottom:54px}.auth-form-wrap{max-width:430px}.auth-heading h2{font-size:31px}}
  `]
})
export class LoginComponent {
  email = '';
  password = '';
  showPw = false;
  emailTouched = false;
  pwTouched = false;
  loading = signal(false);
  isDark = signal(false);

  demoAccounts = [
    { label: 'Borrower', icon: '🙋', email: 'borrower1@demo.finlend.test', password: 'Password123!' },
    { label: 'Lender',   icon: '💼', email: 'lender1@demo.finlend.test',   password: 'Password123!' },
    { label: 'Admin',    icon: '🛡️', email: 'admin@demo.finlend.test',      password: 'AdminPass123!' },
  ];

  constructor(
    private auth: AuthService,
    private toast: ToastService,
    private router: Router,
  ) {
    // Check current theme on init
    this.isDark.set(document.documentElement.classList.contains('dark'));
  }

  toggleTheme() {
    const html = document.documentElement;
    if (html.classList.contains('dark')) {
      html.classList.remove('dark');
      localStorage.setItem('theme', 'light');
      this.isDark.set(false);
    } else {
      html.classList.add('dark');
      localStorage.setItem('theme', 'dark');
      this.isDark.set(true);
    }
  }

  fillDemo(demo: { email: string; password: string }) {
    this.email = demo.email;
    this.password = demo.password;
  }

  submit() {
    this.emailTouched = true;
    this.pwTouched = true;
    if (!this.email || !this.password) return;

    this.loading.set(true);
    this.auth.login({ email: this.email, password: this.password }).subscribe({
      next: (res) => {
        this.loading.set(false);
        this.toast.success('Welcome back!', `Signed in as ${res.role}`);
        setTimeout(() => this.router.navigate([`/${res.role}`]), 400);
      },
      error: (err) => {
        this.loading.set(false);
        const msg = err?.error?.detail ?? 'Incorrect email or password';
        this.toast.error('Sign-in failed', msg);
      },
    });
  }
}