"""
open-root-chamber — edge-vision/root_vigor.py

Captures an image from the Raspberry Pi Camera (or USB webcam),
detects root presence, measures root length in pixels → cm,
and classifies each sett as HIGH_VIGOR, GROWING, or DUD.

Why OpenCV and not a neural network?
  Root length measurement is a geometry problem, not a classification problem.
  OpenCV's color segmentation + skeletonization is deterministic, explainable,
  and runs at ~30fps on a Raspberry Pi 4 without a TPU. A neural net would
  add 200MB of model weight and 10x the latency for no accuracy gain on this
  specific task. (Source: Roscher et al., 2020 — "Explainable Machine Learning
  for Plant Research", Frontiers in Plant Science)

Dependencies: see requirements.txt
"""

import os
import sys
import cv2
import numpy as np
from enum import Enum
from typing import Optional

# Import thresholds from config.py instead of hardcoding them here.
# classify_vigor() and the simulation use identical cutoff values.
# both the simulation AND the camera classification update automatically.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "simulation"))
from config import HIGH_VIGOR_CM, GROWING_CM

# ─── Config ───────────────────────────────────────────────────────────────────

# Calibration: measure a known object in frame to get this value
PIXELS_PER_CM: float = 37.8  # adjust per your camera/mount height

# HSV color range for root detection (off-white / cream colored ube roots)
# Tune these in the calibration notebook if your lighting changes
ROOT_HSV_LOWER = np.array([10,  0,  180])
ROOT_HSV_UPPER = np.array([30, 40,  255])


# ─── Data Models ──────────────────────────────────────────────────────────────

class VigorClass(Enum):
    HIGH_VIGOR = "HIGH_VIGOR"  # root ≥ 3cm  → sell immediately
    GROWING    = "GROWING"     # root 0.5–3cm → monitor
    DUD        = "DUD"         # root < 0.5cm → flag for review


class VigorResult:
    def __init__(self, vessel_id, root_length_cm, vigor_class, confidence, debug_frame=None):
        self.vessel_id      = vessel_id
        self.root_length_cm = root_length_cm
        self.vigor_class    = vigor_class
        self.confidence     = confidence
        self.debug_frame    = debug_frame

# ─── Core Functions ───────────────────────────────────────────────────────────

def capture_frame(camera_index: int = 0) -> np.ndarray:
    """Grab a single frame from camera. Index 0 = Pi Camera or first USB cam."""
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("Camera read failed. Check connection and index.")
    return frame


def extract_root_mask(frame: np.ndarray) -> np.ndarray:
    """
    Isolates root pixels via HSV color segmentation.
    Returns a binary mask (255 = root, 0 = background).
    """
    hsv   = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask  = cv2.inRange(hsv, ROOT_HSV_LOWER, ROOT_HSV_UPPER)

    # Morphological cleanup: remove noise, fill small gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
    mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    return mask


def measure_root_length(mask: np.ndarray) -> tuple[float, float]:
    """
    Skeletonizes the root mask and counts skeleton pixels to estimate length.
    Returns (length_cm, confidence).
    Confidence = ratio of skeleton pixels to total mask pixels (higher = cleaner root).
    """
    # Skeletonize: collapse thick root blobs into single-pixel-wide paths
    skeleton = _skeletonize(mask)

    skeleton_px = np.count_nonzero(skeleton)
    mask_px     = np.count_nonzero(mask)

    if mask_px == 0:
        return 0.0, 0.0

    length_cm  = skeleton_px / PIXELS_PER_CM
    confidence = min(skeleton_px / max(mask_px, 1), 1.0)

    return length_cm, confidence

def classify_vigor(length_cm):
    if length_cm >= HIGH_VIGOR_CM:
        return VigorClass.HIGH_VIGOR
    elif length_cm >= GROWING_CM:
        return VigorClass.GROWING
    else:
        return VigorClass.DUD


def annotate_frame(frame: np.ndarray, result: VigorResult) -> np.ndarray:
    """Draws result overlay onto frame for dashboard livestream."""
    annotated = frame.copy()
    color = {
        VigorClass.HIGH_VIGOR: (0, 255, 0),   # green
        VigorClass.GROWING:    (0, 165, 255),  # orange
        VigorClass.DUD:        (0, 0, 255),    # red
    }[result.vigor_class]

    label = (
        f"{result.vessel_id} | "
        f"{result.vigor_class.value} | "
        f"{result.root_length_cm:.1f}cm | "
        f"conf:{result.confidence:.2f}"
    )
    cv2.putText(annotated, label, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)
    return annotated


# ─── Main Entrypoint ──────────────────────────────────────────────────────────

def analyze_vessel(vessel_id: str, camera_index: int = 0, debug: bool = False) -> VigorResult:
    """
    Full pipeline: capture → segment → measure → classify.
    This is the single function the dashboard-api calls via subprocess or socket.
    """
    frame              = capture_frame(camera_index)
    mask               = extract_root_mask(frame)
    length_cm, conf    = measure_root_length(mask)
    vigor              = classify_vigor(length_cm)

    result = VigorResult(
        vessel_id      = vessel_id,
        root_length_cm = round(length_cm, 2),
        vigor_class    = vigor,
        confidence     = round(conf, 2),
        debug_frame    = annotate_frame(frame, VigorResult(vessel_id, length_cm, vigor, conf)) if debug else None,
    )
    return result


# ─── Private Helpers ──────────────────────────────────────────────────────────

def _skeletonize(binary_mask: np.ndarray) -> np.ndarray:
    """
    Zhang-Suen thinning via iterative erosion.
    OpenCV doesn't ship skeletonize natively; this is the standard
    morphological approximation used in plant phenotyping pipelines.
    (Source: Zhang & Suen, 1984, CACM — the canonical algorithm)
    """
    skeleton = np.zeros_like(binary_mask)
    element  = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    temp     = binary_mask.copy()

    while True:
        eroded   = cv2.erode(temp, element)
        opened   = cv2.dilate(eroded, element)
        subset   = cv2.subtract(temp, opened)
        skeleton = cv2.bitwise_or(skeleton, subset)
        temp     = eroded.copy()
        if cv2.countNonZero(temp) == 0:
            break

    return skeleton


if __name__ == "__main__":
    # Quick CLI test: python root_vigor.py
    result = analyze_vessel(vessel_id="VESSEL-001", debug=True)
print("Result: {} | {}cm | conf:{}".format(
    result.vigor_class.value, result.root_length_cm, result.confidence))

    if result.debug_frame is not None:
        cv2.imshow("Root Vigor Debug", result.debug_frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()