import json
import torch
from pathlib import Path
from typing import Any, cast
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from tqdm import tqdm


def _to_ms(ts: str) -> int:
    hh = int(ts[0:2])
    mm = int(ts[3:5])
    ss = int(ts[6:8])
    ms = int(ts[9:12])
    return (((hh * 60) + mm) * 60 + ss) * 1000 + ms


class VisualCaptioner:
    def __init__(self, model_name="Salesforce/blip-image-captioning-base"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 Using device: {self.device}")

        self.processor: Any = cast(Any, BlipProcessor).from_pretrained(model_name)
        self.model: Any = cast(Any, BlipForConditionalGeneration).from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def caption_from_metadata(self, metadata_path: str, output_path: str):
        metadata_path_obj = Path(metadata_path)

        with open(metadata_path_obj, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        results = []

        for frame_info in tqdm(metadata["frames"], desc="Captioning"):
            image_path = metadata_path_obj.parent / frame_info["file_path"]
            timestamp = frame_info["timestamp"]
            frame_id = int(frame_info.get("frame_id", 0))

            caption = self._caption_image(image_path)

            results.append({
                "frame_id": frame_id,
                "timestamp": timestamp,
                "caption": caption
            })

        results.sort(key=lambda item: (_to_ms(item["timestamp"]), item["frame_id"]))

        normalized_results = [
            {
                "timestamp": item["timestamp"],
                "caption": item["caption"],
            }
            for item in results
        ]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(normalized_results, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved captions to {output_path}")
        return normalized_results

    def _caption_image(self, image_path: Path):
        image = Image.open(image_path).convert("RGB")

        inputs = self.processor(image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=30)

        caption = self.processor.decode(output[0], skip_special_tokens=True)
        return caption
