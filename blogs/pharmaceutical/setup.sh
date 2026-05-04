#!/usr/bin/env bash
# =============================================================================
# Open WebUI — Pharma Industry Setup Script
# =============================================================================
# This script creates the required directory structure, generates secrets,
# pulls initial models, and validates the environment before first boot.
#
# Usage: chmod +x setup.sh && ./setup.sh
# =============================================================================

set -euo pipefail

# --- Colors -----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# --- Pre-flight checks ------------------------------------------------------
info "Running pre-flight checks..."

command -v docker >/dev/null 2>&1 || error "Docker is not installed."
command -v docker compose >/dev/null 2>&1 || error "Docker Compose v2 is not installed."

DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null)
info "Docker version: ${DOCKER_VERSION}"

# Check for NVIDIA GPU (optional)
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "GPU detected but nvidia-smi query failed")
    info "GPU detected: ${GPU_INFO}"
else
    warn "No NVIDIA GPU detected. Ollama will run on CPU (slower inference)."
    warn "vLLM requires a GPU and will not start without one."
fi

# --- Create directory structure ---------------------------------------------
info "Creating directory structure..."

mkdir -p nginx/certs
mkdir -p data/ollama
mkdir -p data/postgres
mkdir -p data/redis
mkdir -p data/open-webui
mkdir -p backups

# --- Generate secrets -------------------------------------------------------
info "Generating secrets..."

generate_secret() {
    openssl rand -base64 32 | tr -d '/+=' | head -c 48
}

if [ ! -f .env ]; then
    TERMINAL_KEY=$(generate_secret)
    cat > .env << EOF
# =============================================================================
# Open WebUI — Pharma Industry Environment Configuration
# Generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# =============================================================================

# --- Public URL ---
WEBUI_URL=https://ai.yourcompany.com
WEBUI_NAME=Pharma AI

# --- Secret key (used for JWT signing — KEEP THIS SECRET) ---
WEBUI_SECRET_KEY=$(generate_secret)

# --- Admin account (created on first startup) ---
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=$(generate_secret)
ADMIN_NAME=IT Admin

# --- PostgreSQL ---
POSTGRES_USER=openwebui
POSTGRES_PASSWORD=$(generate_secret)
POSTGRES_DB=openwebui

# --- vLLM ---
VLLM_MODEL=meta-llama/Llama-3.1-70B-Instruct
VLLM_TP_SIZE=2
VLLM_MAX_MODEL_LEN=8192
VLLM_API_KEY=$(generate_secret)
HF_TOKEN=hf_your_token_here

# --- Open Terminal ---
OPEN_TERMINAL_API_KEY=${TERMINAL_KEY}
TERMINAL_SERVER_CONNECTIONS='[{\"url\":\"http://open-terminal:8000\",\"key\":\"${TERMINAL_KEY}\"}]'

# --- Workers ---
UVICORN_WORKERS=4

# --- Observability (optional) ---
ENABLE_OTEL=False
OTEL_ENDPOINT=

# =============================================================================
# IMPORTANT: Update the following before deploying:
#   1. WEBUI_URL — your actual domain
#   2. ADMIN_EMAIL / ADMIN_PASSWORD — your admin credentials
#   3. HF_TOKEN — your Hugging Face token (for gated models like Llama)
#   4. Place TLS certs in ./nginx/certs/ (fullchain.pem + privkey.pem)
# =============================================================================
EOF
    info ".env file created. Review and update it before starting."
    warn "Generated admin password is in .env — save it securely."
else
    warn ".env already exists. Skipping generation."
fi

# --- Pull Ollama models -----------------------------------------------------
info "Pulling recommended Ollama models..."
info "(This may take a while on first run.)"

# Start Ollama temporarily to pull models
if docker compose ps ollama 2>/dev/null | grep -q "running"; then
    info "Ollama is already running."
else
    info "Starting Ollama service to pull models..."
    docker compose up -d ollama
    sleep 10  # Wait for Ollama to initialize
fi

# Pull models (adjust to your organization's needs)
MODELS=(
    "llama3.1:8b"       # Fast — summarization, Q&A, literature triage
    "nomic-embed-text"  # Embedding model for RAG
)

for model in "${MODELS[@]}"; do
    info "Pulling ${model}..."
    docker compose exec ollama ollama pull "${model}" || warn "Failed to pull ${model}. You can pull it later."
done

info "Models pulled. You can add more models later via:"
info "  docker compose exec ollama ollama pull <model-name>"

# --- Validate Docker Compose ------------------------------------------------
info "Validating Docker Compose configuration..."
docker compose config --quiet && info "Docker Compose configuration is valid." || error "Docker Compose validation failed."

# --- Summary ----------------------------------------------------------------
echo ""
echo "============================================================================="
echo "  Setup complete!"
echo "============================================================================="
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your domain, admin credentials, and HF token"
echo "    2. Place TLS certificates in ./nginx/certs/"
echo "       - fullchain.pem (certificate chain)"
echo "       - privkey.pem   (private key)"
echo "    3. Update nginx/nginx.conf server_name to match your domain"
echo "    4. Start the stack:  docker compose up -d"
echo "    5. Access the UI at: https://ai.yourcompany.com"
echo "    6. Install the Inline Visualizer tool & skill (see setup.md Step 5)"
echo ""
echo "  Open Terminal is pre-configured via TERMINAL_SERVER_CONNECTIONS."
echo "  Verify it's connected: Admin Settings → Integrations → Open Terminal"
echo ""
echo "  To check service health:  docker compose ps"
echo "  To view logs:             docker compose logs -f open-webui-1"
echo "  To pull more models:      docker compose exec ollama ollama pull <model>"
echo ""
echo "============================================================================="
