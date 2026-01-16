#!/bin/bash
# =============================================================================
# Azure App Service Deployment Script for Worklog Application
# =============================================================================
# This script deploys the Worklog application to Azure App Service.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Docker installed (for container builds)
#   - Environment variables set or config file present
#
# Usage:
#   ./scripts/deploy-azure.sh [options]
#
# Options:
#   --subscription ID    Azure subscription ID
#   --resource-group RG  Azure resource group name
#   --app-name NAME      Azure App Service name
#   --location LOC       Azure region (default: eastus)
#   --sku SKU            App Service plan SKU (default: B1)
#   --create-resources   Create resource group and app service plan if missing
#   --build-only         Only build Docker image, don't deploy
#   --help               Show this help message
# =============================================================================

set -e  # Exit on error

# Default values
LOCATION="eastus"
SKU="B1"
CREATE_RESOURCES=false
BUILD_ONLY=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_help() {
    head -30 "$0" | tail -25
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --subscription)
            AZURE_SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        --resource-group)
            AZURE_RESOURCE_GROUP="$2"
            shift 2
            ;;
        --app-name)
            AZURE_APP_NAME="$2"
            shift 2
            ;;
        --location)
            LOCATION="$2"
            shift 2
            ;;
        --sku)
            SKU="$2"
            shift 2
            ;;
        --create-resources)
            CREATE_RESOURCES=true
            shift
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# Load from .env if variables not set
if [ -f "$PROJECT_DIR/.env" ]; then
    log_info "Loading configuration from .env"
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Validate required variables
if [ -z "$AZURE_SUBSCRIPTION_ID" ]; then
    log_error "AZURE_SUBSCRIPTION_ID not set. Use --subscription or set in .env"
    exit 1
fi

if [ -z "$AZURE_RESOURCE_GROUP" ]; then
    log_error "AZURE_RESOURCE_GROUP not set. Use --resource-group or set in .env"
    exit 1
fi

if [ -z "$AZURE_APP_NAME" ]; then
    log_error "AZURE_APP_NAME not set. Use --app-name or set in .env"
    exit 1
fi

# Derived variables
APP_SERVICE_PLAN="${AZURE_APP_NAME}-plan"
ACR_NAME="${AZURE_APP_NAME//-/}acr"  # Remove hyphens for ACR name
IMAGE_NAME="$AZURE_APP_NAME"
IMAGE_TAG="latest"

log_info "=== Worklog Azure Deployment ==="
log_info "Subscription: $AZURE_SUBSCRIPTION_ID"
log_info "Resource Group: $AZURE_RESOURCE_GROUP"
log_info "App Name: $AZURE_APP_NAME"
log_info "Location: $LOCATION"
log_info "SKU: $SKU"
echo ""

# Step 1: Verify Azure CLI is logged in
log_info "Checking Azure CLI authentication..."
if ! az account show &>/dev/null; then
    log_error "Not logged into Azure CLI. Please run: az login"
    exit 1
fi

# Set subscription
log_info "Setting Azure subscription..."
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
log_success "Subscription set"

# Step 2: Create resources if requested
if [ "$CREATE_RESOURCES" = true ]; then
    # Create resource group if it doesn't exist
    if ! az group show --name "$AZURE_RESOURCE_GROUP" &>/dev/null; then
        log_info "Creating resource group: $AZURE_RESOURCE_GROUP"
        az group create --name "$AZURE_RESOURCE_GROUP" --location "$LOCATION"
        log_success "Resource group created"
    else
        log_info "Resource group already exists"
    fi

    # Create Azure Container Registry if it doesn't exist
    if ! az acr show --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &>/dev/null; then
        log_info "Creating Azure Container Registry: $ACR_NAME"
        az acr create \
            --name "$ACR_NAME" \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --sku Basic \
            --admin-enabled true
        log_success "Container Registry created"
    else
        log_info "Container Registry already exists"
    fi

    # Create App Service Plan if it doesn't exist
    if ! az appservice plan show --name "$APP_SERVICE_PLAN" --resource-group "$AZURE_RESOURCE_GROUP" &>/dev/null; then
        log_info "Creating App Service Plan: $APP_SERVICE_PLAN"
        az appservice plan create \
            --name "$APP_SERVICE_PLAN" \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --sku "$SKU" \
            --is-linux
        log_success "App Service Plan created"
    else
        log_info "App Service Plan already exists"
    fi

    # Create Web App if it doesn't exist
    if ! az webapp show --name "$AZURE_APP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &>/dev/null; then
        log_info "Creating Web App: $AZURE_APP_NAME"

        # Get ACR login server
        ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query loginServer -o tsv)

        az webapp create \
            --name "$AZURE_APP_NAME" \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --plan "$APP_SERVICE_PLAN" \
            --deployment-container-image-name "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"

        log_success "Web App created"
    else
        log_info "Web App already exists"
    fi
