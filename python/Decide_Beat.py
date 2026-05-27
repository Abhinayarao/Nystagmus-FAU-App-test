import cv2
import mediapipe as mp
import numpy as np
import matplotlib.pyplot as plt

# ================= MediaPipe setup =================
mp_face_mesh = mp.solutions.face_mesh

LEFT_EYE_CONTOUR = [33, 246, 161, 160, 159, 158, 157, 173,
                    133, 155, 154, 153, 145, 144, 163, 7]

RIGHT_EYE_CONTOUR = [362, 398, 384, 385, 386, 387, 388, 466,
                     263, 249, 390, 373, 374, 380, 381, 382]

# MediaPipe iris landmarks (outer 4 points for left eye)
LEFT_IRIS_OUTER = [469, 470, 471, 472]  # Top, Bottom, Left, Right

# ================= Eye Aspect Ratio =================
def eye_aspect_ratio(eye_points):
    A = np.linalg.norm(eye_points[1] - eye_points[5])
    B = np.linalg.norm(eye_points[2] - eye_points[4])
    C = np.linalg.norm(eye_points[0] - eye_points[3])
    return (A + B) / (2.0 * C)

# ================= Detect and crop eyes =================
def detect_and_crop_eyes(face_mesh, frame):
    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_image)

    if not results.multi_face_landmarks:
        return None, None, None

    h, w = frame.shape[:2]
    landmarks = np.array([
        [int(lm.x * w), int(lm.y * h)]
        for lm in results.multi_face_landmarks[0].landmark
    ])

    left_eye_points = landmarks[[33, 160, 158, 133, 153, 144]]
    right_eye_points = landmarks[[362, 385, 387, 263, 373, 380]]

    if (eye_aspect_ratio(left_eye_points) < 0.22 and
        eye_aspect_ratio(right_eye_points) < 0.22):
        return None, None, None

    left_eye_poly = landmarks[LEFT_EYE_CONTOUR]
    left_iris_poly = landmarks[LEFT_IRIS_OUTER]

    purple_bg = np.zeros_like(frame)
    purple_bg[:] = (128, 0, 128)

    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [left_eye_poly], 255)
    eye = np.where(mask[:, :, None] == 255, frame, purple_bg)
    x, y, w_, h_ = cv2.boundingRect(left_eye_poly)
    eye_crop = eye[y:y+h_, x:x+w_]

    iris_points_adjusted = left_iris_poly - [x, y]

    return eye_crop, iris_points_adjusted, frame

# ================= Find regions with RGB > threshold =================
def find_rgb_greater_than_100(inverted_eye, original_eye, print_info=False):
    height, width = inverted_eye.shape[:2]
    avg_rgb = np.mean(inverted_eye, axis=2)

    green_bg_mask = (
        (inverted_eye[:, :, 0] == 127) &
        (inverted_eye[:, :, 1] == 255) &
        (inverted_eye[:, :, 2] == 127)
    )

    purple_filler_mask = (
        (original_eye[:, :, 0] == 128) &
        (original_eye[:, :, 1] == 0) &
        (original_eye[:, :, 2] == 128)
    )

    b_channel = original_eye[:, :, 0]
    g_channel = original_eye[:, :, 1]
    r_channel = original_eye[:, :, 2]

    tolerance = 5
    near_purple_mask = (
        (np.abs(b_channel - 128) <= tolerance) &
        (np.abs(g_channel - 0) <= tolerance) &
        (np.abs(r_channel - 128) <= tolerance)
    )

    filler_mask = purple_filler_mask | near_purple_mask

    RGB_THRESHOLD = 10
    rgb_greater_mask = (avg_rgb > RGB_THRESHOLD) & (~green_bg_mask) & (~filler_mask)
    pixel_count = np.sum(rgb_greater_mask)

    if print_info:
        total_pixels = height * width
        non_bg_pixels = np.sum(~green_bg_mask)
        filler_pixels = np.sum(filler_mask)
        non_bg_non_filler_pixels = np.sum((~green_bg_mask) & (~filler_mask))
        print(f"\n  RGB > {RGB_THRESHOLD} Analysis:")
        print(f"    Total pixels: {total_pixels}")
        print(f"    Non-background pixels: {non_bg_pixels}")
        print(f"    Filler pixels (purple) excluded: {filler_pixels}")
        print(f"    Non-background, non-filler pixels: {non_bg_non_filler_pixels}")
        print(f"    Pixels with RGB > {RGB_THRESHOLD}: {pixel_count}")
        if non_bg_non_filler_pixels > 0:
            print(f"    Percentage of valid pixels: {pixel_count / non_bg_non_filler_pixels * 100:.1f}%")

    return rgb_greater_mask, pixel_count

