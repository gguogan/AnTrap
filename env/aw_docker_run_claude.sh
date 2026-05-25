#!/usr/bin/env bash

WORK_DIR=$(pwd)
CONTAINER_NAME="android_world_agent_$(date +%s)"

# Auto-detect the currently active nvm node version
NODE_VERSION=$(ls "$HOME/.nvm/versions/node/" 2>/dev/null | sort -V | tail -1)
NODE_MOUNT=""
NODE_PATH_EXTRA=""
if [ -n "$NODE_VERSION" ]; then
  NODE_MOUNT="-v $HOME/.nvm/versions/node/$NODE_VERSION:/opt/node-v20"
  NODE_PATH_EXTRA="/opt/node-v20/bin:"
fi

echo "Launching the Android World development environment..."
echo "Local code dir: $WORK_DIR will be mounted into the container at /app/workspace"

docker run --rm -it \
  --name=$CONTAINER_NAME \
  --ipc=host \
  --gpus all \
  --privileged \
  --device /dev/kvm \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  -v "$WORK_DIR":/app/workspace \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$HOME/.cache/modelscope":/root/.cache/modelscope \
  -v "$HOME/.npm-global":/root/.npm-global \
  -v "$HOME/.gemini":/root/.gemini \
  -v "$HOME/.claude":/root/.claude \
  -v "$HOME/.local":/root/.local \
  $NODE_MOUNT \
  -e DISPLAY=$DISPLAY \
  -e TERM=xterm-256color \
  -e COLORTERM=truecolor \
  -e http_proxy="http://127.0.0.1:17892" \
  -e https_proxy="http://127.0.0.1:17892" \
  -e PATH="/opt/conda/envs/agent/bin:/root/.local/bin:${NODE_PATH_EXTRA}/root/.npm-global/bin:/app/.android/emulator:/app/.android/platform-tools:$PATH" \
  --network host \
  --init \
  android_world_ready:v1 \
  bash
