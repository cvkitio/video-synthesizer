#!/bin/bash

set -e

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Set defaults if not provided in .env
GITHUB_USERNAME=${GITHUB_USERNAME:-"your-github-username"}
GITHUB_TOKEN=${GITHUB_TOKEN:-""}
IMAGE_NAME=${IMAGE_NAME:-"qwen-image-generator"}
VERSION=${VERSION:-"latest"}

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set"
    echo "Please set it with: export GITHUB_TOKEN=your_github_token"
    exit 1
fi

REGISTRY="ghcr.io"
IMAGE_TAG="${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "Logging into GitHub Container Registry..."
echo "${GITHUB_TOKEN}" | docker login ${REGISTRY} -u ${GITHUB_USERNAME} --password-stdin

echo "Building Docker image..."
docker build -t ${IMAGE_NAME}:${VERSION} .

echo "Tagging image for GHCR..."
docker tag ${IMAGE_NAME}:${VERSION} ${IMAGE_TAG}

echo "Pushing image to GHCR..."
docker push ${IMAGE_TAG}

echo "Successfully pushed ${IMAGE_TAG}"

if [ "$VERSION" != "latest" ]; then
    LATEST_TAG="${REGISTRY}/${GITHUB_USERNAME}/${IMAGE_NAME}:latest"
    echo "Also tagging and pushing as latest..."
    docker tag ${IMAGE_NAME}:${VERSION} ${LATEST_TAG}
    docker push ${LATEST_TAG}
    echo "Successfully pushed ${LATEST_TAG}"
fi

echo "Done! Image is available at: ${IMAGE_TAG}"