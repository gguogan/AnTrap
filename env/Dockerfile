FROM nvcr.io/nvidia/pytorch:24.05-py3

ENV DEBIAN_FRONTEND=noninteractive

# 1. System dependencies, Node.js 22, Appium
RUN rm -f /etc/apt/sources.list.d/cuda.list /etc/apt/sources.list.d/nvidia-ml.list || true && \
    apt-get update --fix-missing && \
    apt-get install -y \
    libgl1 git sudo vim libnss3 libxkbfile1 libdrm2 libx11-6 libxi6 \
    pulseaudio curl wget unzip cpu-checker ffmpeg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm i --location=global appium \
    && appium driver install uiautomator2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && mkdir /app \
    && groupadd -r kvm || true && gpasswd -a root kvm

WORKDIR /app

# 2. Miniconda + Python 3.11 isolated environment
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh \
    && bash miniconda.sh -b -p /opt/conda \
    && rm miniconda.sh

ENV PATH="/opt/conda/bin:$PATH"

RUN conda create -y -n agent python=3.11

ENV CONDA_DEFAULT_ENV=agent
ENV PATH="/opt/conda/envs/agent/bin:$PATH"

# 3. Python dependencies
COPY requirements.txt .
RUN pip install torch torchvision torchaudio --default-timeout=1000 \
    && pip install Appium-Python-Client \
    && pip install -r requirements.txt \
    && pip install --upgrade "grpcio>=1.71.0" "grpcio-tools>=1.71.0" "protobuf>=5.26.0" \
    && pip install "numpy<2.0" "opencv-python-headless" --force-reinstall

# 4. JDK 17 + Android command-line tools
RUN wget https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_linux-x64_bin.tar.gz \
    && tar -xf ./openjdk-17.0.2_linux-x64_bin.tar.gz \
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
# Host proxy address: leave empty to auto-detect the default gateway
# (Linux Docker is typically 172.17.0.1).
ARG PROXY_HOST=""

# 5. Android SDK, system image, AVD
RUN HOST_IP="${PROXY_HOST:-$(ip route show default | awk '/default/{print $3}')}" \
    && echo "Proxy host IP: $HOST_IP" \
    && yes | sdkmanager --licenses \
    && echo "[1/3] Installing platform-tools / emulator..." \
    && for i in $(seq 1 10); do \
         sdkmanager --proxy=http --proxy_host="$HOST_IP" --proxy_port=17890 \
           "platform-tools" "platforms;android-${API_LEVEL}" "emulator" --verbose \
           && echo "Base packages downloaded" && break \
           || (rm -rf "$ANDROID_HOME/emulator" /tmp/* && sleep 3); \
       done \
    && echo "[2/3] Downloading system image (resumable)..." \
    && export http_proxy="http://$HOST_IP:17890" \
    && export https_proxy="http://$HOST_IP:17890" \
    && for i in $(seq 1 30); do \
         wget -c "https://dl.google.com/android/repository/sys-img/google_apis/x86_64-33_r15.zip" -O system-image.zip \
           && unzip -t system-image.zip && echo "System image verified" && break \
           || (echo "Resume retry $i/30..."; sleep 2); \
       done \
    && mkdir -p "$ANDROID_HOME/system-images/android-${API_LEVEL}/google_apis/" \
    && unzip -q system-image.zip -d "$ANDROID_HOME/system-images/android-${API_LEVEL}/google_apis/" \
    && rm system-image.zip \
    && echo "[3/3] Creating AVD..." \
    && sh -c 'echo "no" | avdmanager create avd --force --name "${EMULATOR_NAME}" --package "${EMULATOR_PACKAGE}" --device "${EMULATOR_DEVICE}"'

# 6. Final permissions
COPY profile.global /usr/local/etc/
RUN chmod 555 /usr/local/etc/profile.global \
    && chmod -R 755 "$ANDROID_HOME" \
    && chmod -R 755 "$JAVA_HOME" \
    && echo "%users ALL = (ALL) NOPASSWD: ALL" >> /etc/sudoers
