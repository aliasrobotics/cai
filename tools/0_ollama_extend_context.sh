#!/bin/bash

#
# This script extends the context size of a given model
#
# Usage:
#   ./0_ollama_extend_context.sh <model> <ctx>
#
# Example:
#   ./0_ollama_extend_context.sh qwen2.5:14b 32768
#
################################################################################

################################################################################
#
# Parameters
#
################################################################################
# Default values
model=${1:-qwen2.5:14b}
ctx=${2:-32768}

################################################################################
#
# Functions
#
################################################################################

# Function to validate the context size of a model
validate_context_size() {
    local model=$1
    local expected_ctx=$2

    echo "Validating context size of $model..."

    # Start the model in background and capture PID
    ollama run $model "test" >/dev/null 2>&1 &
    local OLLAMA_PID=$!

    # Give it a moment to start up
    sleep 2

    # Get the actual context size from ps output
    local actual_ctx=$(ps aux | grep ollama | grep ctx-size | awk '{for(i=1;i<=NF;i++) if($i=="--ctx-size") print $(i+1)}')

    # Kill the ollama process
    kill $OLLAMA_PID 2>/dev/null

    if [ -n "$actual_ctx" ]; then
        actual_ctx_clean=$(echo "$actual_ctx" | tr -d '\n')
        expected_ctx_clean=$(echo "$expected_ctx" | tr -d '\n')

        echo "Detected context size: $actual_ctx_clean, expected: $expected_ctx_clean"

        if [ "$actual_ctx_clean" -ge "$expected_ctx_clean" ]; then
            echo "✅ Context size validation successful"
            return 0
        else
            echo "❌ Context size ($actual_ctx_clean) is smaller than requested ($expected_ctx_clean)"
            return 1
        fi
    else
        echo "❌ Could not detect context size"
        return 1
    fi
}


################################################################################
#
# Main
#
################################################################################

# Pull the model
ollama pull $model
# Delete the model to create, if it exists
if ollama list | grep -q "$model-ctx-$ctx"; then
    ollama rm $model-ctx-$ctx
fi

# Get the modelfile
modelfile="modelfile.temp"
ollama show $model --modelfile > $modelfile

# Add the following to the modelfile
if [[ "$OSTYPE" == "darwin"* ]]; then
    # OS X
    sed -i '' '/^FROM /a\
PARAMETER num_ctx '"$ctx"'
' $modelfile
else
    # Linux
    sed -i '/^FROM /a PARAMETER num_ctx '"$ctx"'' $modelfile
fi

# Save the new model
if ollama create -f $modelfile $model-ctx-$ctx; then
    echo "✅ Successfully created model $model-ctx-$ctx"
else
    echo "❌ Failed to create model $model-ctx-$ctx"
    exit 1
fi

# Cleanup
rm $modelfile


# Validate the new model
if ! validate_context_size "$model-ctx-$ctx" "$ctx"; then
    exit 1
fi
