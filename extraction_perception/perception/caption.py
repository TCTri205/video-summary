import json
import torch
from pathlib import Path
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from tqdm import tqdm


class VisualCaptioner:
    def __init__(self, model_name="Salesforce/blip-image-captioning-base"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 Using device: {self.device}")

        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForConditionalGeneration.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def caption_from_metadata(self, metadata_path: str, output_path: str):
        metadata_path = Path(metadata_path)

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        results = []

        for frame_info in tqdm(metadata["frames"], desc="Captioning"):
            image_path = metadata_path.parent / frame_info["file_path"]
            timestamp = frame_info["timestamp"]

            caption = self._caption_image(image_path)

            results.append({
                "timestamp": timestamp,
                "caption": caption
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved captions to {output_path}")
        return results

    def _caption_image(self, image_path: Path):
        image = Image.open(image_path).convert("RGB")

        inputs = self.processor(image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=30)

        caption = self.processor.decode(output[0], skip_special_tokens=True)
        return caption
