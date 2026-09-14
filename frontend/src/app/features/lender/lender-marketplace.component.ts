/**
 * Standalone lender marketplace page — same content as the marketplace tab
 * on the dashboard, but accessible via deep-link /lender/marketplace.
 * Reuses LenderDashboardComponent by redirecting activeTab programmatically.
 */
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LenderDashboardComponent } from './lender-dashboard.component';

@Component({
  selector: 'app-lender-marketplace',
  standalone: true,
  imports: [LenderDashboardComponent],
  template: `<app-lender-dashboard></app-lender-dashboard>`,
})
export class LenderMarketplaceComponent {}