# ================= Filter RGB mask by grid =================
def filter_rgb_mask_by_grid(inverted_eye, rgb_mask, print_info=False):
    height, width = inverted_eye.shape[:2]
    grid_rows = 40
    grid_cols = 40
    grid_height = height / grid_rows
    grid_width = width / grid_cols

    if print_info:
        print(f"\n  Grid Filtering Analysis:")
        print(f"    Image size: {width}x{height}")
        print(f"    Grid size: {grid_cols} columns x {grid_rows} rows")
        print(f"    Each grid cell: {grid_width:.1f}x{grid_height:.1f} pixels")

    grid_map = np.zeros((grid_rows, grid_cols), dtype=bool)

    for col in range(grid_cols):
        for row in range(grid_rows):
            x_start = int(col * grid_width)
            x_end = int((col + 1) * grid_width) if col < grid_cols - 1 else width
            y_start = int(row * grid_height)
            y_end = int((row + 1) * grid_height) if row < grid_rows - 1 else height
            grid_cell_mask = rgb_mask[y_start:y_end, x_start:x_end]
            grid_map[row, col] = np.any(grid_cell_mask)

    filtered_mask = rgb_mask.copy()
    valid_columns = 0
    removed_columns = 0

    for col in range(grid_cols):
        count = np.sum(grid_map[:, col])
        if count < 20:
            x_start = int(col * grid_width)
            x_end = int((col + 1) * grid_width) if col < grid_cols - 1 else width
            filtered_mask[:, x_start:x_end] = False
            removed_columns += 1
            if print_info:
                print(f"    Column {col}: {count} grids → REMOVED")
        else:
            valid_columns += 1
            if print_info:
                print(f"    Column {col}: {count} grids → KEPT")

    if print_info:
        original_pixels = np.sum(rgb_mask)
        filtered_pixels = np.sum(filtered_mask)
        removed_pixels = original_pixels - filtered_pixels
        print(f"\n  Filtering Results:")
        print(f"    Valid columns: {valid_columns}")
        print(f"    Removed columns: {removed_columns}")
        print(f"    Original highlighted pixels: {original_pixels}")
        print(f"    Filtered highlighted pixels: {filtered_pixels}")
        if original_pixels > 0:
            print(f"    Removed pixels: {removed_pixels} ({removed_pixels/original_pixels*100:.1f}%)")

    return filtered_mask

# ================= Find largest cluster =================
def find_largest_cluster(filtered_mask, original_eye, print_info=False):
    from scipy import ndimage

    if not filtered_mask.any():
        return np.zeros_like(filtered_mask, dtype=bool), 0

    purple_filler_mask = (
        (original_eye[:, :, 0] == 128) &
        (original_eye[:, :, 1] == 0) &
        (original_eye[:, :, 2] == 128)
    )

    b_channel = original_eye[:, :, 0]
    g_channel = original_eye[:, :, 1]
    r_channel = original_eye[:, :, 2]

    tolerance = 5
    near_purple_mask = (
        (np.abs(b_channel - 128) <= tolerance) &
        (np.abs(g_channel - 0) <= tolerance) &
        (np.abs(r_channel - 128) <= tolerance)
    )

    filler_mask = purple_filler_mask | near_purple_mask
    filtered_mask_no_filler = filtered_mask & (~filler_mask)

    if print_info:
        total_filtered = np.sum(filtered_mask)
        filler_pixels = np.sum(filtered_mask & filler_mask)
        remaining_pixels = np.sum(filtered_mask_no_filler)
        print(f"\n  Filler Exclusion:")
        print(f"    Total filtered pixels: {total_filtered}")
        print(f"    Filler pixels removed: {filler_pixels}")
        print(f"    Remaining pixels: {remaining_pixels}")

    if not filtered_mask_no_filler.any():
        return np.zeros_like(filtered_mask, dtype=bool), 0

    labeled_array, num_features = ndimage.label(filtered_mask_no_filler)
    if num_features == 0:
        return np.zeros_like(filtered_mask, dtype=bool), 0

    component_sizes = np.bincount(labeled_array.ravel())
    component_sizes[0] = 0
    if len(component_sizes) <= 1:
        return np.zeros_like(filtered_mask, dtype=bool), 0

    largest_component_label = component_sizes.argmax()
    largest_cluster_mask = (labeled_array == largest_component_label)
    cluster_size = component_sizes[largest_component_label]

    if print_info:
        print(f"\n  Largest Cluster Analysis:")
        print(f"    Number of clusters: {num_features}")
        print(f"    Largest cluster size: {cluster_size} pixels")

    return largest_cluster_mask, cluster_size

