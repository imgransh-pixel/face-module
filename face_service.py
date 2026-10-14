import cv2
import numpy as np
import urllib.request
import os

DETECTOR_PATH = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_PATH = "face_recognition_sface_2021dec.onnx"

if not os.path.exists(DETECTOR_PATH):
    urllib.request.urlretrieve(
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        DETECTOR_PATH
    )

if not os.path.exists(RECOGNIZER_PATH):
    urllib.request.urlretrieve(
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        RECOGNIZER_PATH
    )

detector = cv2.FaceDetectorYN.create(DETECTOR_PATH, "", (320, 320), 0.5, 0.3, 5000)
recognizer = cv2.FaceRecognizerSF.create(RECOGNIZER_PATH, "")

def verify_staff_face(registered_img_path: str, live_img_path: str) -> dict:
    reg_img = cv2.imread(registered_img_path)
    live_img = cv2.imread(live_img_path)

    if reg_img is None or live_img is None:
        return {"verified": False, "confidence": 0.0, "reason": "Photo not found."}

    h, w, _ = live_img.shape
    detector.setInputSize((w, h))
    _, live_faces = detector.detect(live_img)
    _, reg_faces = detector.detect(reg_img)

    if reg_faces is None or len(reg_faces) == 0:
        return {"verified": False, "confidence": 0.0, "reason": "No face in registered photo. Re-register."}
    if live_faces is None or len(live_faces) == 0:
        return {"verified": False, "confidence": 0.0, "reason": "No face detected in live camera!"}

    # Automatically pick the largest/closest face in front of the camera
    reg_face = sorted(reg_faces, key=lambda f: f[2] * f[3], reverse=True)[0]
    live_face = sorted(live_faces, key=lambda f: f[2] * f[3], reverse=True)[0]

    reg_aligned = recognizer.alignCrop(reg_img, reg_face)
    live_aligned = recognizer.alignCrop(live_img, live_face)

    reg_feature = recognizer.feature(reg_aligned)
    live_feature = recognizer.feature(live_aligned)

    cosine_score = float(recognizer.match(reg_feature, live_feature, cv2.FaceRecognizerSF_FR_COSINE))
    threshold = 0.30

    confidence_pct = round(max(0.0, min(100.0, (cosine_score / 0.60) * 100)), 1)

    if cosine_score >= threshold:
        return {"verified": True, "confidence": confidence_pct, "reason": "Face verified successfully!"}
    else:
        return {"verified": False, "confidence": confidence_pct, "reason": f"Proxy Alert: Face mismatch ({confidence_pct}%)."}