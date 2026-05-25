# Android GRPO Training Server - Emulator + FastAPI
# Based on the top-level env/Dockerfile
#
# Build:  docker build --network host -t grpo_server:v1 .
# Run:    bash docker_run.sh

FROM nvcr.io/nvidia/pytorch:24.05-py3

ENV DEBIAN_FRONTEND=noninteractive

# 1. System dependencies
RUN apt-get update --fix-missing && \
    apt-get install -y \
    libgl1 git sudo vim libnss3 libxkbfile1 libdrm2 libx11-6 libxi6 \
    pulseaudio curl wget unzip cpu-checker ffmpeg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm i --location=global appium --registry=https://registry.npmmirror.com \
    && appium driver install uiautomator2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app \
    && groupadd -r kvm || true && gpasswd -a root kvm

WORKDIR /app

# 2. Python 3.11 via Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh \
    && bash miniconda.sh -b -p /opt/conda \
    && rm miniconda.sh

ENV PATH="/opt/conda/bin:$PATH"
RUN conda create -y -n agent python=3.11
ENV CONDA_DEFAULT_ENV=agent
ENV PATH="/opt/conda/envs/agent/bin:$PATH"

# 3. Java + Android SDK
RUN wget https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_linux-x64_bin.tar.gz \
    && tar -xvf ./openjdk-17.0.2_linux-x64_bin.tar.gz \
    && mv ./jdk-17.0.2 "/app/.jdk" \
    && rm ./openjdk-17.0.2_linux-x64_bin.tar.gz \
    && wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip \
    && unzip commandlinetools-linux-11076708_latest.zip \
    && mkdir -p /app/.android/cmdline-tools \
    && mv cmdline-tools /app/.android/cmdline-tools/latest \
    && rm commandlinetools-linux-11076708_latest.zip

ENV JAVA_HOME="/app/.jdk"
ENV ANDROID_HOME="/app/.android"
ENV ANDROID_SDK_ROOT="$ANDROID_HOME"
ENV PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"
ENV ANDROID_AVD_HOME="$ANDROID_HOME/avd"

ARG API_LEVEL="33"
ARG TARGET="google_apis"
ARG ARCH="x86_64"
ARG EMULATOR_PACKAGE="system-images;android-${API_LEVEL};${TARGET};${ARCH}"
ARG EMULATOR_NAME="Pixel_6_API_33"
ARG EMULATOR_DEVICE="pixel_6"

# 4. Install Android SDK components + create base AVD
RUN yes | sdkmanager --licenses \
    && sdkmanager "platform-tools" "platforms;android-${API_LEVEL}" "emulator" "${EMULATOR_PACKAGE}" \
    && sh -c 'echo "no" | avdmanager create avd --force --name "${EMULATOR_NAME}" --package "${EMULATOR_PACKAGE}" --device "${EMULATOR_DEVICE}"'

# 5. Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# 6. Copy server code
COPY . /app/server/

RUN chmod -R 755 "$ANDROID_HOME" \
    && chmod -R 755 "$JAVA_HOME" \
    && echo "%users ALL = (ALL) NOPASSWD: ALL" >> /etc/sudoers
