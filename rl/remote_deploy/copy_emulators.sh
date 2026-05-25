#!/bin/bash
# Create 8 independent AVD copies from the base AVD.
# Run this ONCE inside the Docker container before starting emulators.

AVD_DIR="${ANDROID_AVD_HOME:-$HOME/.android/avd}"
BASE_AVD="Pixel_6_API_33"
N=8

echo "Creating $N AVD copies from $BASE_AVD..."

if [ ! -d "$AVD_DIR/${BASE_AVD}.avd" ]; then
    echo "Error: Base AVD $BASE_AVD not found at $AVD_DIR/${BASE_AVD}.avd"
    exit 1
fi

for i in $(seq 0 $((N-1))); do
    AVD_NAME="${BASE_AVD}_${i}"
    AVD_PATH="${AVD_DIR}/${AVD_NAME}.avd"
    INI_PATH="${AVD_DIR}/${AVD_NAME}.ini"

    if [ -d "$AVD_PATH" ]; then
        echo "  $AVD_NAME already exists, skipping"
        continue
    fi

    echo "  Creating $AVD_NAME..."
    cp -r "$AVD_DIR/${BASE_AVD}.avd" "$AVD_PATH"
    rm -f "$AVD_PATH"/*.qcow2
    rm -f "$AVD_PATH/multiinstance.lock"

    if [ -f "$AVD_DIR/${BASE_AVD}.avd/userdata.img" ]; then
        cp "$AVD_DIR/${BASE_AVD}.avd/userdata.img" "$AVD_PATH/userdata.img"
    fi

    cat > "$INI_PATH" << EOF
avd.ini.encoding=UTF-8
path=$AVD_PATH
target=android-33
EOF
done

echo "Done. $N AVDs ready."
