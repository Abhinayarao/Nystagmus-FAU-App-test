from fastapi import FastAPI, File, UploadFile
import uvicorn
import mediapipe as mp
import numpy as np
import cv2

REAL_IRIS_DIAMETER_MM = 11.8
FOCAL_LENGTH_PIXELS = 1000

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.2,
    min_tracking_confidence=0.2,
)

LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]
LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "server is running"}



@app.post("/process_frame")
async def process_frame(file: UploadFile = File(...)):
    # Read the image from the request
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    h, w = frame.shape[:2]
    CENTER_X = w / 2
    CENTER_Y = h / 2
    
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    
    if not results.multi_face_landmarks:
        return {"face_detected": False}
    
    lm = results.multi_face_landmarks[0].landmark
    
    def p(idx):
        return np.array([lm[idx].x * w, lm[idx].y * h])
    
    # Left eye calculations
    L_iris = np.array([p(i) for i in LEFT_IRIS])
    L_center = L_iris.mean(axis=0)
    L_dist_cm = (REAL_IRIS_DIAMETER_MM * FOCAL_LENGTH_PIXELS /
                 max(np.linalg.norm(L_iris[0] - L_iris[2]), 1)) / 10
    
    # Right eye calculations
    R_iris = np.array([p(i) for i in RIGHT_IRIS])
    R_center = R_iris.mean(axis=0)
    R_dist_cm = (REAL_IRIS_DIAMETER_MM * FOCAL_LENGTH_PIXELS /
                 max(np.linalg.norm(R_iris[0] - R_iris[2]), 1)) / 10
    
    # Eye horizontal centers
    L_eye_poly = np.array([p(i) for i in LEFT_EYE])
    R_eye_poly = np.array([p(i) for i in RIGHT_EYE])

    L_eye_horiz_center = (L_eye_poly[:, 0].min() + L_eye_poly[:, 0].max()) / 2
    R_eye_horiz_center = (R_eye_poly[:, 0].min() + R_eye_poly[:, 0].max()) / 2

    # Offsets from screen center
    dx_L = L_eye_horiz_center - CENTER_X
    dx_R = R_eye_horiz_center - CENTER_X
    dy_L = L_center[1] - CENTER_Y
    dy_R = R_center[1] - CENTER_Y

    # Centering scores
    residual_dx = dx_L + dx_R
    horiz_pct = max(0, 100 * (1 - abs(residual_dx) / (w / 2)))
    vert_dev = (abs(dy_L) + abs(dy_R)) / 2
    vert_pct = max(0, 100 * (1 - vert_dev / (h / 2)))

    return {
    "face_detected": True,
    "left_eye_distance": round(L_dist_cm, 2),
    "right_eye_distance": round(R_dist_cm, 2),
    "horiz_pct": round(horiz_pct, 1),
    "vert_pct": round(vert_pct, 1),
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)