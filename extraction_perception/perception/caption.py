import json
import math
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
        print(f"Using device: {self.device}")
        self.default_batch_size = 8 if self.device == "cuda" else 2

        self.processor: Any = cast(Any, BlipProcessor).from_pretrained(model_name)
        self.model: Any = cast(Any, BlipForConditionalGeneration).from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def caption_from_metadata(self, metadata_path: str, output_path: str, batch_size: int | None = None):
        metadata_path_obj = Path(metadata_path)

        with open(metadata_path_obj, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        results = []
        frames = metadata["frames"]
        effective_batch_size = max(1, int(batch_size or self.default_batch_size))

        for chunk_start in tqdm(range(0, len(frames), effective_batch_size), desc="Captioning"):
            batch = frames[chunk_start : chunk_start + effective_batch_size]
            captions = self._caption_batch(metadata_path_obj.parent, batch, effective_batch_size)
            for frame_info, caption in zip(batch, captions):
                results.append(
                    {
                        "frame_id": int(frame_info.get("frame_id", 0)),
                        "timestamp": frame_info["timestamp"],
                        "caption": caption,
                    }
                )

        if any(
            (_to_ms(results[i]["timestamp"]), int(results[i]["frame_id"]))
            > (_to_ms(results[i + 1]["timestamp"]), int(results[i + 1]["frame_id"]))
            for i in range(len(results) - 1)
        ):
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

        print(f"Saved captions to {output_path}")
        return normalized_results

    def _caption_batch(self, base_dir: Path, frame_batch: list[dict[str, Any]], batch_size: int) -> list[str]:
        current_batch_size = max(1, int(batch_size))
        while True:
            try:
                captions: list[str] = []
                for chunk_start in range(0, len(frame_batch), current_batch_size):
                    chunk = frame_batch[chunk_start : chunk_start + current_batch_size]
                    images = []
                    for frame_info in chunk:
                        image_path = base_dir / str(frame_info["file_path"])
                        with Image.open(image_path) as img:
                            images.append(img.convert("RGB"))

                    inputs = self.processor(images=images, return_tensors="pt", padding=True).to(self.device)
                    with torch.inference_mode():
                        if self.device == "cuda":
                            with torch.autocast(device_type="cuda", dtype=torch.float16):
                                output = self.model.generate(**inputs, max_new_tokens=30)
                        else:
                            output = self.model.generate(**inputs, max_new_tokens=30)

                    decoded = self.processor.batch_decode(output, skip_special_tokens=True)
                    captions.extend([x.strip() for x in decoded])

                return captions
            except RuntimeError as exc:
                message = str(exc).lower()
                if "out of memory" not in message or current_batch_size == 1:
                    raise
                if self.device == "cuda":
                    torch.cuda.empty_cache()
                current_batch_size = max(1, math.floor(current_batch_size / 2))
