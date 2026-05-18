import cv2
import mediapipe as mp
import numpy as np
from IPython.display import display, Javascript
from google.colab.output import eval_js
from base64 import b64decode

# ---------------- USER PARAMETERS ----------------
REAL_IRIS_DIAMETER_MM = 11.8
FOCAL_LENGTH_PIXELS = 1000
# -------------------------------------------------

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.2,
    min_tracking_confidence=0.2,
)

LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
THICKNESS = 1
BOX_ALPHA = 0.85
BOX_PADDING = 5

frame_idx = 0

# -------- HELPER FUNCTION --------
def draw_text_box(frame, top_left, bottom_right, alpha=0.85):
    overlay = frame.copy()
    cv2.rectangle(overlay, top_left, bottom_right, (255, 255, 255), -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

def put_text_with_box(frame, text, pos, font=FONT, scale=FONT_SCALE, thickness=THICKNESS, color=(0,0,0)):
    (text_w, text_h), _ = cv2.getTextSize(text, font, scale, thickness)
    top_left = (pos[0] - BOX_PADDING, pos[1] - text_h - BOX_PADDING)
    bottom_right = (pos[0] + text_w + BOX_PADDING, pos[1] + BOX_PADDING)
    draw_text_box(frame, top_left, bottom_right, alpha=BOX_ALPHA)
    cv2.putText(frame, text, pos, font, scale, color, thickness)

# ---------------- FRAME PROCESSING ----------------
print("Processing 100 frames from webcam...")

# Start webcam stream
js = Javascript('''
async function startStream() {
  const video = document.createElement('video');
  video.style.display = 'block';
  const stream = await navigator.mediaDevices.getUserMedia({video: true});
  document.body.appendChild(video);
  video.srcObject = stream;
  await video.play();
  google.colab.output.setIframeHeight(document.documentElement.scrollHeight, true);

  // Capture frames
  const canvas = document.createElement('canvas');
  const frames = [];

  for(let i = 0; i < 100; i++) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    frames.push(canvas.toDataURL('image/jpeg', 0.8));
    await new Promise(resolve => setTimeout(resolve, 33)); // ~30fps
  }

  stream.getVideoTracks()[0].stop();
  video.remove();
  return frames;
}
''')
display(js)
frames_data = eval_js('startStream()')

for frame_data in frames_data:
    frame_idx += 1

    # Decode frame
    binary = b64decode(frame_data.split(',')[1])
    nparr = np.frombuffer(binary, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    h, w = frame.shape[:2]
    CENTER_X = w / 2
    CENTER_Y = h / 2

    # Draw screen center lines
    cv2.line(frame, (int(CENTER_X), 0), (int(CENTER_X), h), (200, 200, 200), 2)
    cv2.line(frame, (0, int(CENTER_Y)), (w, int(CENTER_Y)), (200, 200, 200), 2)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    # Frame number
    put_text_with_box(frame, f"Frame: {frame_idx}", (20, 35), color=(0,0,0))

    if results.multi_face_landmarks:
        put_text_with_box(frame, "Face: DETECTED", (20, 75), color=(0,255,0))
        lm = results.multi_face_landmarks[0].landmark

        def p(idx):
            return np.array([lm[idx].x * w, lm[idx].y * h])

        # ---- LEFT EYE ----
        L_iris = np.array([p(i) for i in LEFT_IRIS])
        L_center = L_iris.mean(axis=0)
        L_radius = np.mean([np.linalg.norm(pt - L_center) for pt in L_iris])
        L_dist_cm = (REAL_IRIS_DIAMETER_MM * FOCAL_LENGTH_PIXELS /
                     max(np.linalg.norm(L_iris[0] - L_iris[2]), 1)) / 10

        L_eye_poly = np.array([p(i) for i in LEFT_EYE], dtype=np.int32)
        L_eye_x = L_eye_poly[:,0]
        L_eye_horiz_center = (L_eye_x.min() + L_eye_x.max()) / 2

        # ---- RIGHT EYE ----
        R_iris = np.array([p(i) for i in RIGHT_IRIS])
        R_center = R_iris.mean(axis=0)
        R_radius = np.mean([np.linalg.norm(pt - R_center) for pt in R_iris])
        R_dist_cm = (REAL_IRIS_DIAMETER_MM * FOCAL_LENGTH_PIXELS /
                     max(np.linalg.norm(R_iris[0] - R_iris[2]), 1)) / 10

        R_eye_poly = np.array([p(i) for i in RIGHT_EYE], dtype=np.int32)
        R_eye_x = R_eye_poly[:,0]
        R_eye_horiz_center = (R_eye_x.min() + R_eye_x.max()) / 2

        # Offsets from screen center
        dx_L = L_eye_horiz_center - CENTER_X
        dx_R = R_eye_horiz_center - CENTER_X
        dy_L = L_center[1] - CENTER_Y
        dy_R = R_center[1] - CENTER_Y

        # -------- SYMMETRY-AWARE CENTERING PERCENTAGES --------
        residual_dx = dx_L + dx_R
        horiz_pct = max(0, 100 * (1 - abs(residual_dx) / (w/2)))
        vert_dev = (abs(dy_L) + abs(dy_R)) / 2
        vert_pct = max(0, 100 * (1 - vert_dev / (h/2)))

        # -------- DRAW EYES & IRIS --------
        cv2.polylines(frame, [L_eye_poly], True, (0, 255, 0), 2)
        cv2.polylines(frame, [R_eye_poly], True, (0, 255, 0), 2)
        cv2.circle(frame, tuple(L_center.astype(int)), int(L_radius), (0, 255, 255), 2)
        cv2.circle(frame, tuple(L_center.astype(int)), 3, (0, 0, 255), -1)
        cv2.circle(frame, tuple(R_center.astype(int)), int(R_radius), (0, 255, 255), 2)
        cv2.circle(frame, tuple(R_center.astype(int)), 3, (0, 0, 255), -1)

        # -------- TEXT OUTPUT --------
        y0 = 120
        dy = 40
        h_color = (0, 255, 0) if horiz_pct >= 90 else (255, 165, 0) if horiz_pct >= 70 else (0, 0, 255)
        v_color = (0, 255, 0) if vert_pct >= 90 else (255, 165, 0) if vert_pct >= 70 else (0, 0, 255)

        put_text_with_box(frame, f"LEFT eye distance: {L_dist_cm:.2f} cm", (20, y0), color=(0,0,0))
        put_text_with_box(frame, f"RIGHT eye distance: {R_dist_cm:.2f} cm", (20, y0 + dy), color=(0,0,0))
        put_text_with_box(frame, f"Left and right eye {horiz_pct:.0f}% horizontal center",
                          (20, y0 + 2 * dy), color=h_color)
        put_text_with_box(frame, f"Left and right eye {vert_pct:.0f}% vertical center",
                          (20, y0 + 3 * dy), color=v_color)

    else:
        put_text_with_box(frame, "Face: NOT DETECTED", (20, 75), color=(0,0,255))

    # Display result
    from google.colab.patches import cv2_imshow
    cv2_imshow(frame)

face_mesh.close()
print("Processing complete. 100 frames captured and processed.")