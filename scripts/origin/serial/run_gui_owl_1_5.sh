MODEL_NAME="gui_owl_1_5"
MODEL="GUI-Owl-1.5-8B-Think"

mkdir -p log/origin/${MODEL} trajectory/origin/${MODEL}

current_time=$(date +"%Y-%m-%d_%H-%M-%S")
LOG="log/origin/${MODEL}/log_gui_owl_1_5_"$current_time".log"
API_KEY="EMPTY"
BASE_URL="${BASE_URL:-http://localhost:9001/v1}"
TRAJ_OUTPUT_PATH="trajectory/origin/${MODEL}/traj_gui_owl_1_5_"$current_time

python scripts/origin/serial/run_gui_owl_1_5.py \
  --suite_family=android_world \
  --model=$MODEL \
  --api_key=$API_KEY \
  --base_url=$BASE_URL \
  --traj_output_path=$TRAJ_OUTPUT_PATH \
  --grpc_port=8554 \
  --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
  --console_port=5554 2>&1 | tee "$LOG"

  #   --tasks=SimpleCalendarAnyEventsOnDate \
