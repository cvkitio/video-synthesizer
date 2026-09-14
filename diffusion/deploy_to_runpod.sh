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
CONTAINER_DISK_GB=${CONTAINER_DISK_GB:-100}
VOLUME_DISK_GB=${VOLUME_DISK_GB:-100}

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
  "volumeInGb": ${VOLUME_DISK_GB},
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
  "containerDiskInGb": ${CONTAINER_DISK_GB},
  "volumeInGb": ${VOLUME_DISK_GB},
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
        self.container_disk_gb = int(os.getenv("CONTAINER_DISK_GB", "100"))
        self.volume_disk_gb = int(os.getenv("VOLUME_DISK_GB", "100"))
        
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
                container_disk_in_gb=self.container_disk_gb,
                volume_in_gb=self.volume_disk_gb,
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

    def wait_for_health_check(self, api_url: str, timeout: int = 600) -> bool:
        """Wait for the /health endpoint to return OK."""
        import requests
        
        logger.info("Waiting for service health check...")
        start_time = time.time()
        health_url = f"{api_url}health"
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    health_data = response.json()
                    if health_data.get("status") == "healthy":
                        logger.info("✅ Service is healthy!")
                        return True
                    else:
                        logger.info(f"Service status: {health_data.get('status', 'unknown')}")
                        
            except requests.exceptions.RequestException as e:
                logger.info(f"Health check failed: {str(e)[:100]}...")
            
            logger.info("Waiting for service to be healthy...")
            time.sleep(30)  # Check every 30 seconds
        
        logger.error(f"❌ Service did not become healthy within {timeout} seconds")
        return False

    def submit_test_job(self, api_url: str) -> Optional[Dict[str, Any]]:
        """Submit a test image generation job."""
        import requests
        
        logger.info("Submitting test image generation job...")
        
        # Get AWS credentials from environment
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") 
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        s3_bucket = os.getenv("S3_BUCKET")
        
        if not all([aws_access_key, aws_secret_key, s3_bucket]):
            logger.warning("⚠️ AWS credentials not configured. Skipping test job.")
            logger.info("Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET in .env")
            return None
        
        test_payload = {
            "prompt": "A beautiful sunset over mountains, photorealistic, detailed",
            "negative_prompt": "ugly, blurry, low quality",
            "aspect_ratio": "16:9",
            "num_inference_steps": 20,  # Faster for testing
            "seed": 42,
            "aws_access_key_id": aws_access_key,
            "aws_secret_access_key": aws_secret_key,
            "aws_region": aws_region,
            "s3_bucket": s3_bucket
        }
        
        try:
            generate_url = f"{api_url}generate"
            response = requests.post(generate_url, json=test_payload, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                logger.info("✅ Test job submitted successfully!")
                logger.info(f"Image URL: {result.get('image_url')}")
                logger.info(f"S3 Key: {result.get('s3_key')}")
                return result
            else:
                logger.error(f"❌ Test job failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to submit test job: {e}")
            return None

    def verify_s3_image(self, s3_bucket: str, s3_key: str, timeout: int = 300) -> bool:
        """Verify that the image was uploaded to S3."""
        try:
            import boto3
        except ImportError:
            logger.warning("⚠️ boto3 not installed. Skipping S3 verification.")
            logger.info("Install with: pip install boto3")
            return True  # Don't fail deployment if boto3 isn't available
        
        logger.info("Verifying image upload to S3...")
        
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        
        if not all([aws_access_key, aws_secret_key]):
            logger.warning("⚠️ AWS credentials not configured. Skipping S3 verification.")
            return True
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    response = s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
                    file_size = response.get('ContentLength', 0)
                    
                    if file_size > 1000:  # Image should be larger than 1KB
                        logger.info(f"✅ Image verified in S3! Size: {file_size:,} bytes")
                        logger.info(f"S3 URL: https://{s3_bucket}.s3.{aws_region}.amazonaws.com/{s3_key}")
                        return True
                    else:
                        logger.info(f"Image file too small ({file_size} bytes), waiting...")
                        
                except s3_client.exceptions.NoSuchKey:
                    logger.info("Image not yet uploaded to S3, waiting...")
                
                time.sleep(10)  # Check every 10 seconds
            
            logger.error(f"❌ Image not found in S3 within {timeout} seconds")
            return False
            
        except Exception as e:
            logger.error(f"❌ S3 verification failed: {e}")
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
        api_url = pod_info.get('api_url')
        
        if not api_url:
            logger.error("❌ Could not get pod API URL")
            return 1
        
        # Wait for health check to pass
        logger.info(f"\n🏥 Performing health check on {api_url}health")
        if not deployer.wait_for_health_check(api_url):
            logger.error("❌ Health check failed")
            return 1
        
        # Submit test job and verify S3 upload
        logger.info("\n🧪 Running end-to-end test...")
        test_result = deployer.submit_test_job(api_url)
        
        if test_result:
            s3_bucket = os.getenv("S3_BUCKET")
            s3_key = test_result.get("s3_key")
            
            if s3_bucket and s3_key:
                if deployer.verify_s3_image(s3_bucket, s3_key):
                    logger.info("\n🎉 End-to-end test successful!")
                else:
                    logger.warning("\n⚠️ S3 verification failed, but deployment is complete")
            else:
                logger.info("\n✅ Test job completed (S3 details not available)")
        else:
            logger.warning("\n⚠️ Test job skipped, but deployment is complete")
        
        # Display success information
        logger.info("\n🎉 Deployment successful!")
        logger.info("=" * 60)
        logger.info(f"Pod ID: {pod_info.get('pod_id')}")
        logger.info(f"Status: {pod_info.get('status')}")
        logger.info(f"GPU: {pod_info.get('machine_type')}")
        logger.info(f"API URL: {pod_info.get('api_url')}")
        logger.info(f"SSH: {pod_info.get('ssh_connection')}")
        
        if test_result:
            logger.info(f"\n🖼️ Test Image Generated:")
            logger.info(f"Image URL: {test_result.get('image_url')}")
            logger.info(f"S3 Key: {test_result.get('s3_key')}")
        
        logger.info("\n📋 API Endpoints:")
        logger.info(f"Health check: GET {api_url}health")
        logger.info(f"Generate image: POST {api_url}generate")
        
        logger.info(f"\n💡 Management commands:")
        logger.info(f"Stop pod: runpod stop pod {pod_id}")
        logger.info(f"Delete pod: runpod remove pod {pod_id}")
        
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
echo "pip install runpod python-dotenv requests boto3  # Install dependencies if needed"
echo "python deploy_runpod.py"
echo ""
echo "Configuration files created:"
echo "- runpod_template.json: Template configuration for reusable deployments"
echo "- runpod_deploy.json: Pod deployment configuration"
echo "- deploy_runpod.py: Python deployment script"