import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Settings as SettingsIcon, LogOut } from 'lucide-react';
import { Login } from '@/components/Login';
import { Settings } from '@/components/Settings';
import { Worklog } from '@/components/Worklog';
import {
  apiClient,
  setStoredAccessToken,
  setStoredRefreshToken,
  setStoredUser,
  clearAuth,
  hasStoredAccessToken,
  type User
} from '@/api/client';
import { retrieveCodeVerifier } from '@/lib/pkce';
import { useToast } from '@/hooks/useToast';

type AuthState = 'loading' | 'authenticated' | 'unauthenticated';

function App() {
  const [authState, setAuthState] = useState<AuthState>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const toast = useToast();

  useEffect(() => {
    const initAuth = async () => {
      try {
        // Check if we're handling an OAuth callback
        const url = new URL(window.location.href);
        const code = url.searchParams.get('code');

        if (code) {
          // OAuth callback - exchange code for tokens
          console.log('[Auth] Handling OAuth callback');

          // Clean up URL immediately to prevent retry loops
          window.history.replaceState({}, document.title, window.location.pathname);

          // Retrieve PKCE code verifier
          const codeVerifier = retrieveCodeVerifier();
          if (!codeVerifier) {
            throw new Error('PKCE code verifier not found');
          }

          // Exchange code for tokens
          const tokenResponse = await apiClient.handleAuthCallback(code, codeVerifier);

          // Store tokens and user
          setStoredAccessToken(tokenResponse.access_token);
          setStoredRefreshToken(tokenResponse.refresh_token);
          setStoredUser(tokenResponse.user);

          setUser(tokenResponse.user);
          setAuthState('authenticated');
        } else if (hasStoredAccessToken()) {
          // Check if we have stored tokens - validate them
          console.log('[Auth] Checking stored session');
          try {
            const currentUser = await apiClient.getCurrentUser();
            setUser(currentUser);
            setAuthState('authenticated');
          } catch (error) {
            console.error('[Auth] Stored session invalid:', error);
            clearAuth();
            setAuthState('unauthenticated');
          }
        } else {
          // No code and no stored tokens - unauthenticated
          setAuthState('unauthenticated');
        }
      } catch (error) {
        console.error('Auth initialization failed:', error);
        clearAuth();
        setAuthState('unauthenticated');
        toast.error('Login Failed', error instanceof Error ? error.message : 'Authentication failed');
      }
    };

    initAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once on mount

  if (authState === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <p className="mt-2 text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (authState === 'unauthenticated') {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* Header */}
      <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Worklog</h1>
            <div className="flex items-center gap-3">
              {user && (
                <div className="hidden sm:flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
                  <span>{user.name || user.email}</span>
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSettingsOpen(true)}
                title="Settings"
              >
                <SettingsIcon className="h-4 w-4" />
                <span className="ml-2 hidden sm:inline">Settings</span>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => apiClient.logout()}
                title="Logout"
              >
                <LogOut className="h-4 w-4" />
                <span className="ml-2 hidden sm:inline">Logout</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto">
        <Worklog />
      </main>

      {/* Settings Modal */}
      <Settings open={settingsOpen} onOpenChange={setSettingsOpen} user={user} />
    </div>
  );
}

export default App;
