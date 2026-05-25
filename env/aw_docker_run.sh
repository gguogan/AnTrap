#!/usr/bin/env bash

WORK_DIR=$(pwd)
CONTAINER_NAME="android_world_agent_$(date +%s)"

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
  -e DISPLAY=$DISPLAY \
  --network host \
  --init \
  android_world_ready:v1 \
  /bin/bash
