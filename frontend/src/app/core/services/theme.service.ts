import { Injectable, signal, effect } from '@angular/core';

const STORAGE_KEY = 'finlend_theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  isDark = signal<boolean>(this._loadPreference());

  constructor() {
    // Apply on startup
    this._apply(this.isDark());
    // Keep DOM in sync whenever the signal changes
    effect(() => {
      this._apply(this.isDark());
      localStorage.setItem(STORAGE_KEY, this.isDark() ? 'dark' : 'light');
    });
  }

  toggle() {
    this.isDark.update((v) => !v);
  }

  private _loadPreference(): boolean {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  private _apply(dark: boolean) {
    if (dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }
}
