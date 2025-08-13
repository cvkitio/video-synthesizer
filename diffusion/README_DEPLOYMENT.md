# Qwen Image Generator Deployment Guide

[![Build and Push Docker Image](https://github.com/sinkers/video-synthesizer/actions/workflows/docker-build-push.yml/badge.svg)](https://github.com/sinkers/video-synthesizer/actions/workflows/docker-build-push.yml)

## Overview
This is a GPU-accelerated image generation service using the Qwen diffusion model that accepts HTTP POST requests and uploads generated images to S3.

## Quick Start

### 1. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env with your actual credentials
nano .env
```

## Features
- HTTP API endpoint for image generation
- S3 upload integration
- GPU acceleration with NVIDIA CUDA
- Docker containerization
- GitHub Container Registry (GHCR) support
- RunPod deployment ready

## API Usage

### Health Check
```bash
curl http://localhost:8080/health
```

### Generate Image
```bash
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over mountains",
    "s3_bucket": "your-bucket-name",
    "aws_access_key_id": "your-access-key",
    "aws_secret_access_key": "your-secret-key",
    "aws_region": "us-east-1",
    "aspect_ratio": "16:9",
    "negative_prompt": "ugly, deformed, disfigured",
    "num_inference_steps": 50,
    "seed": 42
  }'
```

### Request Parameters
- `prompt` (required): Text description of the image to generate
- `s3_bucket` (optional if set in .env): S3 bucket name for upload
- `aws_access_key_id` (optional if set in .env): AWS access key
- `aws_secret_access_key` (optional if set in .env): AWS secret key
- `aws_region` (optional): AWS region (default: us-east-1)
- `aspect_ratio` (optional): Image aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3)
- `negative_prompt` (optional): Things to avoid in the image
- `positive_magic` (optional): Additional quality enhancers
- `num_inference_steps` (optional): Number of generation steps (default: 50)
- `true_cfg_scale` (optional): Guidance scale (default: 4.0)
- `seed` (optional): Random seed for reproducibility

## Environment Variables

All configuration can be managed through the `.env` file. See `.env.example` for all available options:

- **GitHub Registry**: `GITHUB_USERNAME`, `GITHUB_TOKEN`
- **AWS S3**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`
- **RunPod**: `RUNPOD_API_KEY`, `GPU_TYPE`, `GPU_COUNT`
- **Model Settings**: `MODEL_NAME`, `NUM_INFERENCE_STEPS`, `TRUE_CFG_SCALE`

## Local Development

### Prerequisites
- Python 3.10+
- NVIDIA GPU with CUDA support (optional but recommended)
- Docker (for containerization)

### Installation
```bash
cd diffusion
pip install -r requirements_server.txt
```

### Run Locally
```bash
# With .env file configured
python qwen_server.py
```

## Docker Deployment

### Build Docker Image
```bash
cd diffusion
docker build -t qwen-image-generator .
```

### Run Docker Container
```bash
# Using docker-compose (recommended, loads .env automatically)
docker-compose up

# Or using docker run with env file
docker run -p 8080:8080 --gpus all --env-file .env qwen-image-generator
```

## Automated CI/CD with GitHub Actions

### Automatic Builds
The repository includes GitHub Actions workflows that automatically build and push Docker images to GHCR:

1. **On Push to Main**: Automatically builds and tags as `latest`
2. **On Release**: Builds multi-platform images with version tags
3. **On Pull Request**: Tests the build without pushing
4. **Manual Dispatch**: Trigger builds manually with custom tags

### Using Pre-built Images
Instead of building locally, you can use the pre-built images from GHCR:
```bash
# Pull the latest image
docker pull ghcr.io/cvkitio/video-synthesizer-qwen:latest

# Run with your .env file
docker run -p 8080:8080 --gpus all --env-file .env ghcr.io/cvkitio/video-synthesizer-qwen:latest
```

### Workflow Files
- `.github/workflows/docker-build-push.yml` - Main build and push workflow
- `.github/workflows/release.yml` - Release workflow with multi-platform support
- `.github/workflows/test-build.yml` - PR testing workflow

### Manual Workflow Trigger
You can manually trigger a build from the GitHub Actions tab:
1. Go to Actions tab in your repository
2. Select "Build and Push Docker Image to GHCR"
3. Click "Run workflow"
4. Optionally specify a custom version tag

## Deploy to GitHub Container Registry (GHCR)

### Setup
1. Create a GitHub Personal Access Token with `write:packages` permission
2. Configure in `.env` file:
```bash
GITHUB_USERNAME=your-github-username
GITHUB_TOKEN=your-github-token
```

### Manual Push to GHCR
For manual deployment without GitHub Actions:
```bash
cd diffusion
./push_to_ghcr.sh
```

Or with a specific version:
```bash
VERSION=1.0.0 ./push_to_ghcr.sh
```

**Note**: GitHub Actions will automatically handle this on push to main branch.

## Deploy to RunPod

### Prerequisites
1. RunPod account and API key
2. Configure in `.env` file:
```bash
RUNPOD_API_KEY=your-runpod-api-key
GITHUB_USERNAME=your-github-username
GPU_TYPE=NVIDIA RTX A4000  # or your preferred GPU
```

### Deploy
```bash
cd diffusion
./deploy_to_runpod.sh
```

This will create configuration files and provide multiple deployment options:
- RunPod CLI deployment
- Direct API deployment
- Python script deployment

### Using the Python Deployment Script
```bash
pip install runpod python-dotenv
python deploy_runpod.py
```

### RunPod URL Format
When a pod is deployed, it will be accessible via RunPod's proxy service:
```
http://{POD_ID}-8080.proxy.runpod.net/
```

For example, if your pod ID is `zwi3zrty402ecv`, the URLs will be:
- **API Base**: `http://zwi3zrty402ecv-8080.proxy.runpod.net/`
- **Health Check**: `http://zwi3zrty402ecv-8080.proxy.runpod.net/health`
- **Generate Images**: `http://zwi3zrty402ecv-8080.proxy.runpod.net/generate`

## GPU Requirements
- Minimum: NVIDIA GPU with 8GB VRAM
- Recommended: NVIDIA RTX A4000 or better
- CUDA 12.8+ compatible (updated from deprecated 12.1.0)
- Docker image uses `nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04`

## Security Notes
- Never commit AWS credentials to version control
- Use environment variables or secrets management for production
- Consider using IAM roles when deploying on AWS
- Implement rate limiting for production deployments

## Troubleshooting

### Out of Memory Errors
- Reduce `num_inference_steps`
- Use smaller image resolutions
- Ensure GPU has sufficient VRAM

### S3 Upload Failures
- Verify AWS credentials
- Check S3 bucket permissions
- Ensure bucket exists in specified region

### Model Loading Issues
- First run will download the model (several GB)
- Ensure sufficient disk space
- Check internet connectivity for Hugging Face model download