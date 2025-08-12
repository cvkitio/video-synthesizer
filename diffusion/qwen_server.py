from diffusers import DiffusionPipeline
import torch
import io
import os
import logging
import uuid
from flask import Flask, request, jsonify
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

model_name = os.getenv('MODEL_NAME', 'Qwen/Qwen-Image')
pipe = None

def initialize_model():
    global pipe
    if torch.cuda.is_available():
        torch_dtype = torch.bfloat16
        device = "cuda"
        logger.info("Using CUDA GPU")
    else:
        torch_dtype = torch.float32
        device = "cpu"
        logger.info("Using CPU")
    
    logger.info(f"Loading model: {model_name}")
    pipe = DiffusionPipeline.from_pretrained(model_name, torch_dtype=torch_dtype)
    pipe = pipe.to(device)
    logger.info("Model loaded successfully")

def upload_to_s3(image, s3_bucket, s3_key, aws_access_key_id, aws_secret_access_key, aws_region='us-east-1'):
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        s3_client.upload_fileobj(
            img_byte_arr,
            s3_bucket,
            s3_key,
            ExtraArgs={'ContentType': 'image/png'}
        )
        
        s3_url = f"https://{s3_bucket}.s3.{aws_region}.amazonaws.com/{s3_key}"
        logger.info(f"Image uploaded successfully to: {s3_url}")
        return s3_url
        
    except ClientError as e:
        logger.error(f"Error uploading to S3: {e}")
        raise

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "model": model_name}), 200

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        data = request.json
        
        # Check if S3 credentials are provided in request, otherwise use environment variables
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({"error": "Missing required field: prompt"}), 400
        
        # Use environment variables as defaults if not provided in request
        s3_bucket = data.get('s3_bucket', os.getenv('S3_BUCKET'))
        aws_access_key_id = data.get('aws_access_key_id', os.getenv('AWS_ACCESS_KEY_ID'))
        aws_secret_access_key = data.get('aws_secret_access_key', os.getenv('AWS_SECRET_ACCESS_KEY'))
        aws_region = data.get('aws_region', os.getenv('AWS_REGION', 'us-east-1'))
        
        # Validate S3 configuration
        if not all([s3_bucket, aws_access_key_id, aws_secret_access_key]):
            return jsonify({
                "error": "S3 configuration missing. Provide in request or set in environment variables"
            }), 400
        
        negative_prompt = data.get('negative_prompt', 'ugly, deformed, disfigured, poor details, bad anatomy')
        positive_magic = data.get('positive_magic', 'Ultra HD, 4K, cinematic composition.')
        aspect_ratio = data.get('aspect_ratio', '16:9')
        num_inference_steps = data.get('num_inference_steps', int(os.getenv('NUM_INFERENCE_STEPS', 50)))
        true_cfg_scale = data.get('true_cfg_scale', float(os.getenv('TRUE_CFG_SCALE', 4.0)))
        seed = data.get('seed', int(os.getenv('DEFAULT_SEED', 42)))
        
        aspect_ratios = {
            "1:1": (1328, 1328),
            "16:9": (1024, 768),
            "9:16": (928, 1664),
            "4:3": (1472, 1140),
            "3:4": (1140, 1472),
            "3:2": (1584, 1056),
            "2:3": (1056, 1584),
        }
        
        if aspect_ratio not in aspect_ratios:
            return jsonify({"error": f"Invalid aspect ratio. Choose from: {list(aspect_ratios.keys())}"}), 400
        
        width, height = aspect_ratios[aspect_ratio]
        
        logger.info(f"Generating image with prompt: {prompt[:100]}...")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        image = pipe(
            prompt=prompt + " " + positive_magic,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            true_cfg_scale=true_cfg_scale,
            generator=torch.Generator(device=device).manual_seed(seed)
        ).images[0]
        
        image_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_key = data.get('s3_key', f"generated_images/{timestamp}_{image_id}.png")
        
        s3_url = upload_to_s3(image, s3_bucket, s3_key, aws_access_key_id, aws_secret_access_key, aws_region)
        
        return jsonify({
            "success": True,
            "image_url": s3_url,
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "metadata": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "aspect_ratio": aspect_ratio,
                "width": width,
                "height": height,
                "seed": seed,
                "timestamp": timestamp
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    initialize_model()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)