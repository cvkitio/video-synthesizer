FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /app

COPY requirements_server.txt .
RUN pip install --no-cache-dir -r requirements_server.txt

COPY qwen_server.py .
# Copy .env file if you want to bake it into the image (optional, not recommended for production)
# COPY .env .

ENV PORT=8080
ENV TRANSFORMERS_CACHE=/app/cache
ENV HF_HOME=/app/cache

RUN mkdir -p /app/cache

EXPOSE 8080

CMD ["python", "qwen_server.py"]