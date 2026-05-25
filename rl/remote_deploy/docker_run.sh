#!/bin/bash
# Start the Docker container for GRPO emulator server.
#
# Usage:
#   bash docker_run.sh              # interactive mode
#   bash docker_run.sh --detach     # background mode

set -e

IMAGE_NAME="grpo_server:v1"
CONTAINER_NAME="grpo_emulators"

# Check if image exists
if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Image $IMAGE_NAME not found. Building..."
    docker build --network host -t "$IMAGE_NAME" .
fi

MODE="-it"
if [ "$1" = "--detach" ]; then
    MODE="-d"
fi

echo "Starting container $CONTAINER_NAME..."
docker run --rm $MODE \
    --name="$CONTAINER_NAME" \
    --ipc=host \
    --privileged \
    --device /dev/kvm \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    --network host \
    --init \
    "$IMAGE_NAME" \
    /bin/bash -c "cd /app/server && bash run_all.sh"
