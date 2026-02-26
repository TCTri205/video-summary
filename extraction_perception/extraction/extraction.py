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

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("EXTRACT_AUDIO_FFMPEG_NOT_FOUND: ffmpeg binary is not available in PATH") from exc

        if result.returncode != 0:
            err = (result.stderr or "").strip()
            raise RuntimeError(f"EXTRACT_AUDIO_FFMPEG_FAILED: {err}")

        if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) == 0:
            raise RuntimeError("EXTRACT_AUDIO_EMPTY_OUTPUT: ffmpeg completed but output audio is missing or empty")

        return self.audio_path

    def extract_keyframes_and_metadata(self, timestamps):
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)

        frames_metadata = []

        targets = []
        for idx, ts in enumerate(timestamps):
            targets.append((idx, float(ts), int(float(ts) * fps)))

        monotonic = True
        prev_frame_no = -1
        for _, _, frame_no in targets:
            if frame_no < prev_frame_no:
                monotonic = False
                break
            prev_frame_no = frame_no

        if monotonic:
            frames_map = self._extract_frames_sequential(cap, targets)
        else:
            frames_map = self._extract_frames_random_seek(cap, targets)

        for idx, ts, _ in targets:
            frame = frames_map.get(idx)

            if frame is None:
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

    def _extract_frames_sequential(self, cap, targets):
        result = {}
        target_pos = 0
        frame_cursor = 0

        while target_pos < len(targets):
            success, frame = cap.read()
            if not success:
                break

            target_idx, _, target_frame = targets[target_pos]
            if frame_cursor >= target_frame:
                result[target_idx] = frame
                target_pos += 1

            frame_cursor += 1

        return result

    def _extract_frames_random_seek(self, cap, targets):
        result = {}
        for idx, _, frame_number in targets:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            success, frame = cap.read()
            if success:
                result[idx] = frame
        return result

    def _format_timestamp(self, seconds: float):
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        ms = int((seconds - total_seconds) * 1000)

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        return f"{hours:02}:{minutes:02}:{secs:02}.{ms:03}"
