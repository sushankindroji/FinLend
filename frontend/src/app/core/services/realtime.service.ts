import { Injectable, signal } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface RealtimeEvent {
  event: string;
  data: any;
  timestamp: string;
}

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000;
  private reconnectTimer: any = null;
  private heartbeatTimer: any = null;
  private eventHandlers = new Map<string, Set<(data: any) => void>>();

  connectionStatus = signal<ConnectionStatus>('disconnected');
  lastEvent = signal<RealtimeEvent | null>(null);

  constructor() {
    // Auto-connect on service creation
    this.connect();
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      console.log('[Realtime] Already connected or connecting');
      return;
    }

    const wsUrl = environment.wsUrl || this.getWebSocketUrl();
    console.log('[Realtime] Connecting to:', wsUrl);

    this.connectionStatus.set('connecting');

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[Realtime] Connected');
        this.connectionStatus.set('connected');
        this.reconnectAttempts = 0;
        this.startHeartbeat();

        // Send authentication if needed
        const token = this.getAuthToken();
        if (token) {
          this.send('auth', { token });
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (err) {
          console.error('[Realtime] Failed to parse message:', err);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[Realtime] WebSocket error:', error);
        this.connectionStatus.set('error');
      };

      this.ws.onclose = (event) => {
        console.log('[Realtime] Connection closed:', event.code, event.reason);
        this.connectionStatus.set('disconnected');
        this.stopHeartbeat();
        
        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };
    } catch (err) {
      console.error('[Realtime] Failed to create WebSocket:', err);
      this.connectionStatus.set('error');
      this.scheduleReconnect();
    }
  }

  disconnect() {
    console.log('[Realtime] Disconnecting');
    this.stopHeartbeat();
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.connectionStatus.set('disconnected');
    this.reconnectAttempts = 0;
  }

  send(event: string, data: any = {}) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ event, data, timestamp: new Date().toISOString() });
      this.ws.send(message);
    } else {
      console.warn('[Realtime] Cannot send message: not connected');
    }
  }

  subscribe(event: string, handler: (data: any) => void) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    this.eventHandlers.get(event)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.eventHandlers.get(event);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.eventHandlers.delete(event);
        }
      }
    };
  }

  subscribeToLoan(loanId: string, handler: (data: any) => void) {
    return this.subscribe(`loan:${loanId}`, handler);
  }

  subscribeToMarketplace(handler: (data: any) => void) {
    return this.subscribe('marketplace', handler);
  }

  subscribeToUser(handler: (data: any) => void) {
    return this.subscribe('user', handler);
  }

  private handleMessage(message: RealtimeEvent) {
    console.log('[Realtime] Received:', message);

    // Update last event signal
    this.lastEvent.set(message);

    // Call registered handlers
    const handlers = this.eventHandlers.get(message.event);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message.data);
        } catch (err) {
          console.error('[Realtime] Handler error:', err);
        }
      });
    }

    // Also call wildcard handlers
    const wildcardHandlers = this.eventHandlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach(handler => {
        try {
          handler(message);
        } catch (err) {
          console.error('[Realtime] Wildcard handler error:', err);
        }
      });
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    console.log(`[Realtime] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send('ping', {});
      }
    }, 30000); // 30 seconds
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private getWebSocketUrl(): string {
    // Try to derive WebSocket URL from API URL
    const apiUrl = environment.apiUrl || 'http://localhost:8000/api';
    const baseUrl = apiUrl.replace('/api', '').replace('http://', 'ws://').replace('https://', 'wss://');
    return `${baseUrl}/ws`;
  }

  private getAuthToken(): string | null {
    // Get token from localStorage (matches auth service implementation)
    return localStorage.getItem('token');
  }

  // Cleanup on service destroy
  ngOnDestroy() {
    this.disconnect();
  }
}
