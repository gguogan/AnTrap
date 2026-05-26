CKPT="/root/.cache/modelscope/UI-TARS-1.5-7B"

# Argument tweaks
PIXEL_ARGS='{"min_pixels":3136,"max_pixels":3211264}'
IMAGE_LIMIT_ARGS="image=8"  # Use key=value form (no braces/quotes)
MP_SIZE=4

echo "Launching the vLLM multimodal inference service..."

VLLM_USE_MODELSCOPE=true vllm serve "$CKPT" \
    --max-model-len 32768 \
    --mm-processor-kwargs "$PIXEL_ARGS" \
    --limit-mm-per-prompt "$IMAGE_LIMIT_ARGS" \
    --tensor-parallel-size $MP_SIZE \
    --allowed-local-media-path '/' \
    --port 4243
