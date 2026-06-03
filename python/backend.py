from fastapi import FastAPI, File, UploadFile
import uvicorn
import mediapipe as mp
import numpy as np
import cv2
import subprocess
import os
import base64
from fastapi.responses import JSONResponse;
from google.cloud import storage
from datetime import timedelta

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

@app.get("/get_upload_url")
async def get_upload_url(filename: str):
    try:
        import google.auth
        import google.auth.transport.requests
        
        credentials, project = google.auth.default()
        credentials.refresh(google.auth.transport.requests.Request())
        client = storage.Client(credentials=credentials)
        bucket = client.bucket("nystagmus-videos-fau")
        blob = bucket.blob(filename)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type="video/quicktime",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )
        return {"url": url, "filename": filename}
    except Exception as e:
        return {"error": str(e)}

@app.post("/process_frame")
async def process_frame(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h_orig, w_orig = frame.shape[:2]

    # Resize for faster MediaPipe processing
    frame = cv2.resize(frame, (640, 480))
    h, w = frame.shape[:2]
    CENTER_X = w_orig / 2
    CENTER_Y = h_orig / 2

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    if not results.multi_face_landmarks:
        return {"face_detected": False}

    lm = results.multi_face_landmarks[0].landmark

    def p(idx):
        return np.array([lm[idx].x * w_orig, lm[idx].y * h_orig])

    # Left eye calculations
    L_iris = np.array([p(i) for i in LEFT_IRIS])
    L_center = L_iris.mean(axis=0)
    L_radius = np.mean([np.linalg.norm(pt - L_center) for pt in L_iris])
    L_dist_cm = (REAL_IRIS_DIAMETER_MM * FOCAL_LENGTH_PIXELS /
                 max(np.linalg.norm(L_iris[0] - L_iris[2]), 1)) / 10

    # Right eye calculations
    R_iris = np.array([p(i) for i in RIGHT_IRIS])
    R_center = R_iris.mean(axis=0)
    R_radius = np.mean([np.linalg.norm(pt - R_center) for pt in R_iris])
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
    horiz_pct = max(0, 100 * (1 - abs(residual_dx) / (w_orig / 2)))
    vert_dev = (abs(dy_L) + abs(dy_R)) / 2
    vert_pct = max(0, 100 * (1 - vert_dev / (h_orig / 2)))

    return {
        "face_detected": True,
        "left_eye_distance": round(L_dist_cm, 2),
        "right_eye_distance": round(R_dist_cm, 2),
        "horiz_pct": round(horiz_pct, 1),
        "vert_pct": round(vert_pct, 1),
        "left_iris_center": L_center.tolist(),
        "left_iris_radius": float(L_radius),
        "right_iris_center": R_center.tolist(),
        "right_iris_radius": float(R_radius),
        "left_eye_poly": L_eye_poly.tolist(),
        "right_eye_poly": R_eye_poly.tolist(),
        "frame_width": w_orig,
        "frame_height": h_orig,
    }

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...), beat_type: str = "left"):
    try:
        # Save uploaded video to temp file
        temp_video_path = f"/tmp/recording_{beat_type}.mp4"
        contents = await file.read()
        with open(temp_video_path, "wb") as f:
            f.write(contents)

        # Select the correct Python script
        script_map = {
            "left": "python/Left_Beat.py",
            "right": "python/Right_Beat.py",
            "up": "python/Up_Beat.py",
            "down": "python/Down_Beat.py",
        }
        script_path = script_map.get(beat_type, "python/Left_Beat.py")

        # Read the script
        with open(script_path, 'r') as f:
            script_content = f.read()

        # Replace video_path with actual path
        script_content = script_content.replace(
            script_content[script_content.find("video_path ="):script_content.find("\n", script_content.find("video_path ="))],
            f"video_path = '{temp_video_path}'"
        )

        # Add non-interactive matplotlib backend at top and fix save path
        script_content = "import matplotlib\nmatplotlib.use('Agg')\n" + script_content

