#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-smoke}" # smoke | strict
BASE_URL="${BASE_URL:-http://localhost:8000}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
EMAIL="${E2E_EMAIL:-e2e_$(date +%s)@example.com}"
PASSWORD="${E2E_PASSWORD:-StrongPass123}"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "ERROR: python/python3 not found on host." >&2
  exit 1
fi

COMPOSE_ARGS=(-f "$COMPOSE_FILE")
OVERRIDE_FILE=""
EVALUATION_MODE_EFFECTIVE="${EVALUATION_MODE:-sync}"

if [[ "$MODE" == "strict" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" && -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    echo "Loaded environment from $ENV_FILE"
  fi

  EVALUATION_MODE_EFFECTIVE="${EVALUATION_MODE:-${EVALUATION_MODE_EFFECTIVE}}"

  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: MODE=strict requires OPENAI_API_KEY (env or $ENV_FILE)." >&2
    exit 2
  fi

  OVERRIDE_FILE="$(mktemp /tmp/compose.override.XXXXXX.yml)"
  cat > "$OVERRIDE_FILE" <<EOF
services:
  api:
    environment:
      OPENAI_API_KEY: "${OPENAI_API_KEY}"
      OPENAI_BASE_URL: "${OPENAI_BASE_URL:-https://api.openai.com/v1}"
EOF
  COMPOSE_ARGS+=(-f "$OVERRIDE_FILE")
fi

cleanup() {
  docker compose "${COMPOSE_ARGS[@]}" down -v >/dev/null 2>&1 || true
  if [[ -n "$OVERRIDE_FILE" && -f "$OVERRIDE_FILE" ]]; then
    rm -f "$OVERRIDE_FILE"
  fi
}
trap cleanup EXIT

echo "[1/8] Starting docker services (db + api) [mode=$MODE]..."
if [[ "${EVALUATION_MODE_EFFECTIVE,,}" == "async" ]]; then
  docker compose "${COMPOSE_ARGS[@]}" up -d db redis api worker
else
  docker compose "${COMPOSE_ARGS[@]}" up -d db api
fi

echo "[2/8] Running migrations..."
docker compose "${COMPOSE_ARGS[@]}" run --rm api bash -lc "pip install -r requirements.txt >/tmp/pip.log && alembic upgrade head"

echo "[3/8] Waiting for /health..."
for i in $(seq 1 60); do
  if curl -fsS "$BASE_URL/health" >/dev/null; then
    echo "API is healthy."
    break
  fi
  sleep 2
  if [[ "$i" -eq 60 ]]; then
    echo "API did not become healthy in time." >&2
    exit 1
  fi
done

echo "[4/8] Scenario: register user"
REGISTER_RESP=$(curl -fsS -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
API_KEY=$($PYTHON_BIN - <<'PY' "$REGISTER_RESP"
import json, sys
print(json.loads(sys.argv[1])["api_key"])
PY
)

if [[ -z "$API_KEY" ]]; then
  echo "Register failed: empty api_key" >&2
  exit 1
fi

echo "[5/8] Scenario: ingest without API key -> expect 401"
NO_KEY_STATUS=$(curl -s -o /tmp/no_key_body.json -w "%{http_code}" -X POST "$BASE_URL/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{"question":"q","answer":"a","contexts":[]}')
[[ "$NO_KEY_STATUS" == "401" ]] || { echo "Expected 401, got $NO_KEY_STATUS" >&2; cat /tmp/no_key_body.json; exit 1; }

echo "[6/8] Scenario: ingest with valid API key"
INGEST_RESP=$(curl -fsS -X POST "$BASE_URL/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"question":"How to increase card limit?","answer":"You can apply via mobile app.","contexts":["Card limit increase requests can be made from mobile app."]}')

TRACE_ID=$($PYTHON_BIN - <<'PY' "$INGEST_RESP"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)
TRACE_STATUS=$($PYTHON_BIN - <<'PY' "$INGEST_RESP"
import json, sys
print(json.loads(sys.argv[1])["status"])
PY
)

echo "Trace status: $TRACE_STATUS"

if [[ "$MODE" == "strict" ]]; then
  if [[ "${EVALUATION_MODE_EFFECTIVE,,}" == "async" ]]; then
    echo "Async mode detected; waiting for trace completion..."
    for i in $(seq 1 60); do
      DETAIL_RESP=$(curl -fsS "$BASE_URL/api/v1/traces/$TRACE_ID" -H "X-API-Key: $API_KEY")
      TRACE_STATUS=$($PYTHON_BIN - <<'PY' "$DETAIL_RESP"
import json, sys
print(json.loads(sys.argv[1])["status"])
PY
)
      if [[ "$TRACE_STATUS" == "completed" ]]; then
        break
      fi
      if [[ "$TRACE_STATUS" == "failed" ]]; then
        echo "STRICT FAIL: async trace became failed" >&2
        exit 1
      fi
      sleep 2
      if [[ "$i" -eq 60 ]]; then
        echo "STRICT FAIL: async trace did not complete in time (status=$TRACE_STATUS)" >&2
        exit 1
      fi
    done
    echo "Final trace status after polling: $TRACE_STATUS"
  else
    [[ "$TRACE_STATUS" == "completed" ]] || {
      echo "STRICT FAIL: expected completed, got $TRACE_STATUS" >&2
      exit 1
    }
  fi
else
  if [[ "$TRACE_STATUS" != "completed" && "$TRACE_STATUS" != "failed" ]]; then
    echo "Unexpected trace status: $TRACE_STATUS" >&2
    exit 1
  fi
fi

echo "[7/8] Scenario: get trace detail and validate evaluation payload"
DETAIL_RESP=$(curl -fsS "$BASE_URL/api/v1/traces/$TRACE_ID" -H "X-API-Key: $API_KEY")
$PYTHON_BIN - <<'PY' "$DETAIL_RESP" "$MODE"
import json, sys
payload = json.loads(sys.argv[1])
mode = sys.argv[2]
assert payload.get("id"), "missing trace id"
assert payload.get("status") in {"completed", "failed"}, "invalid status"
assert "evaluation" in payload, "missing evaluation field"
if mode == "strict":
    assert payload.get("status") == "completed", "strict mode requires completed status"
print("Trace detail validation passed.")
PY

echo "[8/8] Scenario: list traces returns at least one item"
LIST_RESP=$(curl -fsS "$BASE_URL/api/v1/traces?page=1&per_page=20" -H "X-API-Key: $API_KEY")
$PYTHON_BIN - <<'PY' "$LIST_RESP"
import json, sys
payload = json.loads(sys.argv[1])
assert isinstance(payload.get("items"), list), "items is not a list"
assert payload.get("total", 0) >= 1, "expected at least one trace"
print("Trace list validation passed.")
PY

echo "All dockerized E2E scenarios passed (mode=$MODE)."
