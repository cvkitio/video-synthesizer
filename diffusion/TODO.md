OK so this builds and deploys to runpod and now runs but is getting an error for out of memory, possibly needs the CPU fallback option or similar

Error is
NVIDIA GeForce RTX 5090 with CUDA capability sm_120 is not compatible with the current PyTorch installation.
The current PyTorch install supports CUDA capabilities sm_50 sm_60 sm_70 sm_75 sm_80 sm_86 sm_90.
If you want to use the NVIDIA GeForce RTX 5090 GPU with PyTorch, please check the instructions at https://pytorch.org/get-started/locally/
  warnings.warn(
Traceback (most recent call last):
  File "/app/qwen_server.py", line 156, in <module>
    initialize_model()
  File "/app/qwen_server.py", line 37, in initialize_model
    pipe = pipe.to(device)
  File "/usr/local/lib/python3.10/dist-packages/diffusers/pipelines/pipeline_utils.py", line 541, in to
    module.to(device, dtype)
  File "/usr/local/lib/python3.10/dist-packages/diffusers/models/modeling_utils.py", line 1446, in to
    return super().to(*args, **kwargs)
  File "/usr/local/lib/python3.10/dist-packages/torch/nn/modules/module.py", line 1340, in to
    return self._apply(convert)
  File "/usr/local/lib/python3.10/dist-packages/torch/nn/modules/module.py", line 900, in _apply
    module._apply(fn)
  File "/usr/local/lib/python3.10/dist-packages/torch/nn/modules/module.py", line 900, in _apply
    module._apply(fn)
  File "/usr/local/lib/python3.10/dist-packages/torch/nn/modules/module.py", line 900, in _apply
    module._apply(fn)
  [Previous line repeated 2 more times]
  File "/usr/local/lib/python3.10/dist-packages/torch/nn/modules/module.py", line 927, in _apply
    param_applied = fn(param)
  File "/usr/local/lib/python3.10/dist-packages/torch/nn/modules/module.py", line 1326, in convert
    return t.to(
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 72.00 MiB. GPU 0 has a total capacity of 31.37 GiB of which 25.81 MiB is free. Including non-PyTorch memory, this process has 31.33 GiB memory in use. Of the allocated memory 30.66 GiB is allocated by PyTorch, and 197.30 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)

- [ ] When the application starts it has to download a number of large models, investigate whether it will be faster to store these locally on a network share or add to the image