# ================= Centroid =================
def calculate_centroid(cluster_mask):
    if not cluster_mask.any():
        return None
    y_coords, x_coords = np.where(cluster_mask)
    centroid_x = int(np.mean(x_coords))
    centroid_y = int(np.mean(y_coords))
    return (centroid_x, centroid_y)

# ================= Yellow/Red cluster boundaries =================
def find_yellow_cluster_boundaries(rgb_less_than_100_mask, largest_cluster_mask, height, width, print_info=False):
    grid_cols = 200
    grid_width = width / grid_cols

    strip_has_content = []
    for col in range(grid_cols):
        x_start = int(col * grid_width)
        x_end = int((col + 1) * grid_width) if col < grid_cols - 1 else width
        yellow_region = rgb_less_than_100_mask[:, x_start:x_end]
        red_region = largest_cluster_mask[:, x_start:x_end]
        has_content = np.any(yellow_region) or np.any(red_region)
        strip_has_content.append(has_content)

    clusters = []
    current_cluster_start = None
    for col in range(grid_cols):
        if strip_has_content[col]:
            if current_cluster_start is None:
                current_cluster_start = col
        else:
            if current_cluster_start is not None:
                clusters.append((current_cluster_start, col - 1))
                current_cluster_start = None
    if current_cluster_start is not None:
        clusters.append((current_cluster_start, grid_cols - 1))

    if len(clusters) == 0:
        return None, None

    cluster_lengths = [(end - start + 1) for start, end in clusters]
    longest_cluster_idx = np.argmax(cluster_lengths)
    strongest_cluster = clusters[longest_cluster_idx]

    cluster_start_col, cluster_end_col = strongest_cluster
    cluster_left_x = int(cluster_start_col * grid_width)
    cluster_right_x = int((cluster_end_col + 1) * grid_width) if cluster_end_col < grid_cols - 1 else width - 1

    if print_info:
        print(f"\n  Yellow/Red Cluster Detection:")
        print(f"    Found {len(clusters)} cluster(s)")
        print(f"    Strongest cluster boundaries: X=[{cluster_left_x}, {cluster_right_x}]")

    return cluster_left_x, cluster_right_x

