#!/usr/bin/env python3
"""
Quick RunPod GPU Availability Checker

Shows current GPU availability and pricing for deployment planning.
"""

import os
import sys
from dotenv import load_dotenv

try:
    import runpod
except ImportError:
    print("RunPod SDK not installed. Install with: pip install runpod")
    sys.exit(1)

def main():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("RUNPOD_API_KEY")
    if not api_key:
        print("❌ RUNPOD_API_KEY not set in .env file")
        sys.exit(1)
    
    runpod.api_key = api_key
    
    print("🚀 RunPod GPU Quick Check")
    print("=" * 50)
    
    try:
        gpus = runpod.get_gpus()
        
        if not gpus:
            print("❌ No GPU information available")
            return
        
        print(f"📋 Found {len(gpus)} GPU types in RunPod catalog:\n")
        print("🔍 Fetching pricing information for each GPU...\n")
        
        # Filter to high-VRAM GPUs only (>24GB) and sort by VRAM descending
        high_vram_gpus = [gpu for gpu in gpus if gpu.get('memoryInGb', 0) > 24]
        high_vram_gpus.sort(key=lambda x: x.get('memoryInGb', 0), reverse=True)
        
        if not high_vram_gpus:
            print("❌ No GPUs with >24GB VRAM found")
            return
        
        print(f"💰 GPU Pricing Information (>24GB VRAM only):\n")
        print(f"{'GPU Name':<25} {'VRAM':<8} {'Spot $/hr':<12} {'Uninterruptible $/hr':<18} {'Community Cloud':<15}")
        print("-" * 85)
        
        # Get detailed info for each high-VRAM GPU
        for gpu in high_vram_gpus:
            gpu_id = gpu.get('id', 'N/A')
            name = gpu.get('displayName', 'Unknown')[:24]
            vram = f"{gpu.get('memoryInGb', 0)}GB"
            
            try:
                # Get detailed GPU info including pricing
                gpu_details = runpod.get_gpu(gpu_id)
                
                # Extract pricing info
                spot_price = "N/A"
                uninterruptible_price = "N/A"
                community_cloud = "N/A"
                
                if gpu_details:
                    # Get spot prices
                    if 'secureSpotPrice' in gpu_details and gpu_details['secureSpotPrice']:
                        spot_price = f"${gpu_details['secureSpotPrice']:.3f}"
                    elif 'communitySpotPrice' in gpu_details and gpu_details['communitySpotPrice']:
                        spot_price = f"${gpu_details['communitySpotPrice']:.3f}"
                    
                    # Get uninterruptible price
                    if 'lowestPrice' in gpu_details and 'uninterruptablePrice' in gpu_details['lowestPrice']:
                        uninterruptible_price = f"${gpu_details['lowestPrice']['uninterruptablePrice']:.3f}"
                    elif 'communityPrice' in gpu_details and gpu_details['communityPrice']:
                        uninterruptible_price = f"${gpu_details['communityPrice']:.3f}"
                    elif 'securePrice' in gpu_details and gpu_details['securePrice']:
                        uninterruptible_price = f"${gpu_details['securePrice']:.3f}"
                    
                    # Community cloud availability
                    if 'communityCloud' in gpu_details:
                        community_cloud = "Yes" if gpu_details['communityCloud'] else "No"
                
                print(f"{name:<25} {vram:<8} {spot_price:<12} {uninterruptible_price:<18} {community_cloud:<15}")
                
            except Exception as e:
                print(f"{name:<25} {vram:<8} Error fetching pricing: {str(e)[:30]}...")
        
        print()
        
        # Check configured GPU with detailed pricing
        configured_gpu = os.getenv("GPU_TYPE", "NVIDIA GeForce RTX 4090")
        print(f"🎯 Your configured GPU: {configured_gpu}\n")
        
        # Find exact match in all GPUs (not just high-VRAM)
        matching_gpu = None
        for gpu in gpus:
            if gpu.get('id') == configured_gpu:
                matching_gpu = gpu
                break
        
        # If no exact match, try display name match
        if not matching_gpu:
            configured_display = configured_gpu.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
            for gpu in gpus:
                if configured_display.lower() in gpu.get('displayName', '').lower():
                    matching_gpu = gpu
                    break
        
        if matching_gpu:
            name = matching_gpu.get('displayName', 'Unknown')
            vram = matching_gpu.get('memoryInGb', 0)
            gpu_id = matching_gpu.get('id', 'N/A')
            
            print(f"✅ Found matching GPU: {name}")
            print(f"   VRAM: {vram} GB")
            print(f"   Full ID: {gpu_id}")
            
            # Get detailed pricing for configured GPU
            try:
                gpu_details = runpod.get_gpu(gpu_id)
                print(f"\n💰 Pricing for {name}:")
                
                if gpu_details:
                    print(f"   💰 Pricing Details:")
                    if 'secureSpotPrice' in gpu_details and gpu_details['secureSpotPrice']:
                        print(f"      Secure Spot: ${gpu_details['secureSpotPrice']:.3f}/hr")
                    if 'communitySpotPrice' in gpu_details and gpu_details['communitySpotPrice']:
                        print(f"      Community Spot: ${gpu_details['communitySpotPrice']:.3f}/hr")
                    if 'securePrice' in gpu_details and gpu_details['securePrice']:
                        print(f"      Secure Cloud: ${gpu_details['securePrice']:.3f}/hr")
                    if 'communityPrice' in gpu_details and gpu_details['communityPrice']:
                        print(f"      Community Cloud: ${gpu_details['communityPrice']:.3f}/hr")
                    if 'lowestPrice' in gpu_details and 'uninterruptablePrice' in gpu_details['lowestPrice']:
                        print(f"      Lowest Uninterruptible: ${gpu_details['lowestPrice']['uninterruptablePrice']:.3f}/hr")
                    
                    # Show additional pricing tiers if available
                    if 'stockStatus' in gpu_details:
                        stock = gpu_details['stockStatus']
                        print(f"   Stock Status: {stock}")
                    
                    if 'communityCloud' in gpu_details:
                        cc_available = "Yes" if gpu_details['communityCloud'] else "No"
                        print(f"   Community Cloud: {cc_available}")
                        
                else:
                    print(f"   ⚠️  No pricing information available")
                    
            except Exception as e:
                print(f"   ❌ Error fetching pricing: {e}")
            
        else:
            print(f"❌ Could not find {configured_gpu} in GPU catalog")
            print(f"\n🔍 Suggested high-VRAM alternatives:")
            # Show high-VRAM alternatives from our filtered list
            for alt in high_vram_gpus[:3]:
                print(f"   - {alt.get('displayName')} ({alt.get('memoryInGb')} GB)")
        
        print(f"\n💡 To update your GPU selection, edit GPU_TYPE in .env")
        print(f"   Use the exact 'ID' value from the pricing table above.")
        print(f"\n🔍 Note: Prices shown are current lowest available rates.")
        print(f"   Actual availability varies - try deploying to check real-time status.")
        
    except Exception as e:
        print(f"❌ Error querying GPUs: {e}")
        print(f"   Make sure RUNPOD_API_KEY is valid and you have internet connection.")
        sys.exit(1)

if __name__ == "__main__":
    main()