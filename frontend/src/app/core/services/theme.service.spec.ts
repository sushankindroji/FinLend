import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  let service: ThemeService;

  beforeEach(() => {
    localStorage.clear();
    // Reset html class
    document.documentElement.classList.remove('dark');
    TestBed.configureTestingModule({});
    service = TestBed.inject(ThemeService);
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('reads light preference from localStorage', () => {
    localStorage.setItem('finlend_theme', 'light');
    const s2 = new ThemeService();
    expect(s2.isDark()).toBeFalse();
  });

  it('reads dark preference from localStorage', () => {
    localStorage.setItem('finlend_theme', 'dark');
    const s2 = new ThemeService();
    expect(s2.isDark()).toBeTrue();
  });

  it('toggle flips isDark', () => {
    const before = service.isDark();
    service.toggle();
    expect(service.isDark()).toBe(!before);
  });

  it('toggle twice returns to original value', () => {
    const before = service.isDark();
    service.toggle();
    service.toggle();
    expect(service.isDark()).toBe(before);
  });

  it('adds dark class to html when isDark is true', fakeAsync(() => {
    localStorage.setItem('finlend_theme', 'dark');
    const s2 = new ThemeService();
    tick();
    expect(document.documentElement.classList.contains('dark')).toBeTrue();
  }));

  it('removes dark class from html when isDark is false', fakeAsync(() => {
    document.documentElement.classList.add('dark');
    localStorage.setItem('finlend_theme', 'light');
    const s2 = new ThemeService();
    tick();
    expect(document.documentElement.classList.contains('dark')).toBeFalse();
  }));
});
