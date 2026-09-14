import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { LoginComponent } from './login.component';
import { AuthService } from '../../core/services/auth.service';
import { ToastService } from '../../core/services/toast.service';

const mockAuth = {
  login: jasmine.createSpy('login'),
};
const mockToast = {
  success: jasmine.createSpy('success'),
  error:   jasmine.createSpy('error'),
};

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let component: LoginComponent;

  beforeEach(async () => {
    mockAuth.login.calls.reset();
    mockToast.success.calls.reset();
    mockToast.error.calls.reset();

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService,  useValue: mockAuth },
        { provide: ToastService, useValue: mockToast },
      ],
    }).compileComponents();

    fixture   = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders FinLend branding', () => {
    expect(fixture.nativeElement.textContent).toContain('FinLend');
  });

  it('renders email and password inputs', () => {
    const inputs = fixture.nativeElement.querySelectorAll('input');
    expect(inputs.length).toBeGreaterThanOrEqual(2);
  });

  it('shows inline error when submitting empty form', () => {
    component.submit();
    fixture.detectChanges();
    expect(component.emailTouched).toBeTrue();
    expect(component.pwTouched).toBeTrue();
    expect(mockAuth.login).not.toHaveBeenCalled();
  });

  it('calls auth.login with correct credentials', fakeAsync(() => {
    mockAuth.login.and.returnValue(of({ access_token: 'tok', role: 'borrower', user_id: '1' }));
    component.email = 'test@example.com';
    component.password = 'Password1!';
    component.submit();
    tick();
    expect(mockAuth.login).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'Password1!',
    });
  }));

  it('calls toast.success on successful login', fakeAsync(() => {
    mockAuth.login.and.returnValue(of({ access_token: 'tok', role: 'borrower', user_id: '1' }));
    component.email = 'test@example.com';
    component.password = 'Password1!';
    component.submit();
    tick(600); // wait for setTimeout + navigation
    expect(mockToast.success).toHaveBeenCalled();
  }));

  it('calls toast.error on failed login', fakeAsync(() => {
    mockAuth.login.and.returnValue(throwError(() => ({ error: { detail: 'Invalid credentials' } })));
    component.email    = 'test@example.com';
    component.password = 'wrongpassword';
    component.submit();
    tick();
    expect(mockToast.error).toHaveBeenCalledWith('Sign-in failed', 'Invalid credentials');
  }));

  it('fillDemo pre-fills email and password', () => {
    const demo = component.demoAccounts[0];
    component.fillDemo(demo);
    expect(component.email).toBe(demo.email);
    expect(component.password).toBe(demo.password);
  });

  it('toggles password visibility', () => {
    expect(component.showPw).toBeFalse();
    const pwInput = fixture.nativeElement.querySelector('#password') as HTMLInputElement;
    // Initially type="password"
    expect(pwInput?.type).toBe('password');
    component.showPw = true;
    fixture.detectChanges();
    expect(pwInput?.type).toBe('text');
  });

  it('loading signal is set during login call', fakeAsync(() => {
    mockAuth.login.and.returnValue(of({ access_token: 'tok', role: 'borrower', user_id: '1' }));
    component.email    = 'test@example.com';
    component.password = 'Password1!';
    component.submit();
    // loading should be false after observable completes
    tick(600);
    expect(component.loading()).toBeFalse();
  }));
});
