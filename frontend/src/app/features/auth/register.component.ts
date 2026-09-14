import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ToastService } from '../../core/services/toast.service';
import { LoadingSpinnerComponent } from '../../shared/components/loading-spinner.component';
import { ToastContainerComponent } from '../../shared/components/toast-container.component';

type Step = 1 | 2 | 3;

@Component({
  selector:'app-register',standalone:true,
  imports:[CommonModule,FormsModule,RouterLink,LoadingSpinnerComponent,ToastContainerComponent],
  template:`
    <app-toast-container></app-toast-container>
    <main class="auth-shell register-shell">
      <div class="auth-ambient auth-ambient-a"></div><div class="auth-ambient auth-ambient-b"></div>
      <section class="auth-showcase">
        <div class="auth-showcase-inner">
          <div class="auth-logo"><span>F</span><strong>FinLend</strong></div>
          <div class="auth-hero"><span class="eyebrow">A BETTER WAY TO LEND</span><h1>Your financial<br><em>workspace, reimagined.</em></h1><p>Create one secure account and get a focused experience built around transparent lending, intelligent credit signals and simple decisions.</p></div>
          <div class="register-points"><div><span>01</span><strong>Build credit</strong><small>See how every repayment shapes your profile.</small></div><div><span>02</span><strong>Stay in control</strong><small>Clear balances, schedules and activity at a glance.</small></div><div><span>03</span><strong>Move with trust</strong><small>Every step is designed to be understandable.</small></div></div>
        </div>
      </section>
      <section class="auth-form-side">
        <div class="auth-form-wrap register-wrap">
          <div class="auth-mobile-brand"><span>F</span><strong>FinLend</strong></div>
          <div class="auth-heading"><span class="eyebrow">CREATE ACCOUNT</span><h2>Get started</h2><p>Set up your FinLend workspace in a few steps.</p></div>
          <div class="register-progress">
            <div *ngFor="let s of [1,2,3]" class="register-step" [class.active]="step===s" [class.done]="s < step"><span>{{s < step ? '✓' : s}}</span><small>{{s===1?'Account':s===2?'Profile':'Security'}}</small></div>
          </div>
          <div *ngIf="step===1" class="auth-form step-view">
            <div><label class="input-label">Choose your account</label><p class="input-hint">You can use FinLend as a borrower or lender.</p></div>
            <button *ngFor="let opt of roleOptions" type="button" class="role-card" [class.selected]="role===opt.value" (click)="role=opt.value">
              <span class="role-mark">{{opt.value==='borrower'?'B':'L'}}</span><span class="role-copy"><strong>{{opt.label}}</strong><small>{{opt.desc}}</small></span><span class="role-radio">{{role===opt.value?'✓':''}}</span>
            </button>
            <button class="btn-primary w-full py-3.5 mt-1" type="button" (click)="nextStep()">Continue</button>
          </div>
          <div *ngIf="step===2" class="auth-form step-view">
            <div><label class="input-label" for="reg-name">Full name</label><input id="reg-name" name="name" class="input-field" [class.input-field-error]="touched.name&&!name" [(ngModel)]="name" required (blur)="touched.name=true" autocomplete="name" placeholder="Jane Smith"/><p *ngIf="touched.name&&!name" class="input-error">Name is required</p></div>
            <div><label class="input-label" for="reg-email">Email address</label><input id="reg-email" name="email" type="email" class="input-field" [class.input-field-error]="touched.email&&!emailValid" [(ngModel)]="email" required (blur)="touched.email=true" autocomplete="email" placeholder="jane@example.com"/><p *ngIf="touched.email&&!emailValid" class="input-error">Enter a valid email address</p></div>
            <div><label class="input-label" for="reg-phone">Phone <span class="font-normal">(optional)</span></label><input id="reg-phone" name="phone" type="tel" class="input-field" [(ngModel)]="phone" autocomplete="tel" placeholder="+91 98765 43210"/><p class="input-hint">Used for voice features.</p></div>
            <div class="flex gap-3 mt-1"><button class="btn-secondary flex-1" type="button" (click)="prevStep()">Back</button><button class="btn-primary flex-1" type="button" (click)="nextStep()">Continue</button></div>
          </div>
          <div *ngIf="step===3" class="auth-form step-view">
            <div><label class="input-label" for="reg-pw">Password</label><div class="relative"><input id="reg-pw" name="password" [type]="showPw?'text':'password'" class="input-field pr-11" [class.input-field-error]="touched.password&&!pwValid" [(ngModel)]="password" required minlength="6" (blur)="touched.password=true" autocomplete="new-password" placeholder="Create a password"/><button type="button" class="password-toggle" (click)="showPw=!showPw">{{showPw?'Hide':'Show'}}</button></div>
            <div *ngIf="password" class="mt-2 space-y-1"><div class="progress-track h-1"><div class="progress-fill" [class]="strengthColor" [style.width.%]="strengthPct"></div></div><p class="text-xs" [class]="strengthTextColor">{{strengthLabel}}</p></div><p *ngIf="touched.password&&!pwValid" class="input-error">Minimum 6 characters required</p></div>
            <div><label class="input-label" for="reg-pw2">Confirm password</label><input id="reg-pw2" name="confirm" [type]="showPw?'text':'password'" class="input-field" [class.input-field-error]="touched.confirm&&!passwordsMatch" [(ngModel)]="confirm" (blur)="touched.confirm=true" autocomplete="new-password" placeholder="Repeat your password"/><p *ngIf="touched.confirm&&!passwordsMatch" class="input-error">Passwords do not match</p></div>
            <div class="secure-note"><span>✓</span><div><strong>Your data stays yours</strong><small>FinLend is an academic prototype. No real money is involved.</small></div></div>
            <div class="flex gap-3 mt-1"><button class="btn-secondary flex-1" type="button" (click)="prevStep()">Back</button><button class="btn-primary flex-1" type="button" (click)="submit()" [disabled]="loading()"><app-spinner *ngIf="loading()" mode="inline" size="sm"></app-spinner>{{loading()?'Creating…':'Create account'}}</button></div>
          </div>
          <p class="auth-footer">Already have an account? <a routerLink="/login">Sign in</a></p>
        </div>
      </section>
    </main>
  `,
  styles:[`
    .auth-shell{min-height:100dvh;display:grid;grid-template-columns:1.05fr .95fr;position:relative;overflow:hidden;background:var(--fl-bg)}.auth-showcase{display:flex;align-items:center;padding:7vh clamp(36px,6vw,100px);position:relative;overflow:hidden;background:linear-gradient(145deg,rgba(232,238,255,.92),rgba(248,246,255,.68))}:host-context(.dark) .auth-showcase{background:linear-gradient(145deg,#0d1426,#101524)}.auth-showcase-inner{max-width:570px;width:100%;margin:auto;position:relative;z-index:2}.auth-logo{display:flex;align-items:center;gap:10px;color:var(--fl-on-surface)}.auth-logo span,.auth-mobile-brand span{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(145deg,#527eff,#2857dc);color:#fff;font-weight:800;box-shadow:0 10px 25px rgba(53,103,246,.25)}.auth-logo strong{font-size:16px}.auth-hero{margin-top:14vh}.eyebrow{font-size:9px;font-weight:800;letter-spacing:.18em;color:var(--fl-brand)}.auth-hero h1{font-size:clamp(42px,5vw,68px);line-height:.99;letter-spacing:-.055em;margin:18px 0;font-weight:720}.auth-hero h1 em{font-style:normal;color:#5375d9}.auth-hero p{max-width:470px;color:var(--fl-on-surface-muted);font-size:15px;line-height:1.7}.register-points{margin-top:8vh;display:grid;gap:12px}.register-points>div{display:grid;grid-template-columns:34px 130px 1fr;gap:10px;align-items:center}.register-points span{font-size:9px;color:var(--fl-brand);font-weight:800}.register-points strong{font-size:11px}.register-points small{font-size:10px;color:var(--fl-on-surface-muted)}.auth-ambient{position:absolute;border-radius:50%;filter:blur(1px);pointer-events:none}.auth-ambient-a{width:500px;height:500px;background:rgba(90,127,255,.16);top:-250px;left:-180px}.auth-ambient-b{width:450px;height:450px;background:rgba(190,151,255,.13);right:-180px;bottom:-200px}.auth-form-side{display:flex;align-items:center;justify-content:center;padding:42px;position:relative;background:rgba(255,255,255,.38);border-left:1px solid var(--fl-border-soft)}:host-context(.dark) .auth-form-side{background:rgba(10,13,21,.35)}.auth-form-wrap{width:min(100%,410px)}.auth-mobile-brand{display:none}.auth-heading h2{font-size:34px;letter-spacing:-.045em;margin:9px 0 4px;font-weight:720}.auth-heading p{font-size:13px;color:var(--fl-on-surface-muted);margin:0 0 25px}.register-progress{display:flex;align-items:flex-start;margin:4px 0 30px;position:relative}.register-progress:before{content:"";height:1px;background:var(--fl-border-soft);position:absolute;top:14px;left:18px;right:18px}.register-step{position:relative;display:flex;flex-direction:column;align-items:center;gap:7px;flex:1;color:var(--fl-on-surface-muted)}.register-step span{width:29px;height:29px;border-radius:50%;display:grid;place-items:center;background:rgba(100,116,139,.09);border:1px solid var(--fl-border-soft);font-size:10px;font-weight:750}.register-step small{font-size:9px;font-weight:650}.register-step.active{color:var(--fl-brand)}.register-step.active span{background:var(--fl-brand);color:#fff;border-color:transparent;box-shadow:0 7px 17px rgba(53,103,246,.22)}.register-step.done{color:var(--fl-success)}.register-step.done span{background:rgba(22,155,98,.12);color:var(--fl-success);border-color:rgba(22,155,98,.16)}.step-view{animation:stepIn .3s ease}.role-card{display:flex;align-items:center;gap:13px;text-align:left;width:100%;padding:15px;border:1px solid var(--fl-border-soft);background:rgba(255,255,255,.45);border-radius:17px;cursor:pointer;transition:.22s var(--fl-ease)}:host-context(.dark) .role-card{background:rgba(255,255,255,.04)}.role-card:hover{transform:translateY(-1px);border-color:rgba(53,103,246,.2)}.role-card.selected{background:rgba(53,103,246,.065);border-color:rgba(53,103,246,.4);box-shadow:0 8px 25px rgba(53,103,246,.08)}.role-mark{width:37px;height:37px;border-radius:12px;display:grid;place-items:center;background:rgba(53,103,246,.1);color:var(--fl-brand);font-weight:800}.role-copy{flex:1}.role-copy strong{display:block;font-size:12px}.role-copy small{display:block;font-size:10px;line-height:1.5;color:var(--fl-on-surface-muted);margin-top:3px}.role-radio{width:19px;height:19px;border:1.5px solid rgba(100,116,139,.25);border-radius:50%;display:grid;place-items:center;font-size:9px;color:#fff}.selected .role-radio{background:var(--fl-brand);border-color:var(--fl-brand)}.secure-note{display:flex;gap:10px;padding:12px;border-radius:14px;background:rgba(22,155,98,.06);border:1px solid rgba(22,155,98,.10)}.secure-note>span{width:24px;height:24px;border-radius:8px;background:rgba(22,155,98,.12);color:var(--fl-success);display:grid;place-items:center;font-size:11px}.secure-note strong{display:block;font-size:10px}.secure-note small{display:block;font-size:9px;color:var(--fl-on-surface-muted);margin-top:3px}.auth-footer{text-align:center;color:var(--fl-on-surface-muted);font-size:12px;margin:24px 0 0}.auth-footer a{color:var(--fl-brand);font-weight:700}.password-toggle{position:absolute;right:11px;top:50%;transform:translateY(-50%);border:0;background:none;color:var(--fl-brand);font-size:10px;font-weight:700;cursor:pointer}.auth-form{display:flex;flex-direction:column;gap:17px}@keyframes stepIn{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}@media(max-width:820px){.auth-shell{grid-template-columns:1fr}.auth-showcase{display:none}.auth-form-side{min-height:100dvh;border:0;padding:28px 20px}.auth-mobile-brand{display:flex;align-items:center;gap:10px;margin-bottom:48px}.auth-form-wrap{max-width:430px}.auth-heading h2{font-size:31px}.register-progress{margin-bottom:26px}}
  `]
})
export class RegisterComponent {
  step: Step = 1;

