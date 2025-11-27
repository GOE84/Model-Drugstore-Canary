from transformers import AutoModelForImageTextToText, AutoProcessor
from PIL import Image
import torch
import os

model_id = "google/medgemma-4b-it"

print(f"Loading model: {model_id}...")
try:
    processor = AutoProcessor.from_pretrained(model_id)
    # Determine device and dtype
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        dtype = torch.bfloat16  # Better numerical stability than float16
        print("Using MPS (Metal Performance Shaders) acceleration with bfloat16.")
    else:
        device = torch.device("cpu")
        dtype = torch.float32
        print("Using CPU (MPS not available).")

    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        device_map=None,
        torch_dtype=dtype
    ).to(device)
    print("Model loaded. Moving to device...")
    print("Model and processor loaded successfully.")
except Exception as e:
    print(f"Failed to load model/processor: {e}")
    exit(1)

print("Inference setup...")

import sys

# Image handling
image_path = None

# 1. Check command line arguments
if len(sys.argv) > 1:
    image_path = sys.argv[1]

# 2. If not provided, ask user
if not image_path:
    print("Enter path to X-ray image (leave empty to check for 'xray_sample.jpg' or run text-only):")
    user_input = input("Image path: ").strip()
    if user_input:
        image_path = user_input

# 3. Fallback to default
if not image_path:
    image_path = "xray_sample.jpg"

if not os.path.exists(image_path):
    if image_path != "xray_sample.jpg": # Only warn if user specifically provided a path or we defaulted and it's missing
        print(f"Warning: Image file '{image_path}' not found.")
    image = None
else:
    try:
        image = Image.open(image_path)
        print(f"Loaded image: {image_path}")
    except Exception as e:
        print(f"Error loading image: {e}")
        image = None

# Prompt
if image:
    # Gemma chat template
    image_token = "<image_soft_token>"
    num_image_tokens = 256
    
    # Construct prompt with chat template
    user_prompt = "Analyze this X-ray and summarize the findings."
    input_text = f"<start_of_turn>user\n{image_token * num_image_tokens}\n{user_prompt}<end_of_turn>\n<start_of_turn>model\n"
    
    # Manually assemble inputs to bypass processor validation bug
    try:
        # Process image
        image_inputs = processor.image_processor(images=image, return_tensors="pt")
        pixel_values = image_inputs.pixel_values.to(model.device, dtype=model.dtype)
        
        # Process text
        text_inputs = processor.tokenizer(input_text, return_tensors="pt")
        input_ids = text_inputs.input_ids.to(model.device)
        attention_mask = text_inputs.attention_mask.to(model.device)
        
        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "pixel_values": pixel_values
        }
        # Add other keys if present
        # if hasattr(image_inputs, "num_crops"):
        #      inputs["num_crops"] = image_inputs.num_crops.to(model.device)

    except Exception as e:
        print(f"Error processing inputs: {e}")
        exit(1)
else:
    print("Running in text-only mode (no image found).")
    input_text = "What are the common symptoms of influenza?"
    inputs = processor(text=input_text, return_tensors="pt").to(model.device)

print("Generating...")
outputs = model.generate(**inputs, max_new_tokens=200)
print(f"DEBUG: Output shape: {outputs.shape}")
print(f"DEBUG: Output tokens: {outputs[0].tolist()}")
decoded_text = processor.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
print(f"DEBUG: Decoded text: '{decoded_text}'")
print(decoded_text)