# ================= Display single frame =================
def display_frame_results(frame_num, original_eye, adjusted_eye, inverted_eye, largest_cluster_mask, inverted_eye_for_rgb):
    fig, axes = plt.subplots(1, 4, figsize=(24, 6))

    axes[0].imshow(cv2.cvtColor(original_eye, cv2.COLOR_BGR2RGB))
    axes[0].set_title(f"Frame {frame_num}: Original Cropped Eye", fontsize=14, fontweight='bold')
    axes[0].axis('off')

    axes[1].imshow(cv2.cvtColor(adjusted_eye, cv2.COLOR_BGR2RGB))
    axes[1].set_title(f"Frame {frame_num}: After α=3, β=-100", fontsize=14, fontweight='bold')
    axes[1].axis('off')

    axes[2].imshow(cv2.cvtColor(inverted_eye, cv2.COLOR_BGR2RGB))
    axes[2].set_title(f"Frame {frame_num}: After Color Inversion", fontsize=14, fontweight='bold')
    axes[2].axis('off')

    height, width = inverted_eye_for_rgb.shape[:2]
    highlighted = np.ones((height, width, 3), dtype=np.uint8) * 255

    avg_rgb = np.mean(inverted_eye_for_rgb, axis=2)
    green_bg_mask = (
        (inverted_eye_for_rgb[:, :, 0] == 127) &
        (inverted_eye_for_rgb[:, :, 1] == 255) &
        (inverted_eye_for_rgb[:, :, 2] == 127)
    )
    rgb_less_than_100_mask = (avg_rgb < 10) & (~green_bg_mask)

    highlighted[rgb_less_than_100_mask] = [0, 255, 255]
    highlighted[largest_cluster_mask] = [0, 0, 255]

    centroid = calculate_centroid(largest_cluster_mask)
    centroid_text = ""
    normalized_pos_text = ""

    cluster_left_x, cluster_right_x = find_yellow_cluster_boundaries(
        rgb_less_than_100_mask, largest_cluster_mask, height, width, print_info=True)

    if cluster_left_x is not None and cluster_right_x is not None:
        cv2.line(highlighted, (cluster_left_x, 0), (cluster_left_x, height - 1),
                color=(0, 255, 0), thickness=2)
        cv2.line(highlighted, (cluster_right_x, 0), (cluster_right_x, height - 1),
                color=(0, 255, 0), thickness=2)

        if centroid is not None:
            centroid_x, centroid_y = centroid
            yellow_width = cluster_right_x - cluster_left_x
            normalized_x = (centroid_x - cluster_left_x) / yellow_width if yellow_width > 0 else 0.5
            normalized_y = centroid_y / height
            normalized_x = max(0.0, min(1.0, normalized_x))
            normalized_y = max(0.0, min(1.0, normalized_y))

            cv2.circle(highlighted, (centroid_x, centroid_y), radius=5, color=(255, 0, 255), thickness=-1)
            cv2.circle(highlighted, (centroid_x, centroid_y), radius=6, color=(0, 0, 0), thickness=1)

            centroid_text = f", Centroid: ({centroid_x}, {centroid_y})"
            normalized_pos_text = f", Normalized: ({normalized_x:.2f}, {normalized_y:.2f})"
    else:
        if centroid is not None:
            centroid_x, centroid_y = centroid
            cv2.circle(highlighted, (centroid_x, centroid_y), radius=5, color=(255, 0, 255), thickness=-1)
            cv2.circle(highlighted, (centroid_x, centroid_y), radius=6, color=(0, 0, 0), thickness=1)
            centroid_text = f", Centroid: ({centroid_x}, {centroid_y})"

    grid_rows = 40
    grid_cols = 40
    grid_height = height / grid_rows
    grid_width = width / grid_cols

    for col in range(1, grid_cols):
        x = int(col * grid_width)
        cv2.line(highlighted, (x, 0), (x, height - 1), color=(0, 0, 0), thickness=1)
    for row in range(1, grid_rows):
        y = int(row * grid_height)
        cv2.line(highlighted, (0, y), (width - 1, y), color=(0, 0, 0), thickness=1)

    axes[3].imshow(cv2.cvtColor(highlighted, cv2.COLOR_BGR2RGB))
    cluster_pixels = np.sum(largest_cluster_mask)
    rgb_less_pixels = np.sum(rgb_less_than_100_mask)
    axes[3].set_title(f"Frame {frame_num}: Yellow + Red + Grid + Centroid + Boundaries\n"
                      f"(Yellow: {rgb_less_pixels}px, Red: {cluster_pixels}px{centroid_text}{normalized_pos_text})",
                      fontsize=14, fontweight='bold')
    axes[3].axis('off')

    plt.tight_layout()
    plt.show()

# ================= NEW: Detect directional segments (generic) =================
def detect_directional_segments(norm_x_values, frames, direction, magnitude_threshold=0.03):
    """
    Detect continuous monotonic segments in one direction and return only those
    whose total magnitude meets the threshold.

    Args:
        norm_x_values: list of normalized X positions
        frames: list of frame numbers (parallel to norm_x_values)
        direction: 'rightward' (increasing X) or 'leftward' (decreasing X)
        magnitude_threshold: minimum total change to qualify as a fast phase

    Returns:
        qualifying_regions: list of dicts with start_frame, end_frame, start_x, end_x,
                            magnitude, num_frames
        all_segments: list of all monotonic segments (for diagnostics)
    """
    segments = []
    current_segment = None

    for i in range(len(norm_x_values) - 1):
        x_current = norm_x_values[i]
        x_next = norm_x_values[i + 1]

        if direction == 'rightward':
            continues = x_next > x_current
        else:  # leftward
            continues = x_next < x_current

        if continues:
            if current_segment is None:
                current_segment = {
                    'start_idx': i,
                    'end_idx': i + 1,
                    'start_frame': frames[i],
                    'end_frame': frames[i + 1],
                    'start_x': x_current,
                    'end_x': x_next
                }
            else:
                current_segment['end_idx'] = i + 1
                current_segment['end_frame'] = frames[i + 1]
                current_segment['end_x'] = x_next
        else:
            if current_segment is not None:
                segments.append(current_segment)
                current_segment = None

    if current_segment is not None:
        segments.append(current_segment)

    # Filter by magnitude
    qualifying = []
    for seg in segments:
        if direction == 'rightward':
            magnitude = seg['end_x'] - seg['start_x']
        else:
            magnitude = seg['start_x'] - seg['end_x']

        if magnitude >= magnitude_threshold:
            qualifying.append({
                'start_frame': seg['start_frame'],
                'end_frame': seg['end_frame'],
                'start_x': seg['start_x'],
                'end_x': seg['end_x'],
                'magnitude': magnitude,
                'num_frames': seg['end_idx'] - seg['start_idx']
            })

    return qualifying, segments

