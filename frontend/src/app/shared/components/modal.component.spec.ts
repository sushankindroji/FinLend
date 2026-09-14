import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { ModalComponent } from './modal.component';

describe('ModalComponent', () => {
  let fixture: ComponentFixture<ModalComponent>;
  let component: ModalComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ModalComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(ModalComponent);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('does not render backdrop when open=false', () => {
    component.open = false;
    fixture.detectChanges();
    const backdrop = fixture.debugElement.query(By.css('.modal-backdrop'));
    expect(backdrop).toBeNull();
  });

  it('renders backdrop when open=true', () => {
    component.open = true;
    component.title = 'Test Modal';
    fixture.detectChanges();
    const backdrop = fixture.debugElement.query(By.css('.modal-backdrop'));
    expect(backdrop).toBeTruthy();
  });

  it('renders title inside modal box', () => {
    component.open = true;
    component.title = 'My Title';
    fixture.detectChanges();
    const h2 = fixture.nativeElement.querySelector('h2');
    expect(h2?.textContent?.trim()).toBe('My Title');
  });

  it('renders subtitle when provided', () => {
    component.open = true;
    component.title = 'Title';
    component.subtitle = 'Sub text';
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Sub text');
  });

  it('emits close event when close button clicked', () => {
    component.open = true;
    component.title = 'Close Test';
    fixture.detectChanges();
    const closeSpy = spyOn(component.close, 'emit');
    const closeBtn = fixture.nativeElement.querySelector('button[aria-label="Close modal"]');
    closeBtn.click();
    expect(closeSpy).toHaveBeenCalled();
  });

  it('emits close event on backdrop click when closeOnBackdrop=true', () => {
    component.open = true;
    component.title = 'Backdrop Test';
    component.closeOnBackdrop = true;
    fixture.detectChanges();
    const closeSpy = spyOn(component.close, 'emit');
    const backdrop = fixture.debugElement.query(By.css('.modal-backdrop'));
    backdrop.triggerEventHandler('click', new MouseEvent('click'));
    expect(closeSpy).toHaveBeenCalled();
  });

  it('does not emit close on backdrop click when closeOnBackdrop=false', () => {
    component.open = true;
    component.title = 'No Close Test';
    component.closeOnBackdrop = false;
    fixture.detectChanges();
    const closeSpy = spyOn(component.close, 'emit');
    const backdrop = fixture.debugElement.query(By.css('.modal-backdrop'));
    backdrop.triggerEventHandler('click', new MouseEvent('click'));
    expect(closeSpy).not.toHaveBeenCalled();
  });

  it('emits close on Escape key press when open', () => {
    component.open = true;
    fixture.detectChanges();
    const closeSpy = spyOn(component.close, 'emit');
    component.onEsc();
    expect(closeSpy).toHaveBeenCalled();
  });

  it('does not emit close on Escape when closed', () => {
    component.open = false;
    fixture.detectChanges();
    const closeSpy = spyOn(component.close, 'emit');
    component.onEsc();
    expect(closeSpy).not.toHaveBeenCalled();
  });
});
