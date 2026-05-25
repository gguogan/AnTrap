# Remote Deploy - GRPO Emulator Server

Copy this whole folder to the remote emulator machine and follow the steps below.

## Files

```
remote_deploy/
├── Dockerfile              # Docker image (Android SDK + emulator + Python)
├── requirements.txt        # Python dependencies
├── docker_run.sh           # Start the Docker container
├── copy_emulators.sh       # Duplicate 8 AVDs
├── start_emulators.sh      # Launch 8 emulators
├── android_grpo_server.py  # FastAPI server
├── run_all.sh              # One-shot launch
└── README.md
```

## Option 1: Use an existing Docker image

If the remote machine already has a prebuilt Android emulator image (e.g., the
one previously used for the AndroidWorld experiments), you can reuse it.

```bash
# 1. Launch the container (replace with your image name)
docker run --rm -it \
    --privileged --device /dev/kvm \
    --network host --init \
    -v $(pwd):/app/server \
    YOUR-IMAGE:tag \
    /bin/bash

# 2. Inside the container
cd /app/server
bash run_all.sh
```

## Option 2: Build from scratch

```bash
# 1. Build the image (~20-30 min, downloads the Android SDK)
docker build --network host -t grpo_server:v1 .

# 2. One-shot launch
bash docker_run.sh
```

## Option 3: No Docker (remote machine already has an Android environment)

If the remote machine already has the Android SDK and emulator installed:

```bash
# 1. Install Python deps
pip install -r requirements.txt

# 2. Make sure the project has been installed (pip install -e .)
# (the server depends on the android_world package)

# 3. One-shot launch
bash run_all.sh
```

## Verification

Once the server is up, you should see `Uvicorn running on http://0.0.0.0:29101`.

Test it on the remote machine:
```bash
curl http://localhost:29101/health
# → {"status":"ok","active_emulators":[0,1,2,3,4,5,6,7],"total":8}

curl http://localhost:29101/emu/0/health
# → {"status":"ok","emu_id":0}
```

## Connecting from the training machine

Once the server is running, open an SSH tunnel from the HPC training node:

```bash
# Direct SSH
ssh -L 29101:localhost:29101 user@REMOTE_HOST -N &

# Through a jump host
ssh -J user@JUMP_HOST -L 9000:localhost:29101 user@REMOTE_HOST -N &
```

Then verify on the HPC node:
```bash
curl http://localhost:29101/health
```

Seeing `active_emulators` in the response means everything is connected.
