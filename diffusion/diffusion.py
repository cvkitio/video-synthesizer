from diffusers import StableDiffusionPipeline
import torch

# Load the Stable Diffusion pipeline
pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16
)
pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")

# Define your prompt
prompt = "A photo realistic image of a beautiful mountain landscape at sunrise"

# Generate the image
image = pipe(prompt).images[0]

# Save the image
image.save("mountain_landscape.png")