# ================= NEW: Classify dominant direction =================
def classify_direction(rightward_regions, leftward_regions, confidence_ratio=0.80):
    """
    Classify the dominant fast-phase direction.
    Rule: count primary, MEAN intensity per phase as tiebreaker.
    Warns if classification is weak (loser scores >= confidence_ratio of winner).

    Returns:
        result: dict with 'direction', 'is_confident', 'reason',
                'right_count', 'left_count',
                'right_mean_intensity', 'left_mean_intensity',
                'right_total_intensity', 'left_total_intensity'
    """
    right_count = len(rightward_regions)
    left_count = len(leftward_regions)
    right_total = sum(r['magnitude'] for r in rightward_regions)
    left_total = sum(r['magnitude'] for r in leftward_regions)
    right_mean = (right_total / right_count) if right_count > 0 else 0.0
    left_mean = (left_total / left_count) if left_count > 0 else 0.0

    # No data at all
    if right_count == 0 and left_count == 0:
        return {
            'direction': None,
            'is_confident': False,
            'reason': 'No qualifying fast phases detected in either direction',
            'right_count': 0, 'left_count': 0,
            'right_mean_intensity': 0.0, 'left_mean_intensity': 0.0,
            'right_total_intensity': 0.0, 'left_total_intensity': 0.0
        }

    # Decide winner: count primary, MEAN intensity tiebreaker
    if right_count > left_count:
        winner = 'rightward'
        tiebreaker_used = False
    elif left_count > right_count:
        winner = 'leftward'
        tiebreaker_used = False
    else:
        # Equal counts → fall back to mean intensity per phase
        tiebreaker_used = True
        if right_mean > left_mean:
            winner = 'rightward'
        elif left_mean > right_mean:
            winner = 'leftward'
        else:
            return {
                'direction': None,
                'is_confident': False,
                'reason': (f'Perfect tie: counts equal ({right_count}) and '
                           f'mean intensities equal ({right_mean:.3f})'),
                'right_count': right_count, 'left_count': left_count,
                'right_mean_intensity': right_mean, 'left_mean_intensity': left_mean,
                'right_total_intensity': right_total, 'left_total_intensity': left_total
            }

    # Confidence check
    winner_score = right_count if winner == 'rightward' else left_count
    loser_score = left_count if winner == 'rightward' else right_count

    if winner_score == 0:
        ratio = 0.0
    else:
        ratio = loser_score / winner_score

    is_confident = ratio < confidence_ratio
    if tiebreaker_used:
        # Counts were equal — weak/mixed pattern by definition
        is_confident = False
        reason = (f'Counts tied at {right_count}; decided by mean intensity '
                  f'(R={right_mean:.3f} vs L={left_mean:.3f})')
    elif not is_confident:
        reason = (f'Loser/winner count ratio = {ratio:.2f} (≥ {confidence_ratio:.2f}); '
                  f'pattern appears mixed')
    else:
        reason = f'Clear dominance: {winner_score} vs {loser_score} (ratio={ratio:.2f})'

    return {
        'direction': winner,
        'is_confident': is_confident,
        'reason': reason,
        'right_count': right_count, 'left_count': left_count,
        'right_mean_intensity': right_mean, 'left_mean_intensity': left_mean,
        'right_total_intensity': right_total, 'left_total_intensity': left_total
    }

# ================= MAIN =================
video_path = '/content/drive/MyDrive/Dataset/6 March/IMG_3299.MOV'  # change as needed
cap = cv2.VideoCapture(video_path)

DISPLAY_FRAMES = [300, 302, 303, 304, 305, 306, 307, 308, 309, 310]
MAX_FRAME = 500
MAGNITUDE_THRESHOLD = 0.03
CONFIDENCE_RATIO = 0.80  # if loser/winner >= this, classification is weak

frame_count = 0
tracking_data = []

print("="*80)
print("EYE TRACKING WITH AUTOMATIC DIRECTION CLASSIFICATION")
print("="*80)
print(f"Magnitude threshold for fast phases: {MAGNITUDE_THRESHOLD}")
print(f"Confidence ratio threshold: {CONFIDENCE_RATIO}")
print(f"Will detect BOTH rightward and leftward fast phases,")
print(f"then classify the dominant direction (count primary, MEAN intensity tiebreaker).")
print("="*80)

with mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.2,
        min_tracking_confidence=0.2) as face_mesh:

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        if frame_count <= 100:
            continue

        eye_crop, iris_points, original_frame = detect_and_crop_eyes(face_mesh, frame)

        if eye_crop is None:
            if frame_count > MAX_FRAME:
                break
            continue

        original_eye = eye_crop.copy()
        alpha = 3.0
        beta = -100
        adjusted_eye = cv2.convertScaleAbs(eye_crop, alpha=alpha, beta=beta)
        inverted_eye = 255 - adjusted_eye

        print_info = (frame_count in DISPLAY_FRAMES)
        rgb_mask, pixel_count = find_rgb_greater_than_100(inverted_eye, original_eye, print_info=print_info)
        filtered_mask = filter_rgb_mask_by_grid(inverted_eye, rgb_mask, print_info=print_info)
        largest_cluster_mask, cluster_size = find_largest_cluster(filtered_mask, original_eye, print_info=print_info)

        centroid = calculate_centroid(largest_cluster_mask)

        height, width = inverted_eye.shape[:2]
        avg_rgb = np.mean(inverted_eye, axis=2)
        green_bg_mask = (
            (inverted_eye[:, :, 0] == 127) &
            (inverted_eye[:, :, 1] == 255) &
            (inverted_eye[:, :, 2] == 127)
        )
        rgb_less_than_100_mask = (avg_rgb < 10) & (~green_bg_mask)

        cluster_left_x, cluster_right_x = find_yellow_cluster_boundaries(
            rgb_less_than_100_mask, largest_cluster_mask, height, width, print_info=False)

        if cluster_left_x is not None and cluster_right_x is not None and centroid is not None:
            centroid_x, centroid_y = centroid
            yellow_width = cluster_right_x - cluster_left_x
            normalized_x = (centroid_x - cluster_left_x) / yellow_width if yellow_width > 0 else 0.5
            normalized_y = centroid_y / height
            normalized_x = max(0.0, min(1.0, normalized_x))
            normalized_y = max(0.0, min(1.0, normalized_y))

            tracking_data.append({
                'frame': frame_count,
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'normalized_x': normalized_x,
                'normalized_y': normalized_y,
                'left_end_x': cluster_left_x,
                'right_end_x': cluster_right_x,
                'top_end_y': 0,
                'bottom_end_y': height - 1
            })

        if frame_count in DISPLAY_FRAMES:
            print(f"\n{'='*80}\nDISPLAYING FRAME {frame_count}\n{'='*80}")
            display_frame_results(frame_count, original_eye, adjusted_eye, inverted_eye,
                                  largest_cluster_mask, inverted_eye)

        if frame_count >= MAX_FRAME:
            break

cap.release()

print(f"\n{'='*80}\nProcessing complete!\n{'='*80}")

