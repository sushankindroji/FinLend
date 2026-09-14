import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { RegisterComponent } from './register.component';
import { AuthService } from '../../core/services/auth.service';
import { ToastService } from '../../core/services/toast.service';

const mockAuth  = { register: jasmine.createSpy('register') };
const mockToast = { success: jasmine.createSpy('success'), error: jasmine.createSpy('error') };

describe('RegisterComponent', () => {
  let fixture: ComponentFixture<RegisterComponent>;
  let component: RegisterComponent;

  beforeEach(async () => {
    mockAuth.register.calls.reset();
    mockToast.success.calls.reset();
    mockToast.error.calls.reset();

    await TestBed.configureTestingModule({
      imports: [RegisterComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService,  useValue: mockAuth },
        { provide: ToastService, useValue: mockToast },
      ],
    }).compileComponents();

    fixture   = TestBed.createComponent(RegisterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('starts on step 1', () => {
    expect(component.step).toBe(1);
  });

  it('renders role-selection cards on step 1', () => {
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Borrow funds');
    expect(text).toContain('Lend & invest');
  });

  it('advancing to step 2 requires no validation (role always pre-selected)', () => {
    component.nextStep();
    expect(component.step).toBe(2);
  });

  it('emailValid returns false for malformed email', () => {
    component.email = 'not-an-email';
    expect(component.emailValid).toBeFalse();
  });

  it('emailValid returns true for well-formed email', () => {
    component.email = 'user@example.com';
    expect(component.emailValid).toBeTrue();
  });

  it('cannot advance from step 2 without name and valid email', () => {
    component.step = 2;
    component.name = '';
    component.email = 'bad';
    component.nextStep();
    expect(component.step).toBe(2);
  });

  it('advances from step 2 when name and email are valid', () => {
    component.step = 2;
    component.name = 'Jane Smith';
    component.email = 'jane@example.com';
    component.nextStep();
    expect(component.step).toBe(3);
  });

  it('pwValid returns false for short passwords', () => {
    component.password = 'abc';
    expect(component.pwValid).toBeFalse();
  });

  it('pwValid returns true for 6+ char passwords', () => {
    component.password = 'abc123';
    expect(component.pwValid).toBeTrue();
  });

  it('passwordsMatch is true when passwords match', () => {
    component.password = 'Password1!';
    component.confirm  = 'Password1!';
    expect(component.passwordsMatch).toBeTrue();
  });

  it('passwordsMatch is false when passwords differ', () => {
    component.password = 'Password1!';
    component.confirm  = 'different';
    expect(component.passwordsMatch).toBeFalse();
  });

  it('strengthPct increases with complexity', () => {
    component.password = 'a';
    const weak = component.strengthPct;
    component.password = 'aB1!longpass';
    const strong = component.strengthPct;
    expect(strong).toBeGreaterThan(weak);
  });

  it('calls auth.register on valid step-3 submit', fakeAsync(() => {
    mockAuth.register.and.returnValue(of({ access_token: 'tok', role: 'borrower', user_id: '1' }));
    component.step     = 3;
    component.name     = 'Jane';
    component.email    = 'jane@example.com';
    component.role     = 'borrower';
    component.password = 'Password1!';
    component.confirm  = 'Password1!';
    component.phone    = '+91 98765 43210';
    component.submit();
    tick(600);
    expect(mockAuth.register).toHaveBeenCalledWith({
      name: 'Jane',
      email: 'jane@example.com',
      password: 'Password1!',
      role: 'borrower',
      phone: '+91 98765 43210',
    });
  }));

  it('calls toast.error on registration failure', fakeAsync(() => {
    mockAuth.register.and.returnValue(throwError(() => ({ error: { detail: 'Email taken' } })));
    component.step     = 3;
    component.name     = 'Jane';
    component.email    = 'jane@example.com';
    component.password = 'Password1!';
    component.confirm  = 'Password1!';
    component.submit();
    tick();
    expect(mockToast.error).toHaveBeenCalledWith('Registration failed', 'Email taken');
  }));

  it('prevStep decrements step', () => {
    component.step = 2;
    component.prevStep();
    expect(component.step).toBe(1);
  });

  it('prevStep does not go below step 1', () => {
    component.step = 1;
    component.prevStep();
    expect(component.step).toBe(1);
  });

  it('does not call register when passwords do not match', () => {
    component.step     = 3;
    component.password = 'Password1!';
    component.confirm  = 'different';
    component.submit();
    expect(mockAuth.register).not.toHaveBeenCalled();
  });
});
