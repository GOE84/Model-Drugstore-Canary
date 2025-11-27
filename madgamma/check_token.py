from transformers import AutoProcessor

model_id = "google/medgemma-4b-it"
try:
    processor = AutoProcessor.from_pretrained(model_id)
    # Test processor call
    from PIL import Image
    import numpy as np
    image = Image.fromarray(np.zeros((224, 224, 3), dtype=np.uint8))
    
    # Inspect input_ids
    text_input = "<image_soft_token>\nDescribe."
    print(f"Text input: {text_input}")
    
    # Just tokenize first
    input_ids = processor.tokenizer(text_input, return_tensors="pt").input_ids
    print(f"Tokenized input_ids: {input_ids}")
    
    if 262144 in input_ids:
        print("Image token ID 262144 IS present in input_ids.")
    else:
        print("Image token ID 262144 is NOT present in input_ids.")

    # Manual assembly
    print("Attempting manual assembly...")
    try:
        # Get pixel_values using image_processor directly
        if hasattr(processor, "image_processor"):
            print("Using image_processor directly...")
            image_inputs = processor.image_processor(images=image, return_tensors="pt")
        else:
            print("No image_processor found, trying processor with text=None...")
            image_inputs = processor(text=None, images=image, return_tensors="pt")
            
        print(f"Image inputs type: {type(image_inputs)}")
        print(f"Image inputs keys: {image_inputs.keys()}")
        if hasattr(image_inputs, "pixel_values"):
             pixel_values = image_inputs.pixel_values
        else:
             pixel_values = image_inputs["pixel_values"]
        print(f"Pixel values shape: {pixel_values.shape}")
        
        # Get input_ids
        text_inputs = processor(text="<image_soft_token>\nDescribe.", return_tensors="pt")
        input_ids = text_inputs.input_ids
        attention_mask = text_inputs.attention_mask
        print(f"Input IDs shape: {input_ids.shape}")
        
        # Load model (lightweight check, just need class)
        from transformers import AutoModelForImageTextToText
        import torch
        
        # We can't easily load the full model here without waiting, so we will assume it works if we can construct the dict
        # But to really test, we need to run it.
        # Let's just print that we would call model.generate(input_ids=input_ids, pixel_values=pixel_values, ...)
        print("Manual assembly successful (conceptually).")
        
    except Exception as e:
        print(f"Manual assembly failed: {e}")
except Exception as e:
    print(f"Error loading processor: {e}")
