#!/bin/bash

# Create N independent AVD copies from the base AVD
# This ensures each emulator has its own file system

AVD_DIR="$HOME/.android/avd"
BASE_AVD="Pixel_6_API_33"
N=10

echo "Creating $N AVD copies from $BASE_AVD..."

# Check if base AVD exists
if [ ! -d "$AVD_DIR/${BASE_AVD}.avd" ]; then
    echo "Error: Base AVD $BASE_AVD not found!"
    exit 1
fi

# Create AVD copies 0-$((N-1))
for i in $(seq 0 $((N-1))); do
    AVD_NAME="${BASE_AVD}_${i}"
    AVD_PATH="${AVD_DIR}/${AVD_NAME}.avd"
    INI_PATH="${AVD_DIR}/${AVD_NAME}.ini"

    # Skip if already exists
    if [ -d "$AVD_PATH" ]; then
        echo "AVD $AVD_NAME already exists, skipping..."
        continue
    fi

    echo "Creating $AVD_NAME..."

    # Copy the AVD directory
    cp -r "$AVD_DIR/${BASE_AVD}.avd" "$AVD_PATH"

    # Remove qcow2 files to force independent copies
    # The emulator will recreate them as needed
    rm -f "$AVD_PATH"/*.qcow2

    # Recreate userdata.img to ensure it's independent
    # This ensures each AVD has its own user data
    if [ -f "$AVD_PATH/userdata.img" ]; then
        # Create a fresh copy of userdata
        cp "$AVD_DIR/${BASE_AVD}.avd/userdata.img" "$AVD_PATH/userdata.img"
    fi

    # Create the ini file
    cat > "$INI_PATH" << EOF
avd.ini.encoding=UTF-8
path=$AVD_PATH
target=android-33
EOF

    # Remove multi-instance lock file if exists
    rm -f "$AVD_PATH/multiinstance.lock"

    echo "  Created $AVD_NAME"
done

echo ""
echo "Done! Created $N AVD copies."
echo ""
echo "Available AVDs:"
ls -d "$AVD_DIR"/${BASE_AVD}_*.avd | xargs -n1 basename