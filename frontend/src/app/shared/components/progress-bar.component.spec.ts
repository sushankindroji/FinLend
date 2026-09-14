import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ProgressBarComponent } from './progress-bar.component';

describe('ProgressBarComponent', () => {
  let fixture: ComponentFixture<ProgressBarComponent>;
  let component: ProgressBarComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProgressBarComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(ProgressBarComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('clamps negative pct to 0', () => {
    component.pct = -10;
    expect(component.clampedPct).toBe(0);
  });

  it('clamps pct above 100 to 100', () => {
    component.pct = 150;
    expect(component.clampedPct).toBe(100);
  });

  it('passes through pct in 0-100 range unchanged', () => {
    component.pct = 42;
    expect(component.clampedPct).toBe(42);
  });

  it('returns bg-brand-500 for brand color', () => {
    component.color = 'brand';
    expect(component.colorClass).toBe('bg-brand-500');
  });

  it('returns bg-success-500 for success color', () => {
    component.color = 'success';
    expect(component.colorClass).toBe('bg-success-500');
  });

  it('returns bg-danger-500 for danger color', () => {
    component.color = 'danger';
    expect(component.colorClass).toBe('bg-danger-500');
  });

  it('returns bg-warning-500 for warning color', () => {
    component.color = 'warning';
    expect(component.colorClass).toBe('bg-warning-500');
  });

  it('renders fill div at correct width', () => {
    component.pct = 60;
    component.color = 'success';
    fixture.detectChanges();
    const fill = fixture.nativeElement.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('60%');
  });

  it('renders label row when showLabel=true', () => {
    component.showLabel = true;
    component.label = 'Funded';
    component.pct = 50;
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Funded');
    expect(text).toContain('50');
  });

  it('does not render label row when showLabel=false', () => {
    component.showLabel = false;
    fixture.detectChanges();
    const labelEl = fixture.nativeElement.querySelector('.text-xs.font-medium');
    expect(labelEl).toBeNull();
  });
});
