import { ComponentFixture, TestBed } from '@angular/core/testing';
import { StatusBadgeComponent } from './status-badge.component';

describe('StatusBadgeComponent', () => {
  let fixture: ComponentFixture<StatusBadgeComponent>;
  let component: StatusBadgeComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StatusBadgeComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(StatusBadgeComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('returns badge-success for APPROVED status', () => {
    component.value = 'APPROVED';
    component.type = 'status';
    expect(component.cssClass).toBe('badge-success');
  });

  it('returns badge-danger for REJECTED status', () => {
    component.value = 'REJECTED';
    component.type = 'status';
    expect(component.cssClass).toBe('badge-danger');
  });

  it('returns badge-brand for ACTIVE status', () => {
    component.value = 'ACTIVE';
    component.type = 'status';
    expect(component.cssClass).toBe('badge-brand');
  });

  it('returns badge-warning for LATE status', () => {
    component.value = 'LATE';
    component.type = 'status';
    expect(component.cssClass).toBe('badge-warning');
  });

  it('returns badge-success for LOW risk', () => {
    component.value = 'LOW';
    component.type = 'risk';
    expect(component.cssClass).toBe('badge-success');
  });

  it('returns badge-danger for HIGH risk', () => {
    component.value = 'HIGH';
    component.type = 'risk';
    expect(component.cssClass).toBe('badge-danger');
  });

  it('returns badge-warning for MEDIUM risk', () => {
    component.value = 'MEDIUM';
    component.type = 'risk';
    expect(component.cssClass).toBe('badge-warning');
  });

  it('returns badge-gray for unknown value', () => {
    component.value = 'UNKNOWN_STATUS';
    component.type = 'status';
    expect(component.cssClass).toBe('badge-gray');
  });

  it('renders the value text when no label override', () => {
    component.value = 'REPAID';
    component.type = 'status';
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement.querySelector('span');
    expect(el.textContent?.trim()).toContain('REPAID');
  });

  it('renders label override instead of value', () => {
    component.value = 'REPAID';
    component.label = 'Completed';
    component.type = 'status';
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement.querySelector('span');
    expect(el.textContent?.trim()).toContain('Completed');
  });

  it('shows dot when dot=true', () => {
    component.value = 'ACTIVE';
    component.dot = true;
    fixture.detectChanges();
    const dot = fixture.nativeElement.querySelector('span span');
    expect(dot).toBeTruthy();
  });
});
