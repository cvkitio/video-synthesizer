#!/usr/bin/env python3
"""
RunPod GPU Query Script

This script queries RunPod to list all available GPU types with their pricing and availability.
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
    # Load environment variables from .env file
    load_dotenv()
    
    api_key = os.getenv("RUNPOD_API_KEY")
    if not api_key:
        print("Error: RUNPOD_API_KEY not set in .env file or environment")
        print("Please set RUNPOD_API_KEY in your .env file")
        sys.exit(1)
    
    runpod.api_key = api_key
    
    print("🔍 Querying RunPod for available GPUs...")
    print("=" * 80)
    
    try:
        # Get all available GPUs
        gpus = runpod.get_gpus()
        
        if not gpus:
            print("No GPUs available at the moment.")
            return
        
        # Filter GPUs with > 24GB VRAM and sort by VRAM descending
        high_vram_gpus = [gpu for gpu in gpus if gpu.get('memoryInGb', 0) > 24]
        sorted_gpus = sorted(high_vram_gpus, key=lambda x: x.get('memoryInGb', 0), reverse=True)
        
        print(f"\n📊 Found {len(sorted_gpus)} GPU types with >24GB VRAM:\n")
        
        # Print header
        print(f"{'GPU Name':<30} {'VRAM':<10} {'GPU ID':<40}")
        print("-" * 80)
        
        # Print each GPU
        for gpu in sorted_gpus:
            name = gpu.get('displayName', 'Unknown')[:29]
            vram = f"{gpu.get('memoryInGb', 0)} GB"
            gpu_id = gpu.get('id', 'N/A')[:39]
            
            print(f"{name:<30} {vram:<10} {gpu_id:<40}")
        
        print("\n" + "=" * 80)
        print("\n📝 Detailed information for high-VRAM GPUs:\n")
        
        # Show detailed info for all high-VRAM GPUs
        for i, gpu in enumerate(sorted_gpus, 1):
            print(f"{i}. {gpu.get('displayName', 'Unknown')}")
            print(f"   Full ID: {gpu.get('id', 'N/A')}")
            print(f"   VRAM: {gpu.get('memoryInGb', 0)} GB")
            print()
        
        # Find specific GPU types mentioned in .env
        current_gpu = os.getenv("GPU_TYPE", "NVIDIA GeForce RTX 4090")
        print(f"\n🎯 Looking for configured GPU: {current_gpu}")
        
        # Search for exact matches or partial matches
        exact_match = None
        partial_matches = []
        
        for gpu in sorted_gpus:
            display_name = gpu.get('displayName', '')
            gpu_id = gpu.get('id', '')
            
            # Check for exact match
            if gpu_id == current_gpu:
                exact_match = gpu
                break
            # Check for partial matches in display name
            elif current_gpu.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "").lower() in display_name.lower():
                partial_matches.append(gpu)
        
        if exact_match:
            print(f"✅ Found exact match:")
            print(f"   - {exact_match.get('displayName')} ({exact_match.get('memoryInGb')} GB)")
            print(f"     ID: {exact_match.get('id')}")
        elif partial_matches:
            print(f"🔍 Found {len(partial_matches)} partial match(es):")
            for gpu in partial_matches:
                print(f"   - {gpu.get('displayName')} ({gpu.get('memoryInGb')} GB)")
                print(f"     ID: {gpu.get('id')}")
        else:
            print(f"⚠️  No match found for '{current_gpu}'")
            if sorted_gpus:
                print("   Available high-VRAM alternatives:")
                for gpu in sorted_gpus[:3]:
                    print(f"   - {gpu.get('displayName')} ({gpu.get('memoryInGb')} GB)")
                    print(f"     ID: {gpu.get('id')}")
            else:
                print("   No GPUs with >24GB VRAM available")
        
        # Save high-VRAM GPU list to file for reference
        output_file = "runpod_high_vram_gpus.json"
        with open(output_file, 'w') as f:
            json.dump(sorted_gpus, f, indent=2)
        print(f"\n💾 High-VRAM GPU list (>24GB) saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error querying GPUs: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()