# ================= ANALYSIS =================
if len(tracking_data) > 0:
    print(f"\n{'='*80}")
    print(f"TRACKING SUMMARY ({len(tracking_data)} frames with valid data)")
    print(f"{'='*80}")

    frames = [d['frame'] for d in tracking_data]
    norm_x_values = [d['normalized_x'] for d in tracking_data]
    norm_y_values = [d['normalized_y'] for d in tracking_data]

    print(f"\nNormalized X: mean={np.mean(norm_x_values):.3f}, std={np.std(norm_x_values):.3f}, "
          f"range=[{np.min(norm_x_values):.3f}, {np.max(norm_x_values):.3f}]")
    print(f"Normalized Y: mean={np.mean(norm_y_values):.3f}, std={np.std(norm_y_values):.3f}, "
          f"range=[{np.min(norm_y_values):.3f}, {np.max(norm_y_values):.3f}]")

    # Save CSV
    import csv
    csv_filename = 'eye_tracking_data.csv'
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = ['frame', 'centroid_x', 'centroid_y', 'normalized_x', 'normalized_y',
                      'left_end_x', 'right_end_x', 'top_end_y', 'bottom_end_y']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tracking_data)
    print(f"\n✓ Tracking data saved to '{csv_filename}'")

    # ===== Detect BOTH directions =====
    print(f"\n{'='*80}")
    print(f"DETECTING FAST PHASES IN BOTH DIRECTIONS (threshold = {MAGNITUDE_THRESHOLD})")
    print(f"{'='*80}")

    rightward_regions, right_all = detect_directional_segments(
        norm_x_values, frames, 'rightward', MAGNITUDE_THRESHOLD)
    leftward_regions, left_all = detect_directional_segments(
        norm_x_values, frames, 'leftward', MAGNITUDE_THRESHOLD)

    print(f"\nRightward (increasing X):")
    print(f"  Total monotonic segments: {len(right_all)}")
    print(f"  Qualifying fast phases (≥{MAGNITUDE_THRESHOLD}): {len(rightward_regions)}")
    if rightward_regions:
        intensities = [r['magnitude'] for r in rightward_regions]
        print(f"  Total intensity (sum): +{sum(intensities):.3f}")
        print(f"  Mean intensity: +{np.mean(intensities):.3f}")
        print(f"  Max intensity: +{max(intensities):.3f}")

    print(f"\nLeftward (decreasing X):")
    print(f"  Total monotonic segments: {len(left_all)}")
    print(f"  Qualifying fast phases (≥{MAGNITUDE_THRESHOLD}): {len(leftward_regions)}")
    if leftward_regions:
        intensities = [r['magnitude'] for r in leftward_regions]
        print(f"  Total intensity (sum): -{sum(intensities):.3f}")
        print(f"  Mean intensity: -{np.mean(intensities):.3f}")
        print(f"  Max intensity: -{max(intensities):.3f}")

    # ===== Classify dominant direction =====
    print(f"\n{'='*80}")
    print(f"DIRECTION CLASSIFICATION")
    print(f"{'='*80}")

    classification = classify_direction(rightward_regions, leftward_regions, CONFIDENCE_RATIO)

    print(f"  Rightward: count={classification['right_count']}, "
          f"mean intensity={classification['right_mean_intensity']:.3f}, "
          f"total intensity={classification['right_total_intensity']:.3f}")
    print(f"  Leftward:  count={classification['left_count']}, "
          f"mean intensity={classification['left_mean_intensity']:.3f}, "
          f"total intensity={classification['left_total_intensity']:.3f}")
    print(f"\n  Dominant direction: {classification['direction']}")
    print(f"  Reason: {classification['reason']}")

    if not classification['is_confident']:
        print(f"\n  ⚠️  WARNING: Classification is WEAK / MIXED")
        print(f"      The two directions are too close to call confidently.")
        print(f"      Treat the labeled direction as a best guess only.")
    else:
        print(f"\n  ✓ Classification is CONFIDENT")

    dominant_direction = classification['direction']

    # ===== Plotting =====
    print(f"\n{'='*80}\nGENERATING MOVEMENT PLOTS\n{'='*80}")

    fig, axes = plt.subplots(4, 1, figsize=(14, 22))
    ax1, ax2, ax3, ax4 = axes

    # Plot 1: Normalized X
    ax1.plot(frames, norm_x_values, 'b-', linewidth=2)
    ax1.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Center (0.5)')
    ax1.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Normalized X Position', fontsize=12, fontweight='bold')
    ax1.set_title('Horizontal Eye Movement (Normalized X vs Frame)', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 1)
    ax1.legend()
    ax1.text(0.02, 0.98, '0.0 = Far Left\n0.5 = Center\n1.0 = Far Right',
             transform=ax1.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Plot 2: Normalized Y
    ax2.plot(frames, norm_y_values, 'g-o', linewidth=2, markersize=4)
    ax2.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Center (0.5)')
    ax2.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Normalized Y Position', fontsize=12, fontweight='bold')
    ax2.set_title('Vertical Eye Movement (Normalized Y vs Frame)', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0.3, 0.7)
    ax2.legend()
    ax2.text(0.02, 0.98, '0.0 = Top\n0.5 = Center\n1.0 = Bottom',
             transform=ax2.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

    # ----- Plot 3: BOTH directions overlaid, dominant labeled -----
    ax3.plot(frames, norm_x_values, 'black', linewidth=2, marker='o', markersize=4, zorder=3)
    ax3.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, zorder=2)
    ax3.axhspan(0, 1, facecolor='lightgreen', alpha=0.2, zorder=1)

    # Shade rightward fast phases in one color, leftward in another
    for region in rightward_regions:
        ax3.axvspan(region['start_frame'], region['end_frame'],
                    facecolor='red', alpha=0.35, zorder=2)
        mid_frame = (region['start_frame'] + region['end_frame']) / 2
        mid_x = (region['start_x'] + region['end_x']) / 2
        frames_text = f"{region['num_frames']}f"
        ax3.annotate(f"+{region['magnitude']:.3f}\n({frames_text})",
                     xy=(mid_frame, mid_x), fontsize=8, fontweight='bold',
                     color='darkred',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7),
                     zorder=4)

    for region in leftward_regions:
        ax3.axvspan(region['start_frame'], region['end_frame'],
                    facecolor='purple', alpha=0.35, zorder=2)
        mid_frame = (region['start_frame'] + region['end_frame']) / 2
        mid_x = (region['start_x'] + region['end_x']) / 2
        frames_text = f"{region['num_frames']}f"
        ax3.annotate(f"-{region['magnitude']:.3f}\n({frames_text})",
                     xy=(mid_frame, mid_x), fontsize=8, fontweight='bold',
                     color='indigo',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='lavender', alpha=0.7),
                     zorder=4)

    # Title shows dominant direction with confidence flag
    if dominant_direction is None:
        dominant_label = "UNDETERMINED"
    else:
        dominant_label = dominant_direction.upper()
    conf_label = "CONFIDENT" if classification['is_confident'] else "WEAK / MIXED"
    ax3.set_title(f'Both Directions Detected — Dominant: {dominant_label}  [{conf_label}]\n'
                  f'Right: {classification["right_count"]} (mean={classification["right_mean_intensity"]:.3f})  |  '
                  f'Left: {classification["left_count"]} (mean={classification["left_mean_intensity"]:.3f})',
                  fontsize=13, fontweight='bold')

    ax3.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Normalized X Position', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, zorder=0)
    ax3.set_ylim(0, 1)

    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    legend_elements = [
        Patch(facecolor='red', alpha=0.35, label=f'Rightward fast phase (+x)'),
        Patch(facecolor='purple', alpha=0.35, label=f'Leftward fast phase (-x)'),
        Line2D([0], [0], color='r', linestyle='--', alpha=0.5, label='Center (0.5)'),
    ]
    ax3.legend(handles=legend_elements, loc='upper right')

    # Confidence banner
    banner_text = f'Dominant: {dominant_label}\n{classification["reason"]}'
    banner_color = 'lightyellow' if classification['is_confident'] else 'mistyrose'
    ax3.text(0.02, 0.98, banner_text,
             transform=ax3.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor=banner_color, alpha=0.85))

    # ----- Plot 4: clean view of dominant direction's fast + slow phases -----
    if dominant_direction == 'rightward':
        dominant_regions = rightward_regions
        slow_label = 'Slow Phase (leftward drift)'
        fast_label = 'Fast Phase (rightward)'
    elif dominant_direction == 'leftward':
        dominant_regions = leftward_regions
        slow_label = 'Slow Phase (rightward drift)'
        fast_label = 'Fast Phase (leftward)'
    else:
        dominant_regions = []
        slow_label = 'Slow Phase'
        fast_label = 'Fast Phase'

    FRAMES_TO_EXCLUDE_BEFORE_FIRST = 2

    if len(dominant_regions) > 0:
        first_red_start_frame = dominant_regions[0]['start_frame']
        connection_start_frame = max(frames[0], first_red_start_frame - FRAMES_TO_EXCLUDE_BEFORE_FIRST)

        # Initial slow phase connection
        if connection_start_frame < first_red_start_frame and connection_start_frame in frames:
            start_idx = frames.index(connection_start_frame)
            start_x = norm_x_values[start_idx]
            first_red_x = dominant_regions[0]['start_x']
            ax4.plot([connection_start_frame, first_red_start_frame], [start_x, first_red_x],
                     color='blue', linewidth=3, linestyle='-', alpha=0.8, label=slow_label)

        # Connections between consecutive fast phases
        for i in range(len(dominant_regions) - 1):
            end_frame_1 = dominant_regions[i]['end_frame']
            end_x_1 = dominant_regions[i]['end_x']
            start_frame_2 = dominant_regions[i + 1]['start_frame']
            start_x_2 = dominant_regions[i + 1]['start_x']
            label = slow_label if (i == 0 and connection_start_frame >= first_red_start_frame) else None
            ax4.plot([end_frame_1, start_frame_2], [end_x_1, start_x_2],
                     color='blue', linewidth=3, linestyle='-', alpha=0.8,
                     label=label)

        # Fast phase lines
        for i, region in enumerate(dominant_regions):
            ax4.plot([region['start_frame'], region['end_frame']],
                     [region['start_x'], region['end_x']],
                     color='red', linewidth=3, linestyle='-', alpha=0.8,
                     label=fast_label if i == 0 else None)

    ax4.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Normalized X Position', fontsize=12, fontweight='bold')
    ax4.set_title(f'Clean View — Dominant Direction: {dominant_label}  [{conf_label}]',
                  fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim(0, 1)
    if len(dominant_regions) > 0:
        ax4.legend(loc='upper right')

    plt.tight_layout()
    plt.savefig('eye_movement_plots_with_analysis.png', dpi=150, bbox_inches='tight')
    print(f"✓ Plots saved to 'eye_movement_plots_with_analysis.png'")
    plt.show()

    print(f"{'='*80}")
else:
    print(f"\nNo valid tracking data collected.\n{'='*80}")