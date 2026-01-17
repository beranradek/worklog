import React, { useState, useEffect, useCallback } from 'react';
import { format, subDays, subWeeks, isSameDay } from 'date-fns';
import { Plus, Trash2, ExternalLink, Upload, AlertCircle, Check, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { apiClient, type WorklogEntry, type DayWorklog, type JiraConfig } from '@/api/client';
import { useToast } from '@/hooks/useToast';

const generateId = () => {
  return `wl-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

const calculateDuration = (startTime: string, endTime: string): number => {
  const [startH, startM] = startTime.split(':').map(Number);
  const [endH, endM] = endTime.split(':').map(Number);
  const startMinutes = startH * 60 + startM;
  const endMinutes = endH * 60 + endM;
  return Math.max(0, endMinutes - startMinutes);
};

const formatDuration = (minutes: number): string => {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours === 0) return `${mins}m`;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
};

const formatTimeInput = (value: string): string => {
  // Remove non-digits and colon
  const cleaned = value.replace(/[^\d:]/g, '');

  // Try to parse as HH:MM
  const match = cleaned.match(/^(\d{1,2}):?(\d{0,2})$/);
  if (!match) return value; // Return as-is if doesn't match pattern

  const [, hours, minutes] = match;
  const h = parseInt(hours, 10);
  const m = minutes ? parseInt(minutes, 10) : 0;

  // Validate ranges
  if (h > 23 || m > 59) return value;

  // Format with zero padding
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

export const Worklog: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [worklog, setWorklog] = useState<DayWorklog | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [jiraConfig, setJiraConfig] = useState<JiraConfig | null>(null);
  const [loggingEntryId, setLoggingEntryId] = useState<string | null>(null);
  const [isBulkLogging, setIsBulkLogging] = useState(false);
  const [editingDescriptions, setEditingDescriptions] = useState<Record<string, string>>({});
  const [editingIssueKeys, setEditingIssueKeys] = useState<Record<string, string>>({});
  const [editingTimes, setEditingTimes] = useState<Record<string, { startTime?: string; endTime?: string }>>({});
  const toast = useToast();

  const dateKey = format(selectedDate, 'yyyy-MM-dd');

  // Fetch JIRA configuration
  useEffect(() => {
    const fetchJiraConfig = async () => {
      try {
        const config = await apiClient.getJiraConfig();
        setJiraConfig(config);
      } catch (error) {
        console.error('Failed to fetch JIRA config:', error);
        setJiraConfig({ configured: false, base_url: null, has_token: false, has_email: false });
      }
    };
    fetchJiraConfig();
  }, []);

  // Fetch worklog for selected date
  const fetchWorklog = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.getWorklog(dateKey);
      setWorklog(data);
    } catch (error) {
      console.error('Failed to fetch worklog:', error);
      setWorklog({ date: dateKey, entries: [] });
    } finally {
      setLoading(false);
    }
  }, [dateKey]);

  useEffect(() => {
    fetchWorklog();
  }, [fetchWorklog]);

  // Save worklog
  const saveWorklog = async (entries: WorklogEntry[]) => {
    // Format times and filter out entries without issue keys
    const formattedEntries = entries.map(e => ({
      ...e,
      startTime: formatTimeInput(e.startTime),
      endTime: formatTimeInput(e.endTime),
    }));

    const validEntries = formattedEntries.filter(e => e.issueKey && e.issueKey.trim() !== '');

    // If no valid entries, just update local state without calling API
    if (validEntries.length === 0) {
      setWorklog({ date: dateKey, entries: formattedEntries });
      return;
    }

    setSaving(true);
    try {
      await apiClient.saveWorklog(dateKey, validEntries);

      // Update local state with formatted entries (including unsaved draft ones)
      setWorklog({ date: dateKey, entries: formattedEntries });
    } catch (error) {
      console.error('Failed to save worklog:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to save worklog';
      toast.error('Save Failed', errorMessage);
    } finally {
      setSaving(false);
    }
  };

  // Add new entry
  const addEntry = () => {
    const now = new Date();
    const currentTime = format(now, 'HH:mm');

    // Get last entry's end time if available
    const entries = worklog?.entries || [];
    const lastEntry = entries[entries.length - 1];

    let startTime: string;
    let endTime: string;

    if (lastEntry) {
      // If there's a last entry, start where it ended
      startTime = lastEntry.endTime;
      endTime = currentTime;
    } else {
      // If this is the first entry, default to 1 hour duration ending now
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
      startTime = format(oneHourAgo, 'HH:mm');
      endTime = currentTime;
    }

    const newEntry: WorklogEntry = {
      id: generateId(),
      issueKey: '',
      startTime: startTime,
      endTime: endTime,
      description: '',
      loggedToJira: false,
      jiraWorklogId: null,
    };
    const newEntries = [...entries, newEntry];

    // Update local state only - don't save yet (user needs to fill in issue key)
    // Save will happen when user fills in fields and triggers onBlur
    setWorklog({ date: dateKey, entries: newEntries });
  };

  // Update entry
  const updateEntry = (id: string | number, updates: Partial<WorklogEntry>) => {
    if (!worklog) return;
    const idStr = String(id);
    const entries = worklog.entries.map((entry) =>
      String(entry.id) === idStr ? { ...entry, ...updates } : entry
    );
    saveWorklog(entries);
  };

  // Delete entry
  const deleteEntry = (id: string | number) => {
    if (!worklog) return;
    const idStr = String(id);
    const entryToDelete = worklog.entries.find((entry) => String(entry.id) === idStr);
    const entries = worklog.entries.filter((entry) => String(entry.id) !== idStr);

    // If deleting a draft entry (no issue key), just update local state
    if (entryToDelete && (!entryToDelete.issueKey || entryToDelete.issueKey.trim() === '')) {
      setWorklog({ date: dateKey, entries });
      return;
    }

    // Otherwise, save to backend
    saveWorklog(entries);
  };

  // Log entry to JIRA
  const logToJira = async (entry: WorklogEntry) => {
    if (!entry.issueKey || !entry.startTime || !entry.endTime) {
      toast.error('Validation Error', 'Please fill in issue key and times');
      return;
    }

    if (!jiraConfig?.configured) {
      toast.error('JIRA Not Configured', 'Please configure JIRA in Settings');
      return;
    }

    setLoggingEntryId(String(entry.id));
    try {
      const result = await apiClient.logToJira(dateKey, String(entry.id));
      if (result.success) {
        updateEntry(String(entry.id), {
          loggedToJira: true,
          jiraWorklogId: result.jira_worklog_id || null,
        });
        toast.success('Logged to JIRA', `Worklog added to ${entry.issueKey}`);
      } else {
        toast.error('JIRA Error', result.error || 'Failed to log to JIRA');
      }
    } catch (error) {
      console.error('Failed to log to JIRA:', error);
      toast.error('JIRA Error', 'Failed to connect to JIRA');
    } finally {
      setLoggingEntryId(null);
    }
  };

  // Bulk log all unlogged entries to JIRA
  const bulkLogToJira = async () => {
    if (!jiraConfig?.configured) {
      toast.error('JIRA Not Configured', 'Please configure JIRA in Settings');
      return;
    }

    const unloggedEntries = worklog?.entries.filter(e => !e.loggedToJira && e.issueKey) || [];
    if (unloggedEntries.length === 0) {
      toast.info('No Entries', 'All entries already logged to JIRA');
      return;
    }

    setIsBulkLogging(true);
    try {
      const result = await apiClient.bulkLogToJira(dateKey);

      if (result.total_issues === 0) {
        toast.info('No Entries', 'All entries already logged to JIRA');
      } else if (result.success_count === result.total_issues) {
        // All succeeded
        const totalDuration = result.results.reduce((sum, r) => {
          const match = r.duration.match(/(\d+)h/);
          const hours = match ? parseInt(match[1]) : 0;
          const matchM = r.duration.match(/(\d+)m/);
          const mins = matchM ? parseInt(matchM[1]) : 0;
          return sum + hours * 60 + mins;
        }, 0);
        toast.success('Logged to JIRA', `Logged ${result.success_count} issues (${formatDuration(totalDuration)}) to JIRA`);
      } else if (result.success_count > 0) {
        // Partial success
        toast.warning('Partial Success', `${result.success_count} issues logged, ${result.failure_count} failed`);
      } else {
        // All failed
        const firstError = result.results.find(r => !r.success)?.error || 'Unknown error';
        toast.error('JIRA Error', `Failed to log to JIRA: ${firstError}`);
      }

      // Reload worklog to get updated state
      await fetchWorklog();
    } catch (error) {
      console.error('Failed to bulk log to JIRA:', error);
      toast.error('JIRA Error', 'Failed to connect to JIRA');
    } finally {
      setIsBulkLogging(false);
    }
  };

  // Navigate dates
  const goToPreviousDay = () => {
    setSelectedDate((prev) => subDays(prev, 1));
  };

  const goToNextDay = () => {
    setSelectedDate((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + 1);
      return next;
    });
  };

  const goToToday = () => {
    setSelectedDate(new Date());
  };

  // Prefill from previous same weekday (weekly periodicity)
  // Try up to 4 weeks back for the same weekday, then fall back to previous day
  const prefillFromPrevious = async () => {
    const currentDate = selectedDate;
    const maxWeeksBack = 4;

    try {
      // First, try same weekday from previous weeks (1-4 weeks back)
      for (let weeksBack = 1; weeksBack <= maxWeeksBack; weeksBack++) {
        const sameWeekdayDate = subWeeks(currentDate, weeksBack);
        const dateKey = format(sameWeekdayDate, 'yyyy-MM-dd');
        const data = await apiClient.getWorklog(dateKey);

        if (data && data.entries.length > 0) {
          await mergeEntries(data.entries);
          const weekText = weeksBack === 1 ? 'last week' : `${weeksBack} weeks ago`;
          toast.success('Prefilled', `Loaded from ${format(sameWeekdayDate, 'EEEE')} ${weekText}`);
          return;
        }
      }

      // Fallback: try previous day if no same weekday found
      const previousDayDate = subDays(currentDate, 1);
      const previousDayKey = format(previousDayDate, 'yyyy-MM-dd');
      const previousDayData = await apiClient.getWorklog(previousDayKey);

      if (previousDayData && previousDayData.entries.length > 0) {
        await mergeEntries(previousDayData.entries);
        toast.success('Prefilled', `Loaded from yesterday (${format(previousDayDate, 'EEEE')})`);
        return;
      }

      toast.warning('No Data', 'No entries found in the last 4 weeks or yesterday');
    } catch (error) {
      console.error('Failed to prefill:', error);
      toast.error('Prefill Failed', 'Failed to load previous entries');
    }
  };

  // Merge entries from source (combining descriptions for same issue keys)
  const mergeEntries = async (sourceEntries: WorklogEntry[]) => {
    const existingEntries = worklog?.entries || [];
    const mergedMap = new Map<string, WorklogEntry>();

    // Add existing entries first
    existingEntries.forEach((entry) => {
      if (entry.issueKey) {
        mergedMap.set(entry.issueKey, entry);
      }
    });

    // Merge source entries
    sourceEntries.forEach((entry) => {
      if (!entry.issueKey) return;

      const existing = mergedMap.get(entry.issueKey);
      if (existing) {
        // Merge descriptions with space
        const combinedDesc = [existing.description, entry.description]
          .filter(Boolean)
          .join(' ');
        mergedMap.set(entry.issueKey, {
          ...existing,
          description: combinedDesc,
        });
      } else {
        // Add new entry with new ID, reset logged status
        mergedMap.set(entry.issueKey, {
          ...entry,
          id: generateId(),
          loggedToJira: false,
          jiraWorklogId: null,
        });
      }
    });

    const newEntries = Array.from(mergedMap.values());
    await saveWorklog(newEntries);
  };

  // Calculate total hours
  const totalMinutes = worklog?.entries.reduce((sum, entry) => {
    if (entry.startTime && entry.endTime) {
      return sum + calculateDuration(entry.startTime, entry.endTime);
    }
    return sum;
  }, 0) || 0;

  const isToday = isSameDay(selectedDate, new Date());
  const dayOfWeek = format(selectedDate, 'EEEE');

  return (
    <div className="p-4 space-y-4">
      {/* JIRA Configuration Warning */}
      {jiraConfig && !jiraConfig.configured && (
        <Card className="border-amber-500 bg-amber-50 dark:bg-amber-950/20">
          <CardContent className="pt-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-amber-700 dark:text-amber-400">JIRA Integration Not Configured</p>
                <p className="text-amber-600 dark:text-amber-500 mt-1">
                  Configure JIRA settings to enable worklog synchronization.
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1 text-amber-600 dark:text-amber-500">
                  {!jiraConfig.base_url && <li>JIRA Base URL (e.g., https://company.atlassian.net)</li>}
                  {!jiraConfig.has_email && <li>JIRA User Email (your Atlassian account email)</li>}
                  {!jiraConfig.has_token && <li>JIRA API Token (generate at id.atlassian.com/manage-profile/security/api-tokens)</li>}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Date Navigation */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Worklog</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={goToPreviousDay}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant={isToday ? 'default' : 'outline'}
                size="sm"
                onClick={goToToday}
                className="min-w-[100px]"
              >
                {isToday ? 'Today' : format(selectedDate, 'MMM d')}
              </Button>
              <Button variant="outline" size="sm" onClick={goToNextDay}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{dayOfWeek}, {format(selectedDate, 'MMMM d, yyyy')}</span>
            <span className="font-medium">Total: {formatDuration(totalMinutes)}</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* Entries */}
              {worklog?.entries.map((entry) => {
                const entryIdStr = String(entry.id);
                return (
                <div
                  key={entry.id}
                  className={`
                    flex flex-col gap-2 p-3 rounded-lg border
                    ${entry.loggedToJira
                      ? 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800'
                      : 'bg-card border-border'
                    }
                  `}
                >
                  <div className="flex items-center gap-2">
                    {/* Issue Key */}
                    <Input
                      placeholder="ISSUE-123"
                      value={editingIssueKeys[entryIdStr] ?? entry.issueKey}
                      onChange={(e) => {
                        setEditingIssueKeys(prev => ({
                          ...prev,
                          [entryIdStr]: e.target.value.toUpperCase()
                        }));
                      }}
                      onBlur={(e) => {
                        if (editingIssueKeys[entryIdStr] !== undefined) {
                          updateEntry(entryIdStr, { issueKey: e.target.value.toUpperCase() });
                          setEditingIssueKeys(prev => {
                            const newState = { ...prev };
                            delete newState[entryIdStr];
                            return newState;
                          });
                        }
                      }}
                      className="w-28 font-mono text-sm"
                      disabled={entry.loggedToJira}
                    />

                    {/* Time Range */}
                    <Input
                      type="text"
                      value={editingTimes[entryIdStr]?.startTime ?? entry.startTime}
                      onChange={(e) => {
                        setEditingTimes(prev => ({
                          ...prev,
                          [entryIdStr]: { ...prev[entryIdStr], startTime: e.target.value }
                        }));
                      }}
                      onBlur={(e) => {
                        if (editingTimes[entryIdStr]?.startTime !== undefined) {
                          updateEntry(entryIdStr, { startTime: e.target.value });
                          setEditingTimes(prev => {
                            const newState = { ...prev };
                            if (newState[entryIdStr]) {
                              delete newState[entryIdStr].startTime;
                              if (Object.keys(newState[entryIdStr]).length === 0) {
                                delete newState[entryIdStr];
                              }
                            }
                            return newState;
                          });
                        }
                      }}
                      placeholder="HH:MM"
                      className="w-28"
                      disabled={entry.loggedToJira}
                    />
                    <span className="text-muted-foreground">-</span>
                    <Input
                      type="text"
                      value={editingTimes[entryIdStr]?.endTime ?? entry.endTime}
                      onChange={(e) => {
                        setEditingTimes(prev => ({
                          ...prev,
                          [entryIdStr]: { ...prev[entryIdStr], endTime: e.target.value }
                        }));
                      }}
                      onBlur={(e) => {
                        if (editingTimes[entryIdStr]?.endTime !== undefined) {
                          updateEntry(entryIdStr, { endTime: e.target.value });
                          setEditingTimes(prev => {
                            const newState = { ...prev };
                            if (newState[entryIdStr]) {
                              delete newState[entryIdStr].endTime;
                              if (Object.keys(newState[entryIdStr]).length === 0) {
                                delete newState[entryIdStr];
                              }
                            }
                            return newState;
                          });
                        }
                      }}
                      placeholder="HH:MM"
                      className="w-28"
                      disabled={entry.loggedToJira}
                    />

                    {/* Duration */}
                    <span className="text-sm text-muted-foreground min-w-[50px]">
                      {(() => {
                        const startTime = editingTimes[entryIdStr]?.startTime ?? entry.startTime;
                        const endTime = editingTimes[entryIdStr]?.endTime ?? entry.endTime;
                        return startTime && endTime
                          ? formatDuration(calculateDuration(startTime, endTime))
                          : '-';
                      })()}
                    </span>

                    {/* Actions */}
                    <div className="flex items-center gap-1 ml-auto">
                      {entry.loggedToJira ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <Check className="h-4 w-4" />
                          Logged
                        </span>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => logToJira(entry)}
                          disabled={!entry.issueKey || !jiraConfig?.configured || loggingEntryId === entryIdStr}
                          title={!jiraConfig?.configured ? 'JIRA not configured' : 'Log to JIRA'}
                        >
                          {loggingEntryId === entryIdStr ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Upload className="h-4 w-4" />
                          )}
                        </Button>
                      )}

                      {jiraConfig?.base_url && entry.issueKey && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => window.open(`${jiraConfig.base_url}/browse/${entry.issueKey}`, '_blank')}
                          title="Open in JIRA"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Button>
                      )}

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteEntry(entryIdStr)}
                        className="text-destructive hover:text-destructive"
                        disabled={entry.loggedToJira}
                        title="Delete entry"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* Description */}
                  <Input
                    placeholder="Work description..."
                    value={editingDescriptions[entryIdStr] ?? entry.description}
                    onChange={(e) => {
                      setEditingDescriptions(prev => ({
                        ...prev,
                        [entryIdStr]: e.target.value
                      }));
                    }}
                    onBlur={(e) => {
                      if (editingDescriptions[entryIdStr] !== undefined) {
                        updateEntry(entryIdStr, { description: e.target.value });
                        setEditingDescriptions(prev => {
                          const newState = { ...prev };
                          delete newState[entryIdStr];
                          return newState;
                        });
                      }
                    }}
                    className="text-sm"
                    disabled={entry.loggedToJira}
                  />
                </div>
              );
              })}

              {/* Empty State */}
              {(!worklog?.entries || worklog.entries.length === 0) && (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No work logged for this day</p>
                  <p className="text-sm mt-1">Add an entry to start tracking</p>
                </div>
              )}

              {/* Add Entry Button */}
              <div className="flex gap-2 pt-2">
                <Button onClick={addEntry} variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Entry
                </Button>
                <Button onClick={prefillFromPrevious} variant="ghost" size="sm" title="Load entries from previous same weekday (up to 4 weeks back)">
                  Prefill from Previous {dayOfWeek}
                </Button>
                <Button
                  onClick={bulkLogToJira}
                  variant="default"
                  size="sm"
                  disabled={
                    !jiraConfig?.configured ||
                    isBulkLogging ||
                    !worklog?.entries.some(e => !e.loggedToJira && e.issueKey)
                  }
                  title={
                    !jiraConfig?.configured
                      ? 'JIRA not configured'
                      : !worklog?.entries.some(e => !e.loggedToJira && e.issueKey)
                      ? 'No unlogged entries'
                      : 'Log all unlogged entries to JIRA'
                  }
                >
                  {isBulkLogging ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Logging...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4 mr-2" />
                      Log All to JIRA
                    </>
                  )}
                </Button>
              </div>
            </>
          )}

          {/* Saving indicator */}
          {saving && (
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
