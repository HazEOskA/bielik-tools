#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${BIELIK_MODEL:-speakleash/Bielik-1.5B-v3.0-Instruct}"
IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:v0.31.0}"
PORT="${BIELIK_PORT:-8000}"
NAME="${BIELIK_CONTAINER_NAME:-bielik-phase5-vllm}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$ROOT/evidence}"
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}"

mkdir -p "$EVIDENCE_DIR" "$HF_CACHE"

cleanup() {
  docker logs "$NAME" > "$EVIDENCE_DIR/phase5-vllm-gpu.log" 2>&1 || true
  docker inspect "$NAME" > "$EVIDENCE_DIR/phase5-vllm-gpu-inspect.json" 2>&1 || true
  docker stop "$NAME" >/dev/null 2>&1 || true
  docker rm "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== PHASE 5 CUDA PRECHECK ==="
command -v docker
command -v nvidia-smi
nvidia-smi | tee "$EVIDENCE_DIR/phase5-nvidia-smi.txt"

docker info > "$EVIDENCE_DIR/phase5-docker-info.txt"
docker pull "$IMAGE"

docker run -d   --name "$NAME"   --runtime nvidia   --gpus all   --ipc=host   -p "$PORT:8000"   -v "$HF_CACHE:/root/.cache/huggingface"   -v "$ROOT:/workspace:ro"   ${HF_TOKEN:+-e "HF_TOKEN=$HF_TOKEN"}   "$IMAGE"   --model "$MODEL"   --dtype auto   --max-model-len 2048   --enable-auto-tool-choice   --tool-parser-plugin /workspace/tools/bielik_vllm_tool_parser.py   --tool-call-parser bielik   --chat-template /workspace/tools/bielik_advanced_chat_template.jinja   --host 0.0.0.0   --port 8000

ready=0
for _ in $(seq 1 180); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || echo false)" != "true" ]; then
    break
  fi
  sleep 5
done

docker logs "$NAME" > "$EVIDENCE_DIR/phase5-vllm-gpu.log" 2>&1 || true
docker inspect "$NAME" > "$EVIDENCE_DIR/phase5-vllm-gpu-inspect.json" 2>&1 || true

if [ "$ready" -ne 1 ]; then
  echo "vLLM CUDA server did not become ready"
  tail -n 400 "$EVIDENCE_DIR/phase5-vllm-gpu.log" || true
  exit 1
fi

BIELIK_BASE_URL="http://127.0.0.1:$PORT" BIELIK_MODEL="$MODEL" BIELIK_EVIDENCE_PATH="$EVIDENCE_DIR/phase5-vllm-gpu.json" python "$ROOT/scripts/live_vllm_gpu_torture.py"
