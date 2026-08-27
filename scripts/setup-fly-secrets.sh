#!/usr/bin/env bash
# Apply Fly secrets from a local file (never commit secrets.env).
# Usage: cp secrets.env.example secrets.env && edit && ./scripts/setup-fly-secrets.sh
set -euo pipefail
APP="${FLY_APP:-solana-meme-desk}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/secrets.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Copy secrets.env.example → secrets.env and fill in values."
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

ARGS=()
[[ -n "${PUMPPORTAL_API_KEY:-}" ]] && ARGS+=(PUMPPORTAL_API_KEY="$PUMPPORTAL_API_KEY")
[[ -n "${ELEVENLABS_API_KEY:-}" ]] && ARGS+=(ELEVENLABS_API_KEY="$ELEVENLABS_API_KEY")
[[ -n "${OPENAI_API_KEY:-}" ]] && ARGS+=(OPENAI_API_KEY="$OPENAI_API_KEY")
[[ -n "${ALERT_WEBHOOK_URL:-}" ]] && ARGS+=(ALERT_WEBHOOK_URL="$ALERT_WEBHOOK_URL")
[[ -n "${RESEARCH_LLM_ENABLED:-}" ]] && ARGS+=(RESEARCH_LLM_ENABLED="$RESEARCH_LLM_ENABLED")
[[ -n "${SNIPER_RS_ENABLED:-}" ]] && ARGS+=(SNIPER_RS_ENABLED="$SNIPER_RS_ENABLED")

if [[ ${#ARGS[@]} -eq 0 ]]; then
  echo "No secrets to set in $ENV_FILE"
  exit 1
fi

echo "Setting ${#ARGS[@]} secret(s) on $APP..."
~/.fly/bin/flyctl secrets set "${ARGS[@]}" -a "$APP"
echo "Done. Run: flyctl deploy -a $APP"
