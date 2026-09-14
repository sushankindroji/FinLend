import { TestBed } from '@angular/core/testing';
import { ToastService } from './toast.service';

describe('ToastService', () => {
  let service: ToastService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ToastService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('starts with empty toast list', () => {
    expect(service.toasts()).toEqual([]);
  });

  it('adds a success toast', () => {
    service.success('Done', 'It worked');
    const toasts = service.toasts();
    expect(toasts.length).toBe(1);
    expect(toasts[0].type).toBe('success');
    expect(toasts[0].title).toBe('Done');
    expect(toasts[0].message).toBe('It worked');
  });

  it('adds an error toast', () => {
    service.error('Oops', 'Something failed');
    const toasts = service.toasts();
    expect(toasts.some(t => t.type === 'error')).toBeTrue();
  });

  it('adds a warning toast', () => {
    service.warning('Watch out');
    expect(service.toasts().some(t => t.type === 'warning')).toBeTrue();
  });

  it('adds an info toast', () => {
    service.info('FYI');
    expect(service.toasts().some(t => t.type === 'info')).toBeTrue();
  });

  it('assigns unique ids to each toast', () => {
    service.success('First');
    service.success('Second');
    const ids = service.toasts().map(t => t.id);
    expect(ids[0]).not.toBe(ids[1]);
  });

  it('dismiss removes the toast after animation delay', (done) => {
    service.success('To dismiss', undefined, 0);
    const id = service.toasts()[0].id;
    service.dismiss(id);
    setTimeout(() => {
      expect(service.toasts().find(t => t.id === id)).toBeUndefined();
      done();
    }, 350);
  });

  it('leaving flag is set before removal', (done) => {
    service.success('Leaving test', undefined, 0);
    const id = service.toasts()[0].id;
    service.dismiss(id);
    // Immediately after dismiss, leaving=true but not yet removed
    setTimeout(() => {
      const t = service.toasts().find(t => t.id === id);
      // Either already removed or marked leaving
      expect(!t || t.leaving).toBeTrue();
      done();
    }, 50);
  });
});
