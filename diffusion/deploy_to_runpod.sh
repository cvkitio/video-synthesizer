#!/bin/bash

set -e

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    set -a
    source .env
    set +a
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

IMAGE_URL="ghcr.io/cvkitio/video-synthesizer-qwen:latest"

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
#!/usr/bin/env python3
"""
RunPod Deployment Script for Qwen Image Generator

This script deploys the qwen-image-generator Docker image to RunPod
using the official RunPod Python SDK.
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

try:
    import runpod
except ImportError:
    print("RunPod SDK not installed. Install with: pip install runpod")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QwenRunPodDeployer:
    """Handles deployment of Qwen image generator to RunPod."""
    
    def __init__(self):
        """Initialize RunPod client with API key from .env file."""
        # Load environment variables from .env file
        load_dotenv()
        
        self.api_key = os.getenv("RUNPOD_API_KEY")
        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY not set in .env file or environment")
        
        runpod.api_key = self.api_key
        
        # Configuration from .env
        self.github_username = os.getenv("GITHUB_USERNAME", "sinkers")
        self.image_name = os.getenv("IMAGE_NAME", "qwen-image-generator")
        self.version = os.getenv("VERSION", "latest")
        self.pod_name = os.getenv("POD_NAME", "qwen-generator-pod")
        self.gpu_type = os.getenv("GPU_TYPE", "NVIDIA RTX A4000")
        self.gpu_count = int(os.getenv("GPU_COUNT", "1"))
        
        # Use the correct image URL format for the GitHub Actions workflow
        self.image_url = "ghcr.io/cvkitio/video-synthesizer-qwen:latest"
        
        logger.info(f"Deploying image: {self.image_url}")
        logger.info(f"GPU Type: {self.gpu_type}")
    
    def create_pod(self) -> str:
        """Create a regular pod (persistent deployment)."""
        try:
            logger.info(f"Creating pod: {self.pod_name}")
            
            pod = runpod.create_pod(
                name=self.pod_name,
                image_name=self.image_url,
                gpu_type_id=self.gpu_type,
                cloud_type="SECURE",
                container_disk_in_gb=50,
                volume_in_gb=50,
                min_memory_in_gb=16,
                min_vcpu_count=4,
                ports="8080/http",
                volume_mount_path="/workspace",
                env={
                    "PORT": "8080",
                    "TRANSFORMERS_CACHE": "/workspace/cache",
                    "HF_HOME": "/workspace/cache"
                },
                start_ssh=True
            )
            pod_id = pod["id"]
            
            logger.info(f"✅ Pod created successfully!")
            logger.info(f"Pod ID: {pod_id}")
            logger.info(f"Pod Name: {self.pod_name}")
            logger.info(f"Image: {self.image_url}")
            logger.info(f"GPU: {self.gpu_type}")
            
            return pod_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create pod: {e}")
            raise

    def wait_for_pod_ready(self, pod_id: str, timeout: int = 600) -> bool:
        """Wait for the pod to be ready and running."""
        logger.info("Waiting for pod to be ready...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                pod = runpod.get_pod(pod_id)
                if pod is None:
                    logger.info("Pod is still being initialized...")
                    time.sleep(15)
                    continue
                    
                status = pod.get("desiredStatus")
                runtime = pod.get("runtime", {})
                runtime_status = runtime.get("uptimeInSeconds") if runtime else None
                
                logger.info(f"Pod status: {status}")
                
                if status == "RUNNING" and runtime_status and runtime_status > 30:
                    logger.info("✅ Pod is ready!")
                    return True
                elif status in ["FAILED", "STOPPED"]:
                    logger.error(f"❌ Pod failed to start. Status: {status}")
                    return False
                
                time.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.warning(f"Error checking pod status: {e}")
                time.sleep(15)
        
        logger.error(f"❌ Pod did not become ready within {timeout} seconds")
        return False

    def get_pod_info(self, pod_id: str) -> Dict[str, Any]:
        """Get pod information including connection details."""
        try:
            pod = runpod.get_pod(pod_id)
            
            runtime = pod.get("runtime", {})
            
            # Construct RunPod proxy URL using the pod ID
            api_url = f"http://{pod_id}-8080.proxy.runpod.net/"
            
            return {
                "pod_id": pod_id,
                "status": pod.get("desiredStatus"),
                "api_url": api_url,
                "ssh_connection": runtime.get("sshConnectionString"),
                "uptime": runtime.get("uptimeInSeconds"),
                "gpu_count": runtime.get("gpuCount"),
                "machine_type": pod.get("machine", {}).get("gpuDisplayName")
            }
            
        except Exception as e:
            logger.error(f"Failed to get pod info: {e}")
            return {}

def main():
    """Main deployment function."""
    deployer = None
    pod_id = None
    
    try:
        # Initialize deployer
        logger.info("🚀 Starting Qwen Image Generator deployment to RunPod...")
        deployer = QwenRunPodDeployer()
        
        # Create pod
        pod_id = deployer.create_pod()
        
        # Wait for pod to be ready
        if not deployer.wait_for_pod_ready(pod_id):
            logger.error("❌ Pod deployment failed")
            return 1
        
        # Get pod information
        pod_info = deployer.get_pod_info(pod_id)
        
        # Display success information
        logger.info("\n🎉 Deployment successful!")
        logger.info("=" * 50)
        logger.info(f"Pod ID: {pod_info.get('pod_id')}")
        logger.info(f"Status: {pod_info.get('status')}")
        logger.info(f"GPU: {pod_info.get('machine_type')}")
        logger.info(f"API URL: {pod_info.get('api_url')}")
        logger.info(f"SSH: {pod_info.get('ssh_connection')}")
        
        if pod_info.get('api_url'):
            logger.info("\n📋 Next steps:")
            logger.info(f"1. Health check: curl {pod_info.get('api_url')}health")
            logger.info(f"2. Generate image: POST to {pod_info.get('api_url')}generate")
            logger.info(f"3. Direct URL access: {pod_info.get('api_url')}")
        
        logger.info(f"\n💡 To stop the pod: runpod stop pod {pod_id}")
        logger.info(f"💡 To delete the pod: runpod remove pod {pod_id}")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
PYEOF

echo ""
echo "To deploy using Python script:"
echo "pip install runpod python-dotenv  # Install dependencies if needed"
echo "python deploy_runpod.py"
echo ""
echo "Configuration files created:"
echo "- runpod_template.json: Template configuration for reusable deployments"
echo "- runpod_deploy.json: Pod deployment configuration"
echo "- deploy_runpod.py: Python deployment script"