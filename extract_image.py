#!/usr/bin/env python3
"""
Extract image from runpod_response.json
"""

import json
import base64
from pathlib import Path

def extract_image_from_json(json_file_path, output_dir="extracted_images"):
    """
    Extract base64 encoded images from runpod response JSON file
    
    Args:
        json_file_path (str): Path to the JSON file
        output_dir (str): Directory to save extracted images
    """
    try:
        # Read the JSON file
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(exist_ok=True)
        
        # Extract images from the output section
        if 'output' in data and 'images' in data['output']:
            images = data['output']['images']
            
            for i, base64_image in enumerate(images):
                try:
                    # Decode the base64 image
                    image_data = base64.b64decode(base64_image)
                    
                    # Save the image
                    output_path = Path(output_dir) / f"image_{i+1}.png"
                    with open(output_path, 'wb') as img_file:
                        img_file.write(image_data)
                    
                    print(f"Extracted image {i+1} to: {output_path}")
                    
                except Exception as e:
                    print(f"Error decoding image {i+1}: {e}")
            
            print(f"\nTotal images extracted: {len(images)}")
            
        else:
            print("No images found in the JSON file")
            
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {json_file_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Path to the runpod response JSON file
    json_file = "runpod/runpod_response.json"
    
    # Extract images
    extract_image_from_json(json_file)