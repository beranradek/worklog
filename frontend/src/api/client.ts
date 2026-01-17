/**
 * API client for the Worklog Application
 */

// API base URL - use VITE_API_URL if set, otherwise use relative URLs (same origin)
// In production, frontend is served by backend, so relative URLs work
// In development, set VITE_API_URL=http://localhost:8000 in .env
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

console.log(`[API Client] Using API base URL: ${API_BASE_URL || '(relative - same origin)'}`);

// Storage keys for authentication tokens
const ACCESS_TOKEN_KEY = 'worklog_access_token';
const REFRESH_TOKEN_KEY = 'worklog_refresh_token';
const USER_KEY = 'worklog_user';

/**
 * Get the stored access token from localStorage
 */
export function getStoredAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/**
 * Store access token in localStorage
 */
export function setStoredAccessToken(token: string | null): void {
  if (token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
  }
}

/**
 * Get the stored refresh token from localStorage
 */
export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Store refresh token in localStorage
 */
export function setStoredRefreshToken(token: string | null): void {
  if (token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

/**
 * Get the stored user from localStorage
 */
export function getStoredUser(): User | null {
  const stored = localStorage.getItem(USER_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as User;
  } catch {
    return null;
  }
}

/**
 * Store user in localStorage
 */
export function setStoredUser(user: User | null): void {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

/**
 * Clear all stored authentication data
 */
export function clearAuth(): void {
  setStoredAccessToken(null);
  setStoredRefreshToken(null);
  setStoredUser(null);
}

/**
 * Check if we have a stored access token
 */
export function hasStoredAccessToken(): boolean {
  return !!getStoredAccessToken();
}

// Type definitions
export interface User {
  id: string;
  email: string;
  name?: string | null;
  avatar_url?: string | null;
  provider?: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
  user: User;
}

export interface WorklogEntry {
  id: string | number;  // Can be UUID string or integer from backend
  issueKey: string;
  startTime: string;
  endTime: string;
  description: string;
  loggedToJira: boolean;
  jiraWorklogId: string | null;
}

export interface DayWorklog {
  date: string;
  entries: WorklogEntry[];
}

export interface JiraConfig {
  configured: boolean;
  base_url: string | null;
  has_token: boolean;
  has_email: boolean;
}

export interface JiraConfigUpdate {
  jira_base_url?: string;
  jira_user_email?: string;
  jira_api_token?: string;
}

export interface LogToJiraResponse {
  success: boolean;
  jira_worklog_id?: string;
  error?: string;
}

export interface BulkLogResult {
  issue_key: string;
  success: boolean;
  entry_ids: string[];
  duration: string;
  jira_worklog_id?: string;
  error?: string;
}

export interface BulkLogToJiraResponse {
  total_issues: number;
  success_count: number;
  failure_count: number;
  results: BulkLogResult[];
}

/**
 * Backend entry format (snake_case)
 */
interface BackendWorklogEntry {
  id?: string | number;
  issue_key: string;
  start_time: string;
  end_time: string;
  description: string;
  logged_to_jira?: boolean;
  jira_worklog_id?: string | null;
}

/**
 * Backend response for day worklog
 */
interface BackendDayWorklog {
  date: string;
  entries: BackendWorklogEntry[];
}

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

/**
 * Refresh the access token using the refresh token
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh?refresh_token=${refreshToken}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to refresh token');
    }

    const data: TokenResponse = await response.json();
    setStoredAccessToken(data.access_token);
    setStoredRefreshToken(data.refresh_token);
    setStoredUser(data.user);
    return data.access_token;
  } catch (error) {
    console.error('Token refresh failed:', error);
    clearAuth();
    // Redirect to login
    window.location.href = '/';
    return null;
  }
}

/**
 * Generic fetch wrapper with error handling and Bearer token authentication
 */
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  // Build headers with optional Bearer token
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  };

  // Add Authorization header if we have an access token
  const accessToken = getStoredAccessToken();
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  try {
    let response = await fetch(url, {
      ...options,
      headers,
    });

    // Handle 401 - try to refresh token
    if (response.status === 401 && accessToken) {
      if (!isRefreshing) {
        isRefreshing = true;
        const newToken = await refreshAccessToken();
        isRefreshing = false;

        if (newToken) {
          onTokenRefreshed(newToken);
          // Retry the original request with new token
          headers['Authorization'] = `Bearer ${newToken}`;
          response = await fetch(url, {
            ...options,
            headers,
          });
        }
      } else {
        // Wait for the ongoing refresh to complete
        const newToken = await new Promise<string>((resolve) => {
          subscribeTokenRefresh(resolve);
        });
        headers['Authorization'] = `Bearer ${newToken}`;
        response = await fetch(url, {
          ...options,
          headers,
        });
      }
    }

    if (!response.ok) {
      const errorText = await response.text();
      // Parse JSON error if possible
      try {
        const errorJson = JSON.parse(errorText);
        console.error('[API Client] Error response:', errorJson);
        throw new Error(errorJson.detail || errorJson.message || `API Error: ${response.status}`);
      } catch {
        console.error('[API Client] Error response (raw):', errorText);
        throw new Error(`API Error: ${response.status} - ${errorText}`);
      }
    }

    return await response.json();
  } catch (error) {
    console.error(`Failed to fetch ${endpoint}:`, error);
    throw error;
  }
}

/**
 * Transform backend entry (snake_case) to frontend format (camelCase)
 */
function transformEntryFromBackend(backendEntry: BackendWorklogEntry): WorklogEntry {
  return {
    id: backendEntry.id || '',  // Keep as-is (can be string UUID or integer)
    issueKey: backendEntry.issue_key || '',
    startTime: backendEntry.start_time || '',
    endTime: backendEntry.end_time || '',
    description: backendEntry.description || '',
    loggedToJira: backendEntry.logged_to_jira || false,
    jiraWorklogId: backendEntry.jira_worklog_id || null,
  };
}

/**
 * Transform frontend entry (camelCase) to backend format (snake_case)
 */
function transformEntryToBackend(entry: WorklogEntry) {
  return {
    issue_key: entry.issueKey,
    start_time: entry.startTime,
    end_time: entry.endTime,
    description: entry.description,
  };
}

/**
 * API Client
 */
export const apiClient = {
  // Authentication
  getGoogleAuthUrl: (codeChallenge: string, redirectUrl?: string) => {
    const params = new URLSearchParams({ code_challenge: codeChallenge });
    if (redirectUrl) {
      params.append('redirect_url', redirectUrl);
    }
    return fetchAPI<{ url: string }>(`/api/auth/google?${params.toString()}`);
  },

  handleAuthCallback: (code: string, codeVerifier: string) =>
    fetchAPI<TokenResponse>('/api/auth/callback', {
      method: 'POST',
      body: JSON.stringify({ code, code_verifier: codeVerifier }),
    }),

  refreshToken: async () => {
    return await refreshAccessToken();
  },

  logout: () =>
    fetchAPI<{ message: string }>('/api/auth/logout', {
      method: 'POST',
    }).finally(() => {
      clearAuth();
      window.location.href = '/';
    }),

  getCurrentUser: () => fetchAPI<User>('/api/auth/me'),

  // Worklog
  getWorklog: async (date: string): Promise<DayWorklog> => {
    const response = await fetchAPI<BackendDayWorklog>(`/api/worklog/${date}`);
    return {
      date: response.date,
      entries: response.entries.map(transformEntryFromBackend),
    };
  },

  saveWorklog: async (date: string, entries: WorklogEntry[]): Promise<DayWorklog> => {
    // Transform camelCase to snake_case for backend
    const backendEntries = entries.map(transformEntryToBackend);
    const response = await fetchAPI<BackendDayWorklog>(`/api/worklog/${date}`, {
      method: 'PUT',
      body: JSON.stringify({ entries: backendEntries }),
    });
    return {
      date: response.date,
      entries: response.entries.map(transformEntryFromBackend),
    };
  },

  // JIRA Configuration
  getJiraConfig: () =>
    fetchAPI<JiraConfig>('/api/worklog/jira/config'),

  updateJiraConfig: (config: JiraConfigUpdate) =>
    fetchAPI<JiraConfig>('/api/worklog/jira/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    }),

  logToJira: (date: string, entryId: string) =>
    fetchAPI<LogToJiraResponse>(`/api/worklog/${date}/entries/${entryId}/log-to-jira`, {
      method: 'POST',
    }),

  bulkLogToJira: (date: string) =>
    fetchAPI<BulkLogToJiraResponse>(`/api/worklog/${date}/bulk-log-to-jira`, {
      method: 'POST',
    }),
};
