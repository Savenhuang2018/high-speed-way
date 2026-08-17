#!/usr/bin/env bash
# DeepSeek 评测脚本（lm-evaluation-harness via 火山引擎方舟）
# 用法:
#   ./eval_deepseek.sh gsm8k 5        # 评测 gsm8k, 5 个样本
#   ./eval_deepseek.sh mmlu,arc_challenge 100
set -e

TASKS="${1:-gsm8k}"
LIMIT="${2:-5}"
MODEL="deepseek-v4-flash-ga-260731"
BASE_URL="https://ark.cn-beijing.volces.com/api/v3/chat/completions"
TOKENIZER="deepseek-ai/DeepSeek-V3"
API_KEY="${ARK_API_KEY:-ark-ec50eebd-b633-48e7-93c4-61d36b15d3d4-acaba}"

echo "=== DeepSeek 评测: tasks=$TASKS limit=$LIMIT ==="
echo "模型: $MODEL @ 火山引擎"
echo ""

OPENAI_API_KEY="$API_KEY" python3 -m lm_eval run \
  --model openai-chat-completions \
  --apply_chat_template \
  --model_args "model=$MODEL,base_url=$BASE_URL,tokenizer=$TOKENIZER" \
  --tasks "$TASKS" \
  --limit "$LIMIT" \
  --output_path "eval_results_${MODEL}_${TASKS//,/_}.json"
