
# Example using a pre-trained GAN (PGAN) from torch.hub
import torch
from torchvision.utils import save_image
import torchvision.transforms as T

# Load pre-trained PGAN (Progressive GAN) from torch.hub
model = torch.hub.load('facebookresearch/pytorch_GAN_zoo:hub', 'PGAN', model_name='celebAHQ-512', pretrained=True)

# Generate a random latent vector
latent_vector = torch.randn(1, model.latent_dim)

# Generate an image
with torch.no_grad():
	generated_img = model.test(latent_vector)

# Convert to PIL Image and save
transform = T.ToPILImage()
image = transform(generated_img[0].cpu())
image.save("generated_celeb.png")