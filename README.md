# Worklog Application

A secure worklog tracking application with Google OAuth authentication, Supabase PostgreSQL storage, and JIRA integration.

## Features

- **Google OAuth Authentication** - Secure sign-in via Supabase Auth
- **Per-User Data Isolation** - Row Level Security (RLS) ensures users only see their own data
- **JIRA Integration** - Log time entries directly to JIRA Cloud
- **Date-Based Organization** - Track work entries by day with start/end times
- **Bulk Operations** - Save multiple entries at once, bulk log to JIRA
- **Azure Deployment Ready** - Includes deployment scripts and GitHub Actions

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn (2 workers)
- **Database**: Supabase PostgreSQL with Row Level Security
- **Authentication**: Supabase Auth with Google OAuth
- **Deployment**: Azure App Service, Azure Container Registry
- **CI/CD**: GitHub Actions

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- A [Supabase](https://supabase.com) account (free tier works)
- (Optional) Azure subscription for deployment

### 1. Clone and Install

```bash
cd worklog
uv sync  # or: pip install -e .
```

### 2. Set Up Supabase

1. Create a new Supabase project at [supabase.com](https://supabase.com)

2. **Configure Google OAuth in Supabase**:
   - Go to **Authentication** > **Providers** > **Google**
   - Enable Google provider
   - Add your Google OAuth credentials (from [Google Cloud Console](https://console.cloud.google.com/))
     1. Go to https://console.cloud.google.com/
     2. Create a new project (or select existing)
     3. Navigate to APIs & Services > Credentials
     4. Click Create Credentials > OAuth client ID
     5. Choose Web application
     6. Add authorized redirect URI: https://your-project.supabase.co/auth/v1/callback (Get this from your Supabase project settings)
     7. Authorized JavaScript Origins: Add the following domains depending on your environment: http://localhost:3000 (your frontend), http://localhost:8000 (your backend API), https://your-project.supabase.co (Supabase), https://your-frontend-domain.com (your production frontend URL), https://your-api-domain.com (if different from frontend)
     8. Set authorized redirect URL: `https://your-project.supabase.co/auth/v1/callback`
     9. Save and copy the Client ID and Client Secret
   - Paste your Google OAuth Client ID and Client Secret to Supabase Google provider settings and save
   - After BE deployment, Settings - API - Configure Site URL field to BE URL (e.g., `https://your-api-domain.azurewebsites.net`)

3. **Initialize Database**:
   - Go to **SQL Editor** in Supabase Dashboard
   - Copy contents of `sql/init.sql`
   - Run the SQL to create tables and RLS policies

4. **Get API Keys**:
   - Go to **Settings** > **API**
   - Copy `URL` and `Publishable API key` (labeled as "Project API keys")

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-publishable-key
FRONTEND_URL=http://localhost:3000
```

### 4. Run Locally

```bash
# Development mode with auto-reload
uv run python -m worklog_app.main

# Or with uvicorn directly
uv run uvicorn worklog_app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

- Health check: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs` (in debug mode)

## Frontend Setup

The frontend is a React application built with Vite, TypeScript, and Tailwind CSS that provides a user-friendly interface for worklog tracking and JIRA integration.

### Prerequisites

- Node.js 18+ and npm
- Backend API running (see above)

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment (Optional)

Create a `.env.local` file if you need to override the API URL:

```env
VITE_API_URL=http://localhost:8000
```

By default, the frontend proxies API requests to `http://localhost:8000` in development.

### 3. Run Development Server

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

### 4. Build for Production

```bash
npm run build
npm run preview  # Preview production build
```

### Features

- **Google OAuth Login** - Secure authentication via backend
- **Worklog Management** - Add, edit, delete time entries with date navigation
- **JIRA Configuration** - User-friendly Settings modal to configure JIRA credentials
- **JIRA Integration** - Log individual or bulk entries to JIRA with visual feedback
- **Prefill Feature** - Load entries from previous same weekday (up to 4 weeks back)
- **Time Tracking** - Automatic duration calculation and daily totals
- **Dark Mode Support** - Follows system preferences
- **Toast Notifications** - Real-time feedback with sound alerts

### Frontend Technology Stack

- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite 7
- **Styling**: Tailwind CSS 3.4
- **UI Components**: shadcn/ui (Radix UI primitives)
- **Icons**: Lucide React
- **Date Handling**: date-fns
- **Notifications**: Sonner

### Usage

1. **Sign In**: Click "Sign in with Google" on the login page
2. **Track Time**: Add worklog entries with issue key, start/end times, and description
3. **Configure JIRA** (Settings):
   - Click the Settings icon in the top-right
   - Enter JIRA Base URL (e.g., `https://company.atlassian.net`)
   - Enter your JIRA email and API token
   - Click "Save Changes"
4. **Log to JIRA**: Click the upload icon on individual entries or "Log All to JIRA"
5. **Navigate Dates**: Use Previous/Next buttons or click "Today"
6. **Prefill**: Use "Prefill from Previous [Weekday]" to copy entries from last week

### CORS Configuration

Ensure your backend is configured to allow requests from the frontend:

```env
# In backend .env
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173,http://localhost:8000
```

The backend automatically configures CORS for the specified origins.

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/google` | Get Google OAuth URL |
| GET | `/api/auth/google/redirect` | Redirect to Google OAuth |
| POST | `/api/auth/callback?code=...` | Exchange code for tokens |
| POST | `/api/auth/refresh?refresh_token=...` | Refresh access token |
| POST | `/api/auth/logout` | Sign out user |
| GET | `/api/auth/me` | Get current user info |

### Worklog Entries

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/worklog/{date}` | Get entries for date |
| PUT | `/api/worklog/{date}` | Save/replace entries for date |
| POST | `/api/worklog/{date}/entries` | Create new entry |
| GET | `/api/worklog/entries/{id}` | Get entry by ID |
| PATCH | `/api/worklog/entries/{id}` | Update entry |
| DELETE | `/api/worklog/entries/{id}` | Delete entry |
| GET | `/api/worklog/range?start_date=...&end_date=...` | Get entries for date range |

### JIRA Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/worklog/jira/config` | Get JIRA config status |
| PUT | `/api/worklog/jira/config` | Update JIRA credentials |
| POST | `/api/worklog/{date}/entries/{id}/log-to-jira` | Log entry to JIRA |
| POST | `/api/worklog/{date}/bulk-log-to-jira` | Bulk log unlogged entries |

### Health & Database

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/status` | API status |
| GET | `/api/db/status` | Database initialization status |
| GET | `/api/db/init-sql` | Get initialization SQL |

## Authentication Flow

```
1. Frontend calls GET /api/auth/google
2. User redirected to Google sign-in
3. Google redirects back to your frontend with code
4. Frontend calls POST /api/auth/callback?code=...
5. Backend returns access_token and refresh_token
6. Frontend includes token in Authorization header: Bearer <token>
```

## Data Model

### WorklogEntry

```json
{
  "id": 1,
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "date": "2024-01-15",
  "issue_key": "PROJ-123",
  "start_time": "09:00",
  "end_time": "11:30",
  "description": "Implemented feature X",
  "logged_to_jira": false,
  "jira_worklog_id": null,
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T09:00:00Z"
}
```

## Azure Deployment

### Prerequisites

- Azure CLI installed and logged in (`az login`)
- Docker installed
- Azure subscription

### Step 1: One-Time Azure Setup (First Deployment Only)

If this is your first time deploying containers to Azure, register the required resource providers:

```bash
# Register Azure Container Registry provider
az provider register --namespace Microsoft.ContainerRegistry

# Register Web App provider
az provider register --namespace Microsoft.Web

# Wait for registration to complete (takes 2-3 minutes)
az provider show --namespace Microsoft.ContainerRegistry --query "registrationState" -o tsv
az provider show --namespace Microsoft.Web --query "registrationState" -o tsv
# Both should show "Registered"
```

### Step 2: Deploy Using Script

```bash
# Set your subscription and verify authentication
az account set --subscription <your-subscription-id>
az account show

# Create all resources and deploy
./scripts/deploy-azure.sh \
  --subscription your-subscription-id \
  --resource-group worklog-rg \
  --app-name <unique-app-name> \
  --location germanywestcentral \
  --create-resources

# Note: App name must be globally unique across all Azure
# If "worklog-app" is taken, try: worklog-yourname, worklog-company, etc.
```

**Important**: If the script fails with "Readme file does not exist" error, the Dockerfile needs README.md. This is already fixed in the repo, but if you encounter it:

```bash
# The Dockerfile should include this line:
# COPY README.md .
```

### Step 3: Manual Deployment Steps (Alternative to Script)

Create webapp with container deployment:

```bash
(az webapp create --name <worklog-app-name> --resource-group worklog-rg --plan worklog-app-plan --deployment-container-image-name worklogappacr.azurecr.io/worklog-app:latest && echo "Webapp created") || echo "Webapp already exists"
```

Build Docker image:

```bash
docker build -t worklogappacr.azurecr.io/worklog-app:latest .
```

Push Docker image to Azure Container Registry:

```bash
docker push worklogappacr.azurecr.io/worklog-app:latest
```

Configure webapp settings (environment variables):

```bash
source .env && az webapp config appsettings set --name <worklog-app-name> --resource-group worklog-rg --settings SUPABASE_URL="$SUPABASE_URL" SUPABASE_PUBLISHABLE_KEY="$SUPABASE_PUBLISHABLE_KEY" FRONTEND_URL="$FRONTEND_URL" APP_NAME="$APP_NAME" APP_ENV="production" CORS_ORIGINS="$CORS_ORIGINS" DEBUG="false" WORKERS="2"
# Check variables were set:
az webapp config appsettings list --name <worklog-app-name> --resource-group worklog-rg --query "[?name=='SUPABASE_URL' || name=='SUPABASE_PUBLISHABLE_KEY' || name=='FRONTEND_URL']"
# Chech port configuration:
az webapp config show --name <worklog-app-name> --resource-group worklog-rg --query "{linuxFxVersion:linuxFxVersion, appCommandLine:appCommandLine}" -o json
```

Enable continuous deployment in Azure:

```bash
az webapp deployment container config --name <worklog-app-name> --resource-group worklog-rg --enable-cd true && echo "Continuous deployment enabled"
```

Restarting webapp:

```bash
az webapp restart --name <worklog-app-name> --resource-group worklog-rg && echo "App restarted"
```

Check logs:

```bash
az webapp log tail --name <worklog-app-name> --resource-group worklog-rg --only-show-errors 2>&1 | head -50 || echo "Not available yet"
```

Check webapp state:

```bash
az webapp show --name <worklog-app-name> --resource-group worklog-rg --query "{state:state, defaultHostName:defaultHostName}"
curl -s -w "\nHTTP Status: %{http_code}\n" https://<worklog-app-name>.azurewebsites.net/health
curl -s -w "\nHTTP Status: %{http_code}\n" https://<worklog-app-name>.azurewebsites.net/api/status
```

### Step 4: Configure Container for Production (Important!)

If the container times out during startup (returns 503), apply these production configurations:

```bash
# Enable container logging to debug issues
az webapp log config --name <worklog-app-name> --resource-group worklog-rg \
  --docker-container-logging filesystem

# Increase container startup timeout (default is 230s, increase to 600s)
az webapp config appsettings set --name <worklog-app-name> --resource-group worklog-rg \
  --settings WEBSITES_CONTAINER_START_TIME_LIMIT="600" \
  -o none

# Configure health check path (tells Azure where to check if app is alive)
az webapp config set --name <worklog-app-name> --resource-group worklog-rg \
  --generic-configurations '{"healthCheckPath": "/health"}'

# Restart to apply all changes
az webapp restart --name <worklog-app-name> --resource-group worklog-rg

# Stream logs to verify startup (wait 30-60 seconds)
az webapp log tail --name <worklog-app-name> --resource-group worklog-rg
```

**Expected successful output in logs:**
```
INFO:     Started server process [X]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
Site started.
```

### Step 5: Verify Deployment

```bash
# Check health endpoint (should return 200 OK)
curl https://<worklog-app-name>.azurewebsites.net/health

# Check API status
curl https://<worklog-app-name>.azurewebsites.net/api/status

# Check Google OAuth URL endpoint
curl https://<worklog-app-name>.azurewebsites.net/api/auth/google
```

### GitHub Actions (Automatic Deployment)

1. **Create Azure Service Principal**:
   ```bash
   az ad sp create-for-rbac --name "worklog-github-actions" \
     --role contributor \
     --scopes /subscriptions/{subscription-id}/resourceGroups/{resource-group} \
     --sdk-auth
   ```

2. **Add GitHub Secrets**:
   - `AZURE_CREDENTIALS` - JSON output from above command
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_RESOURCE_GROUP`
   - `AZURE_APP_NAME`
   - `ACR_LOGIN_SERVER` - e.g., `worklogacr.azurecr.io`
   - `ACR_USERNAME`
   - `ACR_PASSWORD`

3. **Push to master/main** - Deployment runs automatically

### Configure App Settings in Azure

After deployment, set environment variables:

```bash
az webapp config appsettings set \
  --name worklog-app \
  --resource-group worklog-rg \
  --settings \
    SUPABASE_URL='https://your-project.supabase.co' \
    SUPABASE_PUBLISHABLE_KEY='your-publishable-key' \
    FRONTEND_URL='https://your-frontend.com' \
    APP_ENV='production' \
    DEBUG='false'
```

## JIRA Integration Setup

### Via Frontend (Recommended)

1. Sign in to the frontend application
2. Click the Settings icon in the top-right corner
3. Enter your JIRA configuration:
   - **JIRA Base URL**: Your Atlassian instance URL (e.g., `https://your-company.atlassian.net`)
   - **JIRA Email**: Your Atlassian account email
   - **JIRA API Token**: Generate from [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
4. Click "Save Changes"

### Via API

Alternatively, configure JIRA credentials directly via the API:

```bash
curl -X PUT https://your-app.azurewebsites.net/api/worklog/jira/config \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "jira_base_url": "https://your-company.atlassian.net",
    "jira_user_email": "your-email@company.com",
    "jira_api_token": "your-api-token"
  }'
```

## Security Features

- **Row Level Security (RLS)** - Database enforces data isolation per user
- **JWT Token Validation** - All requests validated via Supabase Auth
- **HTTPS Only** - Enforced in production
- **Non-root Container** - Docker runs as unprivileged user
- **No Secrets in Code** - All credentials via environment variables

## Development

### Run Tests

```bash
uv run pytest tests/ -v
```

### Lint Code

```bash
uv run ruff check src/
uv run black src/
```

### Project Structure

```
worklog/
├── src/
│   └── worklog_app/
│       ├── __init__.py
│       ├── main.py          # FastAPI application
│       ├── config.py        # Settings management
│       ├── auth.py          # Authentication module
│       ├── models.py        # Pydantic models
│       ├── storage.py       # Database operations
│       ├── database.py      # DB initialization
│       └── jira_client.py   # JIRA API client
├── frontend/                # React frontend application
│   ├── src/
│   │   ├── components/      # React components
│   │   │   ├── ui/          # shadcn/ui components
│   │   │   ├── Login.tsx    # Google OAuth login
│   │   │   ├── Settings.tsx # JIRA config modal
│   │   │   └── Worklog.tsx  # Main worklog component
│   │   ├── api/
│   │   │   └── client.ts    # API client with auth
│   │   ├── hooks/
│   │   │   └── useToast.ts  # Toast notifications
│   │   ├── lib/
│   │   │   └── utils.ts     # Utilities
│   │   ├── App.tsx          # Main app component
│   │   └── main.tsx         # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── sql/
│   └── init.sql             # Database schema
├── scripts/
│   └── deploy-azure.sh      # Azure deployment
├── .github/
│   └── workflows/
│       └── deploy.yml       # CI/CD pipeline
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

## Troubleshooting

### Database not initialized

Run the SQL script in Supabase Dashboard > SQL Editor:
```sql
-- Copy contents of sql/init.sql and run
```

### Google OAuth not working

1. Check Google Cloud Console OAuth credentials
2. Verify redirect URI matches Supabase callback URL
3. Ensure Google provider is enabled in Supabase

### JIRA logging fails

1. Verify JIRA base URL (e.g., `https://company.atlassian.net`)
2. Check API token is valid
3. Ensure issue keys exist and you have permission to log time

### Container health check fails

1. Check environment variables are set
2. View container logs: `az webapp log tail --name worklog-app --resource-group worklog-rg`
3. Verify Supabase connectivity

## License

MIT License
