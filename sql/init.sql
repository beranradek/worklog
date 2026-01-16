-- Worklog Application Database Schema
-- This script is idempotent - safe to run multiple times

-- Create worklog_entries table
CREATE TABLE IF NOT EXISTS worklog_entries (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    issue_key VARCHAR(50) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    description TEXT,
    logged_to_jira BOOLEAN DEFAULT FALSE,
    jira_worklog_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for efficient querying by user and date
CREATE INDEX IF NOT EXISTS idx_worklog_entries_user_date
    ON worklog_entries(user_id, date);

-- Create index for querying by date
CREATE INDEX IF NOT EXISTS idx_worklog_entries_date
    ON worklog_entries(date);

-- Create user_jira_config table for per-user JIRA settings
CREATE TABLE IF NOT EXISTS user_jira_config (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    jira_base_url VARCHAR(255),
    jira_user_email VARCHAR(255),
    jira_api_token_encrypted TEXT,  -- Encrypted token
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for user lookup
CREATE INDEX IF NOT EXISTS idx_user_jira_config_user
    ON user_jira_config(user_id);

-- Row Level Security (RLS) Policies
-- Enable RLS on worklog_entries
ALTER TABLE worklog_entries ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own worklog entries
DROP POLICY IF EXISTS "Users can view own worklog entries" ON worklog_entries;
CREATE POLICY "Users can view own worklog entries" ON worklog_entries
    FOR SELECT USING (auth.uid() = user_id);

-- Policy: Users can insert their own worklog entries
DROP POLICY IF EXISTS "Users can insert own worklog entries" ON worklog_entries;
CREATE POLICY "Users can insert own worklog entries" ON worklog_entries
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update their own worklog entries
DROP POLICY IF EXISTS "Users can update own worklog entries" ON worklog_entries;
CREATE POLICY "Users can update own worklog entries" ON worklog_entries
    FOR UPDATE USING (auth.uid() = user_id);

-- Policy: Users can delete their own worklog entries
DROP POLICY IF EXISTS "Users can delete own worklog entries" ON worklog_entries;
CREATE POLICY "Users can delete own worklog entries" ON worklog_entries
    FOR DELETE USING (auth.uid() = user_id);

-- Enable RLS on user_jira_config
ALTER TABLE user_jira_config ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own JIRA config
DROP POLICY IF EXISTS "Users can view own jira config" ON user_jira_config;
CREATE POLICY "Users can view own jira config" ON user_jira_config
    FOR SELECT USING (auth.uid() = user_id);

-- Policy: Users can insert their own JIRA config
DROP POLICY IF EXISTS "Users can insert own jira config" ON user_jira_config;
CREATE POLICY "Users can insert own jira config" ON user_jira_config
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update their own JIRA config
DROP POLICY IF EXISTS "Users can update own jira config" ON user_jira_config;
CREATE POLICY "Users can update own jira config" ON user_jira_config
    FOR UPDATE USING (auth.uid() = user_id);

-- Policy: Users can delete their own JIRA config
DROP POLICY IF EXISTS "Users can delete own jira config" ON user_jira_config;
CREATE POLICY "Users can delete own jira config" ON user_jira_config
    FOR DELETE USING (auth.uid() = user_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for worklog_entries updated_at
DROP TRIGGER IF EXISTS update_worklog_entries_updated_at ON worklog_entries;
CREATE TRIGGER update_worklog_entries_updated_at
    BEFORE UPDATE ON worklog_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for user_jira_config updated_at
DROP TRIGGER IF EXISTS update_user_jira_config_updated_at ON user_jira_config;
CREATE TRIGGER update_user_jira_config_updated_at
    BEFORE UPDATE ON user_jira_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE ON worklog_entries TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_jira_config TO authenticated;
