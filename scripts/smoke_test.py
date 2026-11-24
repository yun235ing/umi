"""Run the original ArUco and replay-buffer scripts on one synthetic clip."""

import os
import pickle
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import zarr
from exiftool import ExifToolHelper
from skfda.exploratory.stats import geometric_median


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream" / "universal_manipulation_interface"
FRAME_COUNT = 12
TAG_ID = 13


def create_clip(video_path: Path) -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, TAG_ID, 100)
    frame = np.full((480, 640), 238, dtype=np.uint8)
    frame[190:290, 270:370] = marker

    image_path = video_path.parents[2] / "marker.png"
    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"Could not write {image_path}")
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error", "-loop", "1", "-framerate", "12",
            "-i", image_path, "-frames:v", str(FRAME_COUNT), "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-metadata", "creation_time=2026-01-02T00:00:00Z",
            "-timecode", "00:00:01:00", video_path,
        ],
        check=True,
    )


def run_upstream(script: str, *args: str | Path) -> None:
    subprocess.run([sys.executable, UPSTREAM / script, *args], cwd=UPSTREAM, check=True)


def main() -> None:
    sys.path.insert(0, str(UPSTREAM))
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]
    from diffusion_policy.codecs.imagecodecs_numcodecs import register_codecs
    from umi.common.timecode_util import mp4_get_start_datetime

    register_codecs()
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    np.testing.assert_allclose(geometric_median(points), [1.0, 0.0, 0.0])

    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    session = Path(tempfile.mkdtemp(prefix="smoke-", dir=runs))
    print(f"Smoke-test files: {session}", flush=True)
    demos = session / "demos"
    clip_relative = Path("demo_synthetic") / "raw_video.mp4"
    video = demos / clip_relative
    video.parent.mkdir(parents=True)
    create_clip(video)

    with ExifToolHelper() as exiftool:
        metadata = exiftool.get_metadata(str(video))[0]
    assert metadata["File:FileType"] == "MP4"
    assert mp4_get_start_datetime(str(video)) == datetime(2026, 1, 2, 0, 0, 1)

    calibration = UPSTREAM / "example" / "calibration"
    run_upstream(
        "scripts_slam_pipeline/04_detect_aruco.py",
        "-i", demos, "-ci", calibration / "gopro_intrinsics_2_7k.json",
        "-ac", calibration / "aruco_config.yaml", "-n", "1",
    )
    with video.with_name("tag_detection.pkl").open("rb") as tags_file:
        detections = pickle.load(tags_file)
    assert [frame["frame_idx"] for frame in detections] == list(range(FRAME_COUNT))
    assert all(TAG_ID in frame["tag_dict"] for frame in detections)
    assert np.isfinite(detections[0]["tag_dict"][TAG_ID]["tvec"]).all()

    # Stage 07 consumes the schema written by stage 06. These poses are synthetic.
    poses = np.zeros((FRAME_COUNT, 6), dtype=np.float32)
    poses[:, 0] = np.linspace(0.0, 0.11, FRAME_COUNT)
    widths = np.linspace(0.06, 0.02, FRAME_COUNT, dtype=np.float32)
    plan = [{
        "grippers": [{
            "tcp_pose": poses,
            "gripper_width": widths,
            "demo_start_pose": poses[0],
            "demo_end_pose": poses[-1],
        }],
        "cameras": [{"video_path": str(clip_relative), "video_start_end": (0, FRAME_COUNT)}],
    }]
    with (session / "dataset_plan.pkl").open("wb") as plan_file:
        pickle.dump(plan, plan_file)

    output = session / "dataset.zarr.zip"
    run_upstream(
        "scripts_slam_pipeline/07_generate_replay_buffer.py",
        "-o", output, "-or", "64,64", "-cl", "85", "-n", "1", session,
    )
    with zarr.ZipStore(str(output), mode="r") as store:
        root = zarr.open_group(store=store, mode="r")
        np.testing.assert_array_equal(root["meta/episode_ends"][:], [FRAME_COUNT])
        np.testing.assert_allclose(root["data/robot0_eef_pos"][:], poses[:, :3])
        np.testing.assert_allclose(root["data/robot0_gripper_width"][:, 0], widths)
        rgb = root["data/camera0_rgb"][:]
        assert rgb.shape == (FRAME_COUNT, 64, 64, 3) and rgb.dtype == np.uint8
        assert np.all(np.ptp(rgb, axis=(1, 2, 3)) > 0)

    print(f"PASS: ArUco ID {TAG_ID} detected in {FRAME_COUNT} frames")
    print(f"PASS: Zarr episode, positions, widths and RGB decoded from {output}")


if __name__ == "__main__":
    main()
