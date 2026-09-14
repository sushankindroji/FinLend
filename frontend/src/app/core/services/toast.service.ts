import { Injectable, signal } from '@angular/core';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
  leaving?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  toasts = signal<Toast[]>([]);

  private show(type: ToastType, title: string, message?: string, duration = 4000) {
    const id = crypto.randomUUID();
    this.toasts.update((ts) => [
      ...ts,
      { id, type, title, message, duration, leaving: false },
    ]);
    if (duration > 0) {
      // Start leave animation slightly before actual removal
      setTimeout(() => this._startLeave(id), duration - 300);
      setTimeout(() => this._remove(id), duration);
    }
    return id;
  }

  private _startLeave(id: string) {
    this.toasts.update((ts) =>
      ts.map((t) => (t.id === id ? { ...t, leaving: true } : t))
    );
  }

  private _remove(id: string) {
    this.toasts.update((ts) => ts.filter((t) => t.id !== id));
  }

  dismiss(id: string) {
    this._startLeave(id);
    setTimeout(() => this._remove(id), 300);
  }

  success(title: string, message?: string, duration?: number) {
    return this.show('success', title, message, duration);
  }
  error(title: string, message?: string, duration = 6000) {
    return this.show('error', title, message, duration);
  }
  warning(title: string, message?: string, duration?: number) {
    return this.show('warning', title, message, duration);
  }
  info(title: string, message?: string, duration?: number) {
    return this.show('info', title, message, duration);
  }
}
