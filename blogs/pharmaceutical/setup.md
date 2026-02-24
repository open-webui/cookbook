# Pharma Industry — Technical Setup Guide

This guide is the engineering companion to [Private AI for the Pharmaceutical Industry with Open WebUI](article.md). It provides everything your engineering or IT team needs to deploy, configure, and operate the production architecture described there.

---

## Table of Contents

1. [Architecture Deep Dive](#architecture-deep-dive)
2. [Pre-Requisites](#pre-requisites)
3. [Docker Compose Reference](#docker-compose-reference)
4. [Setup Script](#setup-script)
5. [Environment Variable Reference](#environment-variable-reference)
6. [RBAC Configuration Guide](#rbac-configuration-guide)
7. [Knowledge Base Setup Guide](#knowledge-base-setup-guide)
8. [Security Hardening Checklist](#security-hardening-checklist)
9. [Backup & Disaster Recovery](#backup--disaster-recovery)

---

## Architecture Deep Dive

This section explains each component in the production stack and why it exists. For the high-level overview and business rationale, see the [blog post](article.md).

### Reverse Proxy + TLS Termination

All traffic enters through a single reverse proxy that enforces TLS encryption in transit. This is your network boundary — nothing reaches Open WebUI without passing through it. For organizations with existing network infrastructure, this integrates with your current certificate management and firewall rules. The proxy also handles load balancing across Open WebUI instances, distributing requests evenly to prevent any single node from becoming a bottleneck.

### Stateless Open WebUI Nodes

Open WebUI instances run as stateless containers. This means you can:

- Scale horizontally — add nodes during peak usage (e.g., submission deadlines, safety signal reviews) and remove them during quieter periods
- Lose any single node without service interruption
- Restart containers without losing data — all persistent state lives in PostgreSQL and Redis

Key environment variables for this deployment pattern:

- `ENABLE_ADMIN_CHAT_ACCESS=False` — Protects confidential scientific discussions and pre-competitive research data from internal IT access
- `ENABLE_SIGNUP=False` — No self-registration; user provisioning is controlled
- `DEFAULT_USER_ROLE=pending` — New accounts require admin approval before accessing any AI capabilities
- `ENABLE_ADMIN_EXPORT=False` — Prevents bulk data extraction

### PostgreSQL + PGVector

PostgreSQL serves dual duty: it stores chat history, user records, and configuration (the audit trail), and with the PGVector extension, it also acts as the vector database for RAG knowledge bases. One database to back up, monitor, and secure rather than two.

For pharma organizations, the audit trail matters most. Every conversation is persisted, timestamped, and associated with a user identity. Combined with the `USER_PERMISSIONS_CHAT_DELETE=False` setting, this creates an electronic record that supports 21 CFR Part 11 and Annex 11 requirements. Connection pooling and proper indexing ensure performance holds at enterprise scale.

### Redis

Redis handles session management and WebSocket coordination across stateless nodes. When a scientist starts a conversation on one Open WebUI instance and their next request routes to a separate instance, Redis ensures the session is seamless. Without it, multi-node deployments cannot function. Redis Sentinel or Cluster mode is recommended for production HA.

### Shared Document Storage

Uploaded documents — SOPs, study reports, regulatory submissions, literature PDFs — need to be accessible from any Open WebUI instance. An S3-compatible object store (MinIO for on-prem, or your cloud provider's offering) or NFS mount provides this shared layer. Open WebUI's file management dashboard provides a centralized interface to search, view, and manage them.

### Ollama — Local Model Inference

Ollama runs models directly on your infrastructure. This is the core of the data sovereignty promise: prompts, completions, and any intermediate representations never leave your network. Ollama supports GPU passthrough via NVIDIA Container Toolkit, and Open WebUI can load-balance across multiple Ollama instances for concurrent users.

### vLLM — GPU-Optimized Inference

For organizations needing maximum throughput from large models (70B+ parameters), vLLM provides optimized GPU inference with continuous batching and PagedAttention. It exposes an OpenAI-compatible API, so Open WebUI connects to it just like any other API endpoint.

vLLM is the right choice when:

- Dozens of scientists are running concurrent queries
- You're serving 70B+ parameter models that need tensor parallelism across multiple GPUs
- You need deterministic throughput guarantees for SLA-sensitive workflows

Both Ollama and vLLM can run side-by-side. A common pattern is to use Ollama to serve smaller models for quick tasks (summarization, Q&A, literature triage), while using vLLM to handle the large reasoning models for complex scientific analysis.

### Functions (Optional)

Open WebUI's built-in [Functions](https://docs.openwebui.com/features/plugin/functions/) plugin system enables custom processing logic without external services. Pharma-relevant functions include:

- **Rate limiting**: Prevent runaway local LLM usage during bulk document processing
- **Toxic message filtering**: Content safety guardrails
- **LLM-Guard prompt injection scanning**: Protect against adversarial inputs that might attempt to extract proprietary data
- **Langfuse monitoring**: Detailed usage analytics per user, model, and functional group
- **Custom RAG functions**: Organization-specific retrieval logic, e.g., prioritizing recent publications or FDA guidance over older sources

### OpenTelemetry (Optional)

Built-in OpenTelemetry support exports traces, metrics, and logs to your existing observability stack (Prometheus, Grafana, Jaeger, Splunk, Datadog). For organizations subject to GxP audit, this provides infrastructure-level evidence that AI systems are operating within policy.

---

## Pre-Requisites

### Hardware Requirements

For an organization with 500–10,000+ employees and concurrent usage of ~100–500 users:

| Component | Minimum | Recommended |
|---|---|---|
| **Open WebUI nodes** | 2× (4 vCPU, 8 GB RAM each) | 3× (8 vCPU, 16 GB RAM each) |
| **PostgreSQL** | 4 vCPU, 16 GB RAM, 500 GB SSD | 8 vCPU, 32 GB RAM, 1 TB NVMe |
| **Redis** | 2 vCPU, 4 GB RAM | 2 vCPU, 8 GB RAM (Sentinel: 3 nodes) |
| **Ollama (small models, ≤13B)** | 1× NVIDIA GPU (24 GB VRAM, e.g., RTX 4090) | 2× GPUs behind load balancer |
| **vLLM (large models, 70B+)** | 2× NVIDIA A100 80 GB (tensor parallel) | 4× A100 80 GB or 2× H100 |
| **Shared storage** | 1 TB S3-compatible or NFS | 5 TB+ with lifecycle policies |

### Software Requirements

- **Docker Engine** ≥ 24.0 and **Docker Compose** ≥ 2.20
- **NVIDIA Container Toolkit** (for GPU nodes) — [installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- **TLS certificates** — from your organization's internal CA or Let's Encrypt
- **LDAP / SSO credentials** — for OAuth/OIDC integration (Okta, Azure AD, Ping Identity, etc.)
- **DNS entry** — e.g., `ai.yourcompany.com` pointing to the reverse proxy

### Network Requirements

- All services communicate on an internal Docker network — no public exposure except the reverse proxy
- Outbound internet access is **not required** if models are pre-pulled (fully air-gappable)
- Ports: only `443` (HTTPS) exposed externally

---

## Docker Compose Reference

Save this as `docker-compose.yml` in your deployment directory. An accompanying `.env` file is generated by the [setup script](#setup-script) below.

```yaml
# =============================================================================
# Open WebUI — Pharma Industry Production Stack
# =============================================================================
# Usage:
#   1. Run ./setup.sh to generate .env and required directories
#   2. docker compose up -d
#   3. Access via https://ai.yourcompany.com
# =============================================================================

services:
  # ---------------------------------------------------------------------------
  # Reverse Proxy — TLS termination and load balancing
  # ---------------------------------------------------------------------------
  nginx:
    image: nginx:alpine
    container_name: owui-proxy
    restart: unless-stopped
    ports:
      - "443:443"
      - "80:80"       # Redirect to HTTPS
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      open-webui-1:
        condition: service_healthy
    networks:
      - owui-net

  # ---------------------------------------------------------------------------
  # Open WebUI — Stateless application nodes
  # ---------------------------------------------------------------------------
  open-webui-1:
    image: ghcr.io/open-webui/open-webui:main
    container_name: owui-node-1
    restart: unless-stopped
    environment:
      # --- Core ---
      - WEBUI_URL=${WEBUI_URL}
      - WEBUI_NAME=${WEBUI_NAME:-Pharma AI}
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
      - PORT=8080

      # --- Database ---
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}

      # --- Vector DB (PGVector, same PostgreSQL instance) ---
      - VECTOR_DB=pgvector
      - PGVECTOR_DB_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}

      # --- Redis ---
      - REDIS_URL=redis://redis:6379/0
      - WEBSOCKET_MANAGER=redis
      - WEBSOCKET_REDIS_URL=redis://redis:6379/0
      - ENABLE_WEBSOCKET_SUPPORT=True

      # --- Inference backends ---
      - OLLAMA_BASE_URL=http://ollama:11434
      - ENABLE_OLLAMA_API=True
      - OPENAI_API_BASE_URL=http://vllm:8000/v1
      - OPENAI_API_KEY=${VLLM_API_KEY:-sk-none}
      - ENABLE_OPENAI_API=True

      # --- Pharma-specific security defaults ---
      - ENABLE_SIGNUP=False
      - DEFAULT_USER_ROLE=pending
      - ENABLE_ADMIN_CHAT_ACCESS=False
      - ENABLE_ADMIN_EXPORT=False
      - BYPASS_MODEL_ACCESS_CONTROL=False
      - BYPASS_ADMIN_ACCESS_CONTROL=False
      - ENABLE_COMMUNITY_SHARING=False

      # --- User permissions ---
      - USER_PERMISSIONS_CHAT_DELETE=False
      - USER_PERMISSIONS_CHAT_TEMPORARY=False

      # --- RAG tuning ---
      - RAG_TOP_K=5
      - RAG_SYSTEM_CONTEXT=True
      - ENABLE_RAG_HYBRID_SEARCH=True

      # --- Admin provisioning (first startup only) ---
      - WEBUI_ADMIN_EMAIL=${ADMIN_EMAIL}
      - WEBUI_ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - WEBUI_ADMIN_NAME=${ADMIN_NAME:-IT Admin}

      # --- Workers ---
      - UVICORN_WORKERS=${UVICORN_WORKERS:-4}
      - ENABLE_DB_MIGRATIONS=True  # Only on node-1; set False on others

      # --- Observability (optional) ---
      - ENABLE_OTEL=${ENABLE_OTEL:-False}
      - OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_ENDPOINT:-}

      # --- Persistent config ---
      - ENABLE_PERSISTENT_CONFIG=True
    volumes:
      - owui-data:/app/backend/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - owui-net

  # Note: open-webui-2 duplicates the environment from open-webui-1 because
  # Docker Compose list-style environment blocks do not support YAML merge keys.
  # If you add or change a variable above, update it here as well.
  open-webui-2:
    image: ghcr.io/open-webui/open-webui:main
    container_name: owui-node-2
    restart: unless-stopped
    environment:
      - WEBUI_URL=${WEBUI_URL}
      - WEBUI_NAME=${WEBUI_NAME:-Pharma AI}
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
      - PORT=8080
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - VECTOR_DB=pgvector
      - PGVECTOR_DB_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - WEBSOCKET_MANAGER=redis
      - WEBSOCKET_REDIS_URL=redis://redis:6379/0
      - ENABLE_WEBSOCKET_SUPPORT=True
      - OLLAMA_BASE_URL=http://ollama:11434
      - ENABLE_OLLAMA_API=True
      - OPENAI_API_BASE_URL=http://vllm:8000/v1
      - OPENAI_API_KEY=${VLLM_API_KEY:-sk-none}
      - ENABLE_OPENAI_API=True
      - ENABLE_SIGNUP=False
      - DEFAULT_USER_ROLE=pending
      - ENABLE_ADMIN_CHAT_ACCESS=False
      - ENABLE_ADMIN_EXPORT=False
      - BYPASS_MODEL_ACCESS_CONTROL=False
      - BYPASS_ADMIN_ACCESS_CONTROL=False
      - ENABLE_COMMUNITY_SHARING=False
      - USER_PERMISSIONS_CHAT_DELETE=False
      - USER_PERMISSIONS_CHAT_TEMPORARY=False
      - RAG_TOP_K=5
      - RAG_SYSTEM_CONTEXT=True
      - ENABLE_RAG_HYBRID_SEARCH=True
      - WEBUI_ADMIN_EMAIL=${ADMIN_EMAIL}
      - WEBUI_ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - WEBUI_ADMIN_NAME=${ADMIN_NAME:-IT Admin}
      - UVICORN_WORKERS=${UVICORN_WORKERS:-4}
      - ENABLE_DB_MIGRATIONS=False  # Node-1 handles migrations
      - ENABLE_OTEL=${ENABLE_OTEL:-False}
      - OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_ENDPOINT:-}
      - ENABLE_PERSISTENT_CONFIG=True
    volumes:
      - owui-data:/app/backend/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - owui-net

  # ---------------------------------------------------------------------------
  # PostgreSQL 16 + PGVector — Database and vector store
  # ---------------------------------------------------------------------------
  postgres:
    image: pgvector/pgvector:pg16
    container_name: owui-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - owui-net
    # Recommended: tune postgresql.conf for your hardware
    command: >
      postgres
        -c shared_buffers=2GB
        -c effective_cache_size=6GB
        -c work_mem=64MB
        -c maintenance_work_mem=512MB
        -c max_connections=200
        -c wal_level=replica
        -c max_wal_senders=3

  # ---------------------------------------------------------------------------
  # Redis — Session management and WebSocket coordination
  # ---------------------------------------------------------------------------
  redis:
    image: redis:7-alpine
    container_name: owui-redis
    restart: unless-stopped
    command: >
      redis-server
        --maxmemory 2gb
        --maxmemory-policy allkeys-lru
        --maxclients 10000
        --timeout 1800
        --save 60 1000
        --appendonly yes
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - owui-net

  # ---------------------------------------------------------------------------
  # Ollama — Local model inference (smaller models, ≤13B)
  # ---------------------------------------------------------------------------
  ollama:
    image: ollama/ollama:latest
    container_name: owui-ollama
    restart: unless-stopped
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    networks:
      - owui-net

  # ---------------------------------------------------------------------------
  # vLLM — GPU-optimized inference (large models, 70B+)
  # ---------------------------------------------------------------------------
  vllm:
    image: vllm/vllm-openai:latest
    container_name: owui-vllm
    restart: unless-stopped
    command: >
      --model ${VLLM_MODEL:-meta-llama/Llama-3.1-70B-Instruct}
      --tensor-parallel-size ${VLLM_TP_SIZE:-2}
      --max-model-len ${VLLM_MAX_MODEL_LEN:-8192}
      --gpu-memory-utilization 0.90
      --enforce-eager
      --api-key ${VLLM_API_KEY:-sk-none}
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: ${VLLM_TP_SIZE:-2}
              capabilities: [gpu]
    networks:
      - owui-net

# =============================================================================
# Named Volumes
# =============================================================================
volumes:
  owui-data:
    driver: local
  postgres-data:
    driver: local
  redis-data:
    driver: local
  ollama-data:
    driver: local

# =============================================================================
# Network
# =============================================================================
networks:
  owui-net:
    driver: bridge
```

### Nginx Configuration

Save this as `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream openwebui {
        least_conn;
        server open-webui-1:8080;
        server open-webui-2:8080;
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name ai.yourcompany.com;

        ssl_certificate     /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Max upload size for document ingestion
        client_max_body_size 100M;

        location / {
            proxy_pass http://openwebui;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket support (required for streaming responses)
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            # Timeouts for long-running LLM responses
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }
    }
}
```

---

## Setup Script

Save this as `setup.sh` and run it before your first `docker compose up`:

```bash
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
echo ""
echo "  To check service health:  docker compose ps"
echo "  To view logs:             docker compose logs -f open-webui-1"
echo "  To pull more models:      docker compose exec ollama ollama pull <model>"
echo ""
echo "============================================================================="
```

---

## Environment Variable Reference

The Docker Compose file above includes the most important variables for a pharma deployment. This section explains the pharma-specific rationale for each configuration choice.

### Security & Access Control

| Variable | Value | Why |
|---|---|---|
| `ENABLE_SIGNUP` | `False` | Prevents unauthorized accounts. All users are provisioned by an admin or synced via SSO. |
| `DEFAULT_USER_ROLE` | `pending` | New SSO users land in a "pending" state until an admin explicitly approves them. |
| `ENABLE_ADMIN_CHAT_ACCESS` | `False` | **Critical for data protection.** Prevents IT administrators from accessing confidential scientific discussions, pre-competitive research, or proprietary compound data. |
| `ENABLE_ADMIN_EXPORT` | `False` | Prevents bulk database exports that could expose proprietary data. |
| `BYPASS_MODEL_ACCESS_CONTROL` | `False` | Ensures RBAC model restrictions are enforced — users only see models assigned to their group. |
| `BYPASS_ADMIN_ACCESS_CONTROL` | `False` | Admins are subject to the same workspace access rules as regular users. |
| `ENABLE_COMMUNITY_SHARING` | `False` | Disables sharing prompts/models to the Open WebUI Community hub. |
| `USER_PERMISSIONS_CHAT_DELETE` | `False` | **Audit compliance.** Users cannot delete chat history, preserving the full electronic record for 21 CFR Part 11. |
| `USER_PERMISSIONS_CHAT_TEMPORARY` | `False` | Prevents users from creating temporary (unlogged) chats that would bypass the audit trail. |

### RAG Configuration

| Variable | Value | Why |
|---|---|---|
| `VECTOR_DB` | `pgvector` | Uses PostgreSQL's PGVector extension. Officially maintained by Open WebUI. Safe for multi-replica. |
| `RAG_TOP_K` | `5` | Returns the top 5 most relevant document chunks. Increase for broader recall, decrease for precision. |
| `RAG_SYSTEM_CONTEXT` | `True` | Places RAG context in the system message for better KV prefix caching performance with Ollama/vLLM. |
| `ENABLE_RAG_HYBRID_SEARCH` | `True` | Enables BM25 + vector ensemble search with reranking for higher retrieval quality. |

### Multi-Node Infrastructure

| Variable | Value | Why |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | **Required** for multi-node. SQLite cannot handle concurrent writes from multiple instances. |
| `REDIS_URL` | `redis://redis:6379/0` | Required for session coordination across stateless Open WebUI nodes. |
| `WEBSOCKET_MANAGER` | `redis` | Routes WebSocket events through Redis so streaming responses work across all nodes. |
| `ENABLE_WEBSOCKET_SUPPORT` | `True` | Enables real-time streaming responses via WebSocket. |
| `UVICORN_WORKERS` | `4` | Number of worker processes per container. Tune based on CPU cores available. |
| `ENABLE_DB_MIGRATIONS` | `True` (node-1 only) | Only one node should run database migrations on startup to prevent race conditions. |

### Redis Configuration Notes

The Redis `command` in the Docker Compose file includes critical settings:

```
maxclients 10000    # Default is often 1000 — too low for production
timeout 1800        # Close idle connections after 30 minutes
save 60 1000        # Snapshot every 60s if 1000+ keys changed
appendonly yes      # AOF persistence for durability
```

**Without `timeout 1800`**, idle Redis connections accumulate indefinitely. Over days or weeks, you will hit `maxclients` and all logins will fail with `500 Internal Server Error`. This is a documented failure mode — see the [Open WebUI Redis documentation](https://docs.openwebui.com/reference/env-configuration/#redis_url).

---

## RBAC Configuration Guide

After first deployment, configure functional groups via the Admin Panel. This section provides the step-by-step workflow.

### Step 1: Configure OAuth / SSO

Navigate to **Admin Panel → Settings → OAuth** and configure your identity provider:

<!-- TODO: Replace with screenshot of Admin Panel → Settings → OAuth page -->
![OAuth configuration settings](images/oauth_settings.png)

```
OPENID_PROVIDER_URL=https://login.yourcompany.com/.well-known/openid-configuration
OAUTH_CLIENT_ID=<your-client-id>
OAUTH_CLIENT_SECRET=<your-client-secret>
OAUTH_SCOPES=openid email profile groups
OAUTH_GROUP_CLAIM=groups
ENABLE_OAUTH_GROUP_MANAGEMENT=True
ENABLE_OAUTH_GROUP_CREATION=True
ENABLE_OAUTH_ROLE_MANAGEMENT=True
```

> **Tip:** Set `ENABLE_OAUTH_GROUP_MANAGEMENT=True` so that functional group membership syncs automatically from your identity provider. When a scientist moves from R&D to Medical Affairs in your directory, their Open WebUI permissions update on next login.

### Step 2: Create Functional Groups

Navigate to **Admin Panel → Groups** and create groups matching your organization's structure:

<!-- TODO: Replace with screenshot of Admin Panel → Groups page -->
![Groups management page](images/groups_creation.png)

1. **R&D / Discovery**
   - Models: All available models
   - Knowledge bases: Compound libraries, assay protocols, literature databases
   - Permissions: Code interpreter enabled, file upload enabled, web search enabled

2. **Clinical Operations**
   - Models: All available models
   - Knowledge bases: Study protocols, CRF templates, monitoring plans
   - Permissions: File upload enabled, web search enabled

3. **Regulatory Affairs**
   - Models: All available models
   - Knowledge bases: Guidance documents, submission templates, precedent filings
   - Permissions: Document extraction enabled, file upload enabled

4. **Pharmacovigilance**
   - Models: Reasoning models only (e.g., Llama 3.1 70B via vLLM)
   - Knowledge bases: MedDRA dictionaries, CIOMS forms, signal detection SOPs
   - Permissions: RAG-only mode (no web search, no file upload)

5. **Manufacturing / CMC**
   - Models: All available models
   - Knowledge bases: Batch records, process validation reports, equipment SOPs
   - Permissions: File upload enabled

6. **Medical Affairs**
   - Models: All available models
   - Knowledge bases: Product monographs, congress abstracts, KOL presentations
   - Permissions: Web search enabled, file upload enabled

7. **Support Staff**
   - Models: Small models only (e.g., Llama 3.1 8B, Mistral 7B via Ollama)
   - Knowledge bases: Company policies, HR procedures, training materials
   - Permissions: No file upload, no web search

### Step 3: Assign Models to Groups

For each model in **Admin Panel → Models**:

<!-- TODO: Replace with screenshot of model edit page showing access control -->
![Model access control settings](images/model_access.png)

1. Set visibility to **Private** (not Public)
2. Under **Access Control**, add the groups that should have access
3. Ensure `BYPASS_MODEL_ACCESS_CONTROL=False` in your environment so these restrictions are enforced

### Step 4: Assign Knowledge Bases to Groups

For each knowledge base in **Admin Panel → Knowledge**:

<!-- TODO: Replace with screenshot of knowledge base access control -->
![Knowledge base access control](images/knowledge_access.png)

1. Set access control to the relevant functional groups
2. Users will only see knowledge bases assigned to their group(s) in the chat interface

---

## Knowledge Base Setup Guide

Open WebUI's RAG system ingests documents and creates searchable vector embeddings in PGVector. This section walks through configuring knowledge bases for a pharmaceutical organization.

### Recommended Knowledge Base Structure

| Knowledge Base | Contents | Functional Groups |
|---|---|---|
| `Compound Library` | Structures, SAR data, screening results, mechanism-of-action summaries | R&D / Discovery |
| `Assay Protocols` | Standard assay procedures, validation data, reference compound data | R&D / Discovery |
| `Clinical Protocols` | Study protocols, ICH guidelines, statistical analysis plans | Clinical Operations |
| `CRF Templates` | Case report forms, data management plans, reconciliation guides | Clinical Operations |
| `Regulatory Guidance` | FDA guidance documents, EMA guideline library, ICH harmonized guidelines | Regulatory Affairs |
| `Submission Templates` | eCTD module templates, cover letters, precedent review correspondence | Regulatory Affairs |
| `PV Reference` | MedDRA hierarchy, CIOMS forms, signal detection SOPs, PSUR templates | Pharmacovigilance |
| `Manufacturing SOPs` | Batch records, process validation reports, equipment qualification docs | Manufacturing / CMC |
| `Medical Information` | Product monographs, SmPCs, congress posters, medical response letters | Medical Affairs |
| `Company Policies` | HR handbook, compliance policies, IT security procedures, training guides | All groups |

### Upload Workflow

1. Navigate to **Workspace → Knowledge → Create Knowledge Base**

<!-- TODO: Replace with screenshot of knowledge base creation and upload workflow -->
![Knowledge base upload workflow](images/kb_upload.png)
2. Name the knowledge base and set the access control to the relevant functional group(s)
3. Upload documents (supported formats: PDF, DOCX, TXT, Markdown, HTML, CSV, XLSX, PPTX)
4. Open WebUI automatically:
   - Extracts text from uploaded documents
   - Chunks the content for optimal retrieval
   - Generates vector embeddings and stores them in PGVector
5. Users in the assigned groups can now reference this knowledge base in chat by typing `#` followed by the knowledge base name

### RAG Best Practices for Pharma Documents

- **Chunk size**: The default works well for most documents. For very long regulatory submissions or study reports, consider uploading individual sections (e.g., individual CTD modules) as separate documents for more precise retrieval.
- **Citation verification**: RAG provides relevance scores with each retrieved chunk. Train scientists to check citations against the source — RAG reduces hallucination but does not eliminate it.
- **Version control**: When guidance documents update or SOPs are revised, upload the new version and remove the old one. Knowledge bases can be updated without downtime.
- **Document naming**: Use descriptive filenames (e.g., `FDA-Guidance-ICH-E6R3-GCP-2024.pdf` instead of `doc1.pdf`). Open WebUI displays filenames in citation references.

### Embedding Model Selection

The Docker Compose stack pulls `nomic-embed-text` via Ollama for generating embeddings locally. Configure this in **Admin Panel → Settings → Documents → Embedding Model**.

For higher-quality embeddings (recommended for 10,000+ document deployments), consider using a dedicated embedding endpoint. Set `RAG_OPENAI_API_BASE_URL` to point to a self-hosted embedding service or use Ollama's built-in embedding support (no data leaves your network either way).

---

## Security Hardening Checklist

Use this checklist before going to production. Each item maps to a specific regulatory or compliance requirement.

### Network Layer

- [ ] TLS 1.2+ enforced on the reverse proxy — no plaintext HTTP traffic reaches Open WebUI
- [ ] Only port 443 is exposed to the user network; all other services are on internal Docker network
- [ ] HSTS header set with `max-age=63072000; includeSubDomains`
- [ ] Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] Rate limiting configured on the reverse proxy to prevent abuse
- [ ] DNS resolves only to the reverse proxy — no direct access to application nodes

### Authentication & Authorization

- [ ] `ENABLE_SIGNUP=False` — no self-registration
- [ ] `DEFAULT_USER_ROLE=pending` — new SSO users require admin approval
- [ ] SSO/OIDC configured with your organization's identity provider
- [ ] `ENABLE_OAUTH_GROUP_MANAGEMENT=True` — groups sync from IdP
- [ ] `ENABLE_OAUTH_ROLE_MANAGEMENT=True` — roles sync from IdP
- [ ] `BYPASS_MODEL_ACCESS_CONTROL=False` — RBAC enforced on model access
- [ ] `BYPASS_ADMIN_ACCESS_CONTROL=False` — admins subject to workspace ACLs

### Data Protection

- [ ] `ENABLE_ADMIN_CHAT_ACCESS=False` — **proprietary data and trade secret protection**
- [ ] `ENABLE_ADMIN_EXPORT=False` — prevents bulk data extraction
- [ ] `USER_PERMISSIONS_CHAT_DELETE=False` — immutable audit trail (21 CFR Part 11)
- [ ] `USER_PERMISSIONS_CHAT_TEMPORARY=False` — no unlogged conversations
- [ ] `ENABLE_COMMUNITY_SHARING=False` — no external data sharing
- [ ] PostgreSQL configured with encryption at rest (transparent data encryption or full-disk encryption on the host)
- [ ] Redis `requirepass` set if Redis is network-accessible (not needed when Redis is internal-only via Docker network)
- [ ] Backup encryption enabled (see [Backup & Disaster Recovery](#backup--disaster-recovery))

### Model & Inference Security

- [ ] All models run locally via Ollama or vLLM — no external API calls for inference
- [ ] Hugging Face token is stored only in `.env`, not committed to version control
- [ ] `.env` file has restrictive permissions: `chmod 600 .env`
- [ ] vLLM API key (`VLLM_API_KEY`) is set to prevent unauthorized direct access to the inference endpoint
- [ ] If Functions are used: LLM-Guard or equivalent function installed for prompt injection scanning

### Operational Security

- [ ] `ENABLE_DB_MIGRATIONS=True` on exactly one node; `False` on all others
- [ ] Redis `maxclients` set to 10000+ and `timeout` set to 1800 (see [Redis Configuration Notes](#redis-configuration-notes))
- [ ] Log aggregation configured (OpenTelemetry, Splunk, Datadog, or equivalent)
- [ ] Alerting on container restarts, database connection failures, and GPU memory exhaustion
- [ ] Docker image tags pinned to specific versions in production (not `:main` or `:latest`)
- [ ] Regular security updates for base images (`docker compose pull && docker compose up -d`)

---

## Backup & Disaster Recovery

### What to Back Up

| Component | Data Location | Backup Method |
|---|---|---|
| **PostgreSQL** | `postgres-data` volume | `pg_dump` (logical) or continuous WAL archiving |
| **Redis** | `redis-data` volume | AOF + RDB snapshots (handled by Redis config) |
| **Ollama models** | `ollama-data` volume | Volume snapshot or re-pull (models are public) |
| **Open WebUI data** | `owui-data` volume | Volume snapshot |
| **Configuration** | `.env`, `nginx/`, `docker-compose.yml` | Git repository (exclude secrets) |
| **TLS certificates** | `nginx/certs/` | Certificate management system |

### Automated PostgreSQL Backup Script

Add this to your crontab (`crontab -e`) or scheduling system:

```bash
#!/usr/bin/env bash
# Daily PostgreSQL backup — run via cron at 02:00 UTC
# 0 2 * * * /opt/openwebui/backup-postgres.sh

set -euo pipefail

BACKUP_DIR="/opt/openwebui/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/openwebui_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

docker compose exec -T postgres pg_dump \
    -U "${POSTGRES_USER:-openwebui}" \
    -d "${POSTGRES_DB:-openwebui}" \
    --format=custom \
    --compress=9 \
    > "${BACKUP_FILE}"

# Verify backup integrity (pg_restore runs on the host against the host-side file)
pg_restore --list "${BACKUP_FILE}" > /dev/null 2>&1 \
    && echo "[OK] Backup verified: ${BACKUP_FILE}" \
    || echo "[ERROR] Backup verification failed: ${BACKUP_FILE}"

# Prune old backups
find "${BACKUP_DIR}" -name "openwebui_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

echo "[INFO] Backup complete. Size: $(du -h "${BACKUP_FILE}" | cut -f1)"
```

### Recovery Procedure

1. **Stop Open WebUI nodes**: `docker compose stop open-webui-1 open-webui-2`
2. **Restore PostgreSQL**: `docker compose exec -T postgres pg_restore -U openwebui -d openwebui --clean < backup.sql.gz`
3. **Restart**: `docker compose up -d`
4. **Verify**: Check health endpoints and run a test query

### RPO / RTO Targets

| Scenario | RPO (Data Loss) | RTO (Downtime) |
|---|---|---|
| Single node failure | 0 (stateless, auto-recovered) | < 30 seconds (health check interval) |
| Database corruption | ≤ 24 hours (daily backups) | < 1 hour |
| Full infrastructure loss | ≤ 24 hours | 2–4 hours (restore from backups) |
| With WAL archiving | ≤ 5 minutes | < 1 hour |

For mission-critical deployments, enable PostgreSQL WAL archiving for point-in-time recovery with an RPO of minutes rather than hours.

---

*This guide is maintained alongside the [Private AI for the Pharmaceutical Industry with Open WebUI](article.md) blog post. For questions about enterprise deployment, contact [sales@openwebui.com](mailto:sales@openwebui.com).*
