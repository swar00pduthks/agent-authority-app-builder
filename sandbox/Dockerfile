# Per-project sandbox for Azure Container Apps dynamic sessions (Hyper-V isolated).
# Untrusted by design: no cloud credentials, no Agent Authority ingest key, egress only
# through Azure Firewall FQDN rules. IMDS (169.254.169.254) and WireServer
# (168.63.129.16) are blocked at the network layer, not here.
FROM mcr.microsoft.com/devcontainers/base:bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip nodejs npm git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 builder
USER builder
WORKDIR /workspace

# Generated stack: React + Vite + TypeScript frontend, optional FastAPI backend.
EXPOSE 5173 8000
CMD ["sleep", "infinity"]