  // form fields
  role = 'borrower';
  name = '';
  email = '';
  phone = '';
  password = '';
  confirm = '';
  showPw = false;
  loading = signal(false);

  touched: Record<string, boolean> = {
    name: false, email: false, password: false, confirm: false
  };

  roleOptions = [
    {
      value: 'borrower',
      label: 'Borrow funds',
      icon: '🙋',
      desc: 'Request micro-loans, build credit history, and repay on a flexible schedule.',
    },
    {
      value: 'lender',
      label: 'Lend & invest',
      icon: '💼',
      desc: 'Fund loan requests, earn returns, and manage your portfolio.',
    },
  ];

  constructor(
    private auth: AuthService,
    private toast: ToastService,
    private router: Router,
  ) {}

  get emailValid(): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.email);
  }
  get pwValid(): boolean { return this.password.length >= 6; }
  get passwordsMatch(): boolean { return this.password === this.confirm; }

  get strengthPct(): number {
    const p = this.password;
    let score = 0;
    if (p.length >= 6)  score += 25;
    if (p.length >= 10) score += 25;
    if (/[A-Z]/.test(p) && /[a-z]/.test(p)) score += 25;
    if (/[0-9!@#$%^&*]/.test(p)) score += 25;
    return score;
  }
  get strengthLabel(): string {
    const s = this.strengthPct;
    if (s <= 25) return 'Weak';
    if (s <= 50) return 'Fair';
    if (s <= 75) return 'Good';
    return 'Strong';
  }
  get strengthColor(): string {
    const s = this.strengthPct;
    if (s <= 25) return 'bg-danger-500';
    if (s <= 50) return 'bg-warning-500';
    if (s <= 75) return 'bg-info-500';
    return 'bg-success-500';
  }
  get strengthTextColor(): string {
    const s = this.strengthPct;
    if (s <= 25) return 'text-danger-600 dark:text-danger-400';
    if (s <= 50) return 'text-warning-600 dark:text-warning-400';
    if (s <= 75) return 'text-info-600 dark:text-info-400';
    return 'text-success-600 dark:text-success-400';
  }

  stepClass(s: number): string {
    if (s < this.step) return 'wizard-step-done';
    if (s === this.step) return 'wizard-step-active';
    return 'wizard-step-inactive';
  }

  nextStep() {
    if (this.step === 1) {
      // Role already chosen; just advance
      this.step = 2;
    } else if (this.step === 2) {
      this.touched.name = true;
      this.touched.email = true;
      if (!this.name || !this.emailValid) return;
      this.step = 3;
    }
  }

  prevStep() {
    if (this.step > 1) this.step = (this.step - 1) as Step;
  }

  submit() {
    this.touched.password = true;
    this.touched.confirm  = true;
    if (!this.pwValid || !this.passwordsMatch) return;

    this.loading.set(true);
    this.auth.register({
      name: this.name,
      email: this.email,
      password: this.password,
      role: this.role,
      phone: this.phone || undefined,
    }).subscribe({
      next: (res) => {
        this.loading.set(false);
        this.toast.success('Account created!', `Welcome to FinLend, ${this.name}.`);
        setTimeout(() => this.router.navigate([`/${res.role}`]), 500);
      },
      error: (err) => {
        this.loading.set(false);
        const msg = err?.error?.detail ?? 'Registration failed. Try a different email.';
        this.toast.error('Registration failed', msg);
      },
    });
  }
}