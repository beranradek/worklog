import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, LogOut, User as UserIcon } from 'lucide-react';
import { apiClient, type User, type JiraConfig, type JiraConfigUpdate } from '@/api/client';
import { useToast } from '@/hooks/useToast';

interface SettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: User | null;
}

export const Settings: React.FC<SettingsProps> = ({ open, onOpenChange, user }) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [jiraConfig, setJiraConfig] = useState<JiraConfig | null>(null);
  const [formData, setFormData] = useState<JiraConfigUpdate>({
    jira_base_url: '',
    jira_user_email: '',
    jira_api_token: '',
  });
  const toast = useToast();

  const loadJiraConfig = useCallback(async () => {
    setLoading(true);
    try {
      const config = await apiClient.getJiraConfig();
      setJiraConfig(config);
      // Populate form with existing config (but not the token for security)
      setFormData({
        jira_base_url: config.base_url || '',
        jira_user_email: '', // Don't show email for security
        jira_api_token: '', // Don't show token for security
      });
    } catch (error) {
      toast.error(
        'Failed to load JIRA configuration',
        error instanceof Error ? error.message : 'Unknown error'
      );
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (open) {
      loadJiraConfig();
    }
  }, [open, loadJiraConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Only send fields that have been modified
      const updates: JiraConfigUpdate = {};
      if (formData.jira_base_url) updates.jira_base_url = formData.jira_base_url;
      if (formData.jira_user_email) updates.jira_user_email = formData.jira_user_email;
      if (formData.jira_api_token) updates.jira_api_token = formData.jira_api_token;

      await apiClient.updateJiraConfig(updates);
      toast.success('JIRA configuration saved successfully');
      await loadJiraConfig(); // Reload to get updated status

      // Clear the password fields for security
      setFormData((prev) => ({
        ...prev,
        jira_user_email: '',
        jira_api_token: '',
      }));
    } catch (error) {
      toast.error(
        'Failed to save JIRA configuration',
        error instanceof Error ? error.message : 'Unknown error'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiClient.logout();
      // apiClient.logout() will clear tokens and redirect to login
    } catch (error) {
      console.error('Logout failed:', error);
      toast.error('Logout failed', error instanceof Error ? error.message : 'Unknown error');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* User Info Section */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-muted-foreground">Account</h3>
            <div className="flex items-center gap-3 p-3 border rounded-lg">
              <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.name || user.email}
                    className="h-10 w-10 rounded-full"
                  />
                ) : (
                  <UserIcon className="h-5 w-5 text-primary" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.name || 'User'}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="ml-auto"
              >
                <LogOut className="h-4 w-4 mr-1" />
                Logout
              </Button>
            </div>
          </div>

          {/* JIRA Configuration Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-muted-foreground">JIRA Integration</h3>
              {jiraConfig && (
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    jiraConfig.configured
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                  }`}
                >
                  {jiraConfig.configured ? 'Configured' : 'Not Configured'}
                </span>
              )}
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="jira-base-url">JIRA Base URL</Label>
                  <Input
                    id="jira-base-url"
                    placeholder="https://your-company.atlassian.net"
                    value={formData.jira_base_url}
                    onChange={(e) =>
                      setFormData({ ...formData, jira_base_url: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="jira-email">JIRA Email</Label>
                  <Input
                    id="jira-email"
                    type="email"
                    placeholder="your-email@company.com"
                    value={formData.jira_user_email}
                    onChange={(e) =>
                      setFormData({ ...formData, jira_user_email: e.target.value })
                    }
                  />
                  {jiraConfig?.has_email && !formData.jira_user_email && (
                    <p className="text-xs text-muted-foreground">
                      Email is configured (hidden for security)
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="jira-token">JIRA API Token</Label>
                  <Input
                    id="jira-token"
                    type="password"
                    placeholder="Your JIRA API token"
                    value={formData.jira_api_token}
                    onChange={(e) =>
                      setFormData({ ...formData, jira_api_token: e.target.value })
                    }
                  />
                  {jiraConfig?.has_token && !formData.jira_api_token && (
                    <p className="text-xs text-muted-foreground">
                      Token is configured (hidden for security)
                    </p>
                  )}
                </div>

                <p className="text-xs text-muted-foreground">
                  Generate an API token at:{' '}
                  <a
                    href="https://id.atlassian.com/manage-profile/security/api-tokens"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    Atlassian API Tokens
                  </a>
                </p>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
