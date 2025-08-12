#!/bin/bash

set -e

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Set defaults if not provided in .env
RUNPOD_API_KEY=${RUNPOD_API_KEY:-""}
GITHUB_USERNAME=${GITHUB_USERNAME:-"your-github-username"}
IMAGE_NAME=${IMAGE_NAME:-"qwen-image-generator"}
VERSION=${VERSION:-"latest"}
TEMPLATE_NAME=${TEMPLATE_NAME:-"qwen-image-generator-template"}
POD_NAME=${POD_NAME:-"qwen-generator-pod"}
GPU_TYPE=${GPU_TYPE:-"NVIDIA RTX A4000"}
GPU_COUNT=${GPU_COUNT:-1}

if [ -z "$RUNPOD_API_KEY" ]; then
    echo "Error: RUNPOD_API_KEY environment variable is not set"
    echo "Please set it with: export RUNPOD_API_KEY=your_runpod_api_key"
    exit 1
fi

IMAGE_URL="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "Creating RunPod template configuration..."
cat > runpod_template.json <<EOF
{
  "name": "${TEMPLATE_NAME}",
  "imageName": "${IMAGE_URL}",
  "dockerArgs": "",
  "ports": "8080/http",
  "volumeInGb": 50,
  "volumeMountPath": "/workspace",
  "env": [
    {
      "key": "PORT",
      "value": "8080"
    },
    {
      "key": "TRANSFORMERS_CACHE",
      "value": "/workspace/cache"
    },
    {
      "key": "HF_HOME",
      "value": "/workspace/cache"
    }
  ],
  "startJupyter": false,
  "startSSH": true
}
EOF

echo "Creating pod deployment configuration..."
cat > runpod_deploy.json <<EOF
{
  "cloudType": "SECURE",
  "gpuType": "${GPU_TYPE}",
  "gpuCount": ${GPU_COUNT},
  "containerDiskInGb": 50,
  "volumeInGb": 50,
  "minMemoryInGb": 16,
  "minVcpuCount": 4,
  "name": "${POD_NAME}",
  "imageName": "${IMAGE_URL}",
  "dockerArgs": "",
  "ports": "8080/http",
  "volumeMountPath": "/workspace",
  "env": [
    {
      "key": "PORT",
      "value": "8080"
    },
    {
      "key": "TRANSFORMERS_CACHE",
      "value": "/workspace/cache"
    },
    {
      "key": "HF_HOME",
      "value": "/workspace/cache"
    }
  ],
  "dataCenterId": null,
  "countryCode": null,
  "minBidPrice": null,
  "stopAfter": null,
  "startJupyter": false,
  "startSSH": true,
  "templateId": null
}
EOF

echo "Deploying to RunPod..."
echo "Note: You can use the RunPod CLI or API to deploy with these configurations"
echo ""
echo "Using RunPod CLI:"
echo "1. Install RunPod CLI: pip install runpod"
echo "2. Set API key: runpod config --api-key ${RUNPOD_API_KEY}"
echo "3. Deploy pod: runpod deploy --config runpod_deploy.json"
echo ""
echo "Using RunPod API directly:"
echo "curl -X POST 'https://api.runpod.io/v2/pods' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer ${RUNPOD_API_KEY}' \\"
echo "  -d @runpod_deploy.json"
echo ""
echo "Using Python script for deployment:"

cat > deploy_runpod.py <<'PYEOF'
import os
import json
import requests
import sys

def deploy_to_runpod():
    api_key = os.environ.get('RUNPOD_API_KEY')
    if not api_key:
        print("Error: RUNPOD_API_KEY not set")
        sys.exit(1)
    
    with open('runpod_deploy.json', 'r') as f:
        config = json.load(f)
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    response = requests.post(
        'https://api.runpod.io/v2/pods',
        headers=headers,
        json=config
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Pod deployed successfully!")
        print(f"Pod ID: {result.get('id')}")
        print(f"Pod URL: {result.get('desiredStatus', {}).get('url')}")
    else:
        print(f"Deployment failed: {response.status_code}")
        print(response.text)
        sys.exit(1)

if __name__ == "__main__":
    deploy_to_runpod()
PYEOF

echo ""
echo "To deploy using Python script:"
echo "python deploy_runpod.py"
echo ""
echo "Configuration files created:"
echo "- runpod_template.json: Template configuration for reusable deployments"
echo "- runpod_deploy.json: Pod deployment configuration"
echo "- deploy_runpod.py: Python deployment script"