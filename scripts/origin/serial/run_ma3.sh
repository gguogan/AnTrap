MODEL_NAME="mobile_agent_v3"
MODEL="your model name"

mkdir -p log/${MODEL_NAME} trajectory/${MODEL_NAME}

current_time=$(date +"%Y-%m-%d_%H-%M-%S")
LOG="log/${MODEL_NAME}/log_ma3_"$current_time".log"
API_KEY="your api kei"
BASE_URL="${BASE_URL:-http://localhost:9001/v1}"
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"
TRAJ_OUTPUT_PATH="trajectory/${MODEL_NAME}/traj_"$current_time

python scripts/origin/serial/run_ma3.py \
  --suite_family=android_world \
  --agent_name=$MODEL_NAME \
  --model=$MODEL \
  --api_key=$API_KEY \
  --base_url=$BASE_URL \
  --traj_output_path=$TRAJ_OUTPUT_PATH \
  --grpc_port=8554 \
  --console_port=5554 2>&1 | tee "$LOG"