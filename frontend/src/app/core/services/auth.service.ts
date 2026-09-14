import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  role: 'borrower' | 'lender' | 'admin';
  user_id: string;
}

const TOKEN_KEY = 'finlend_token';
const ROLE_KEY = 'finlend_role';
const USER_ID_KEY = 'finlend_user_id';

@Injectable({ providedIn: 'root' })
export class AuthService {
  role = signal<string | null>(localStorage.getItem(ROLE_KEY));
  userId = signal<string | null>(localStorage.getItem(USER_ID_KEY));

  constructor(private http: HttpClient) {}

  register(payload: { name: string; email: string; password: string; role: string; phone?: string }): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${environment.apiUrl}/auth/register`, payload).pipe(
      tap((res) => this.persistSession(res))
    );
  }

  login(payload: { email: string; password: string }): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${environment.apiUrl}/auth/login`, payload).pipe(
      tap((res) => this.persistSession(res))
    );
  }

  private persistSession(res: AuthResponse) {
    localStorage.setItem(TOKEN_KEY, res.access_token);
    localStorage.setItem(ROLE_KEY, res.role);
    localStorage.setItem(USER_ID_KEY, res.user_id);
    this.role.set(res.role);
    this.userId.set(res.user_id);
  }

  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
    localStorage.removeItem(USER_ID_KEY);
    this.role.set(null);
    this.userId.set(null);
  }

  get token(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  isLoggedIn(): boolean {
    return !!this.token;
  }
}