fi

# Step 3: Build Docker image
log_info "Building Docker image..."
cd "$PROJECT_DIR"

# Create Dockerfile if it doesn't exist
if [ ! -f "Dockerfile" ]; then
    log_info "Creating Dockerfile..."
    cat > Dockerfile << 'DOCKERFILE'
# Multi-stage build for Python application
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY sql/ sql/

# Install dependencies
RUN uv pip install --system --no-cache .

# Production image
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app/src /app/src
COPY --from=builder /app/sql /app/sql

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8000
ENV WORKERS=2

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "worklog_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
DOCKERFILE
    log_success "Dockerfile created"
fi

if [ "$BUILD_ONLY" = true ]; then
    # Just build locally
    docker build -t "$IMAGE_NAME:$IMAGE_TAG" .
    log_success "Docker image built locally: $IMAGE_NAME:$IMAGE_TAG"
    exit 0
fi

# Step 4: Build and push to Azure Container Registry
log_info "Building and pushing to Azure Container Registry..."

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query passwords[0].value -o tsv)

# Login to ACR
echo "$ACR_PASSWORD" | docker login "$ACR_LOGIN_SERVER" -u "$ACR_USERNAME" --password-stdin

# Build and tag image
docker build -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG" .
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"

log_success "Image pushed to ACR: $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"

# Step 5: Configure Web App
log_info "Configuring Web App..."

# Set container image
az webapp config container set \
    --name "$AZURE_APP_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --docker-custom-image-name "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG" \
    --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
    --docker-registry-server-user "$ACR_USERNAME" \
    --docker-registry-server-password "$ACR_PASSWORD"

# Configure app settings (environment variables)
log_info "Setting application configuration..."
log_warning "Please configure the following environment variables in Azure Portal or via CLI:"
echo ""
echo "  az webapp config appsettings set \\"
echo "    --name $AZURE_APP_NAME \\"
echo "    --resource-group $AZURE_RESOURCE_GROUP \\"
echo "    --settings \\"
echo "      SUPABASE_URL='your-supabase-url' \\"
echo "      SUPABASE_PUBLISHABLE_KEY='your-publishable-key' \\"
echo "      FRONTEND_URL='https://your-frontend.com' \\"
echo "      APP_ENV='production' \\"
echo "      DEBUG='false'"
echo ""

# Enable continuous deployment
log_info "Enabling continuous deployment..."
az webapp deployment container config \
    --name "$AZURE_APP_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --enable-cd true

# Step 6: Restart app to apply changes
log_info "Restarting Web App..."
az webapp restart --name "$AZURE_APP_NAME" --resource-group "$AZURE_RESOURCE_GROUP"

# Get app URL
APP_URL=$(az webapp show --name "$AZURE_APP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query defaultHostName -o tsv)

log_success "=== Deployment Complete ==="
echo ""
log_info "Application URL: https://$APP_URL"
log_info "Health Check: https://$APP_URL/health"
log_info "API Status: https://$APP_URL/api/status"
echo ""
log_warning "Don't forget to:"
echo "  1. Configure environment variables (SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, etc.)"
echo "  2. Run the SQL initialization script in Supabase"
echo "  3. Configure Google OAuth in Supabase Dashboard"
echo "  4. Update CORS settings with your frontend URL"
