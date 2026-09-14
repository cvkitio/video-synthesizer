#!/usr/bin/env python3
"""
Find RunPod GPU ID for deployment

Search for a specific GPU and show the exact ID needed for deployment.
"""

import os
import sys
import json
from dotenv import load_dotenv

try:
    import runpod
except ImportError:
    print("RunPod SDK not installed. Install with: pip install runpod")
    sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print("Usage: python find_gpu_id.py 'GPU_NAME'")
        print("Example: python find_gpu_id.py 'RTX 4090'")
        sys.exit(1)
    
    search_term = sys.argv[1].lower()
    
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("RUNPOD_API_KEY")
    if not api_key:
        print("❌ RUNPOD_API_KEY not set in .env file")
        sys.exit(1)
    
    runpod.api_key = api_key
    
    print(f"🔍 Searching for GPU: '{search_term}'")
    print("=" * 60)
    
    try:
        gpus = runpod.get_gpus()
        matches = []
        
        for gpu in gpus:
            display_name = gpu.get('displayName', '').lower()
            gpu_id = gpu.get('id', '').lower()
            
            if search_term in display_name or search_term in gpu_id:
                matches.append(gpu)
        
        if not matches:
            print(f"❌ No GPUs found matching '{search_term}'")
            print("\nAvailable GPUs:")
            for gpu in sorted(gpus, key=lambda x: x.get('displayName', ''))[:10]:
                print(f"   - {gpu.get('displayName')}")
            return
        
        print(f"✅ Found {len(matches)} matching GPU(s):\n")
        
        for i, gpu in enumerate(matches, 1):
            name = gpu.get('displayName', 'Unknown')
            gpu_id = gpu.get('id', 'N/A')
            vram = gpu.get('memoryInGb', 0)
            available = gpu.get('maxGpuCount', 0)
            secure_price = gpu.get('securePrice', 0)
            
            print(f"{i}. {name}")
            print(f"   GPU ID: '{gpu_id}'")
            print(f"   VRAM: {vram} GB")
            print(f"   Available: {available} units")
            print(f"   Price: ${secure_price:.3f}/hr (Secure)")
            
            # Show .env configuration
            print(f"\n   📝 To use this GPU, set in .env:")
            print(f'   GPU_TYPE="{gpu_id}"')
            print()
        
        # Show update command
        if matches:
            best_match = matches[0]
            gpu_id = best_match.get('id', '')
            print(f"🚀 Quick update command:")
            print(f"   sed -i '' 's/GPU_TYPE=.*/GPU_TYPE=\"{gpu_id}\"/' .env")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()