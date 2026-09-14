import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ThemeService } from './core/services/theme.service';
import { ToastContainerComponent } from './shared/components/toast-container.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, ToastContainerComponent],
  template: `
    <!-- Global toast container (rendered above everything) -->
    <app-toast-container></app-toast-container>
    <div class="min-h-dvh">
      <router-outlet></router-outlet>
    </div>
  `,
})
export class AppComponent {
  // Injecting ThemeService here ensures it initializes (applies dark/light class)
  // on app startup before any component renders.
  private _theme = inject(ThemeService);
}
