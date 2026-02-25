import os
import json
import subprocess
from datetime import timedelta
from pathlib import Path

import cv2
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

class VideoPreprocessor:
    def __init__(self, video_path: str, output_root: str, resize: int = 448):
        assert resize in [448, 336], "Resize must be 448 or 336"

        self.video_path = video_path
        self.video_name = Path(video_path).stem
        self.resize = resize

        self.video_dir = os.path.join(output_root, self.video_name)
        self.extraction_dir = os.path.join(self.video_dir, "extraction")
        self.keyframe_dir = os.path.join(self.extraction_dir, "keyframes")
        self.audio_dir = os.path.join(self.extraction_dir, "audio")
        self.audio_path = os.path.join(self.audio_dir, "audio_16k.wav")
        self.metadata_path = os.path.join(self.extraction_dir, "scene_metadata.json")

        os.makedirs(self.keyframe_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

    def detect_scenes(self, threshold: float = 27.0):
        # Mở video theo API mới
        video = open_video(self.video_path)

        # Tạo scene manager
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))

        # Detect scene
        scene_manager.detect_scenes(video)

        # Lấy danh sách scene
        scene_list = scene_manager.get_scene_list()

        # Lấy timestamp midpoint của mỗi scene
        timestamps = []
        for scene in scene_list:
            start = scene[0].get_seconds()
            end = scene[1].get_seconds()
            midpoint = (start + end) / 2
            timestamps.append(midpoint)

        return timestamps

    def extract_audio(self):
        command = [
            "ffmpeg",
            "-y",
            "-i", self.video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            self.audio_path
        ]
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return self.audio_path

    def extract_keyframes_and_metadata(self, timestamps):
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)

        frames_metadata = []

        for idx, ts in enumerate(timestamps):
            frame_number = int(ts * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            success, frame = cap.read()

            if not success:
                continue

            # Resize về 448x448 hoặc 336x336
            frame = cv2.resize(frame, (self.resize, self.resize))

            # Format timestamp: HH:MM:SS.mmm
            formatted_ts = self._format_timestamp(ts)

            # File name theo quy ước
            filename = f"frame_{formatted_ts.replace(':', '_').replace('.', '_')}.jpg"
            file_path = os.path.join(self.keyframe_dir, filename)

            cv2.imwrite(file_path, frame)

            frames_metadata.append({
                "frame_id": idx + 1,
                "timestamp": formatted_ts,
                "file_path": f"keyframes/{filename}"
            })

        cap.release()

        metadata = {
            "total_keyframes": len(frames_metadata),
            "frames": frames_metadata
        }

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)

        return metadata

    def _format_timestamp(self, seconds: float):
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        ms = int((seconds - total_seconds) * 1000)

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        return f"{hours:02}:{minutes:02}:{secs:02}.{ms:03}"