#        Make script save graph to /tmp
        script_content = script_content.replace(
        "plt.savefig('plot5_spv_analysis.png'",
        "plt.savefig('/tmp/plot5_spv_analysis.png'"
)

        # Save modified script to temp file
        temp_script = f"/tmp/temp_{beat_type}_beat.py"
        with open(temp_script, 'w') as f:
            f.write(script_content)

        # Run the script
        result = subprocess.run(
            ["python", temp_script],
            capture_output=True,
            text=True,
            timeout=300
        )

        # Read generated graph image
        graph_path = "/tmp/plot5_spv_analysis.png"
        if not os.path.exists(graph_path):
            graph_path = "plot5_spv_analysis.png"

        if os.path.exists(graph_path):
            with open(graph_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            return {"success": True, "graph": img_base64}
        else:
            return {"success": False, "error": "Graph not generated", "stderr": result.stderr}

    except Exception as e:
        return {"success": False, "error": str(e)}
    
@app.post("/analyze_auto")
async def analyze_auto(file: UploadFile = File(...)):
    try:
        # Save uploaded video to temp file
        temp_video_path = f"/tmp/recording_auto.mp4"
        contents = await file.read()
        with open(temp_video_path, "wb") as f:
            f.write(contents)

        # Read Decide_Beat.py
        with open("python/Decide_Beat.py", 'r') as f:
            decide_content = f.read()

        # Replace video_path
        decide_content = decide_content.replace(
            decide_content[decide_content.find("video_path ="):decide_content.find("\n", decide_content.find("video_path ="))],
            f"video_path = '{temp_video_path}'"
        )

        # Add matplotlib backend and print direction at end
        decide_content = "import matplotlib\nmatplotlib.use('Agg')\n" + decide_content
        decide_content += """
                         if classification['direction'] is None:
                         # Use best guess based on counts
                        if classification['right_count'] > classification['left_count']:
                            print(f'DIRECTION:rightward')
                        elif classification['left_count'] > classification['right_count']:
                            print(f'DIRECTION:leftward')
                        else:
                            print(f'DIRECTION:None')
                        else:
                            print(f'DIRECTION:{classification[\"direction\"]}')
                        """
        

        # Save and run Decide_Beat.py
        temp_decide = "/tmp/temp_decide_beat.py"
        with open(temp_decide, 'w') as f:
            f.write(decide_content)

        result = subprocess.run(
            ["python", temp_decide],
            capture_output=True,
            text=True,
            timeout=300
        )

        # Extract direction from output
        direction = None
        for line in result.stdout.split('\n'):
            if line.startswith('DIRECTION:'):
                direction = line.replace('DIRECTION:', '').strip()
                break

        if direction not in ['rightward', 'leftward']:
                return {"success": False, "error": "No nystagmus detected in the video. Please record a longer video with clear eye movement visible."}

        # Map direction to beat script
        beat_script = "python/Right_Beat.py" if direction == 'rightward' else "python/Left_Beat.py"

        # Read and run the beat script
        with open(beat_script, 'r') as f:
            script_content = f.read()

        script_content = script_content.replace(
            script_content[script_content.find("video_path ="):script_content.find("\n", script_content.find("video_path ="))],
            f"video_path = '{temp_video_path}'"
        )
        script_content = "import matplotlib\nmatplotlib.use('Agg')\n" + script_content
        script_content = script_content.replace(
            "plt.savefig('plot5_spv_analysis.png'",
            "plt.savefig('/tmp/plot5_spv_analysis.png'"
        )

        temp_script = f"/tmp/temp_beat.py"
        with open(temp_script, 'w') as f:
            f.write(script_content)

        result2 = subprocess.run(
            ["python", temp_script],
            capture_output=True,
            text=True,
            timeout=300
        )

        # Read graph
        graph_path = "/tmp/plot5_spv_analysis.png"
        if os.path.exists(graph_path):
            with open(graph_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            return {"success": True, "graph": img_base64, "direction": direction}
        else:
            return {"success": False, "error": "Graph not generated", "stderr": result2.stderr}

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/analyze_from_gcs")
async def analyze_from_gcs(gcs_path: str):
    try:
        client = storage.Client()
        bucket = client.bucket("nystagmus-videos-fau")
        blob = bucket.blob(gcs_path)
        temp_video_path = f"/tmp/{gcs_path}"
        blob.download_to_filename(temp_video_path)

        # Run Decide_Beat.py
        with open("python/Decide_Beat.py", 'r') as f:
            decide_content = f.read()
        decide_content = decide_content.replace(
            decide_content[decide_content.find("video_path ="):decide_content.find("\n", decide_content.find("video_path ="))],
            f"video_path = '{temp_video_path}'"
        )
        decide_content = "import matplotlib\nmatplotlib.use('Agg')\n" + decide_content
        decide_content += """
if classification['direction'] is None:
    if classification['right_count'] > classification['left_count']:
        print(f'DIRECTION:rightward')
    elif classification['left_count'] > classification['right_count']:
        print(f'DIRECTION:leftward')
    else:
        print(f'DIRECTION:None')
else:
    print(f'DIRECTION:{classification["direction"]}')
"""
        temp_decide = "/tmp/temp_decide_beat.py"
        with open(temp_decide, 'w') as f:
            f.write(decide_content)
        result = subprocess.run(
            ["python", temp_decide],
            capture_output=True, text=True, timeout=300
        )

        direction = None
        for line in result.stdout.split('\n'):
            if line.startswith('DIRECTION:'):
                direction = line.replace('DIRECTION:', '').strip()
                break

        if direction not in ['rightward', 'leftward']:
            return {"success": False, "error": "No nystagmus detected in the video."}

        beat_script = "python/Right_Beat.py" if direction == 'rightward' else "python/Left_Beat.py"
        with open(beat_script, 'r') as f:
            script_content = f.read()
        script_content = script_content.replace(
            script_content[script_content.find("video_path ="):script_content.find("\n", script_content.find("video_path ="))],
            f"video_path = '{temp_video_path}'"
        )
        script_content = "import matplotlib\nmatplotlib.use('Agg')\n" + script_content
        script_content = script_content.replace(
            "plt.savefig('plot5_spv_analysis.png'",
            "plt.savefig('/tmp/plot5_spv_analysis.png'"
        )
        temp_script = "/tmp/temp_beat_gcs.py"
        with open(temp_script, 'w') as f:
            f.write(script_content)
        result2 = subprocess.run(
            ["python", temp_script],
            capture_output=True, text=True, timeout=300
        )

        graph_path = "/tmp/plot5_spv_analysis.png"
        if os.path.exists(graph_path):
            with open(graph_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            return {"success": True, "graph": img_base64, "direction": direction}
        else:
            return {"success": False, "error": "Graph not generated", "stderr": result2.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)