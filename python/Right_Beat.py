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
    """
    Detects eyes and crops them from original frame
    """
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

    # Purple background
    purple_bg = np.zeros_like(frame)
    purple_bg[:] = (128, 0, 128)  # Purple in BGR

    # ---- LEFT EYE ----
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [left_eye_poly], 255)
    eye = np.where(mask[:, :, None] == 255, frame, purple_bg)
    x, y, w_, h_ = cv2.boundingRect(left_eye_poly)
    eye_crop = eye[y:y+h_, x:x+w_]

    # Adjust iris points to cropped coordinate system
    iris_points_adjusted = left_iris_poly - [x, y]

    return eye_crop, iris_points_adjusted, frame

# ================= Find regions with RGB > 100 in inverted image =================
def find_rgb_greater_than_100(inverted_eye, original_eye, print_info=False):
    """
    Find all pixels in inverted image where average RGB > 100,
    excluding the green background (inverted purple) and pink/purple filler.

    Args:
        inverted_eye: Inverted eye image
        original_eye: Original cropped eye image (to check for pink/purple filler)

    Returns:
        mask: Boolean mask of pixels where RGB > 100 (excluding background and filler)
        count: Number of such pixels
    """
    height, width = inverted_eye.shape[:2]

    # Calculate average RGB for each pixel
    avg_rgb = np.mean(inverted_eye, axis=2)

    # Identify green background (inverted purple: 128,0,128 becomes 127,255,127)
    green_bg_mask = (
        (inverted_eye[:, :, 0] == 127) &  # B channel
        (inverted_eye[:, :, 1] == 255) &  # G channel
        (inverted_eye[:, :, 2] == 127)    # R channel
    )

    # Identify pink/purple filler regions in the original image
    # Purple filler is (128, 0, 128) in BGR
    purple_filler_mask = (
        (original_eye[:, :, 0] == 128) &  # B channel
        (original_eye[:, :, 1] == 0) &    # G channel
        (original_eye[:, :, 2] == 128)    # R channel
    )

    # Also check for near-purple colors (with some tolerance)
    b_channel = original_eye[:, :, 0]
    g_channel = original_eye[:, :, 1]
    r_channel = original_eye[:, :, 2]

    # Tolerance of ±5 for each channel
    tolerance = 5
    near_purple_mask = (
        (np.abs(b_channel - 128) <= tolerance) &
        (np.abs(g_channel - 0) <= tolerance) &
        (np.abs(r_channel - 128) <= tolerance)
    )

    # Combine exact and near-purple masks
    filler_mask = purple_filler_mask | near_purple_mask

    RGB_THRESHOLD = 10

    # Create mask for pixels with RGB > 10, excluding green background AND filler
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

# ================= Filter RGB mask based on grid criteria =================
def filter_rgb_mask_by_grid(inverted_eye, rgb_mask, print_info=False):
    """
    Apply 20x20 grid on the eye image. For each vertical column:
    - If it has 10+ horizontal grids with RGB > 100: keep highlighting
    - If it has < 10 horizontal grids with RGB > 100: remove highlighting

    Returns:
        filtered_mask: Boolean mask with highlighting only in valid vertical strips
    """
    height, width = inverted_eye.shape[:2]

    # Calculate grid dimensions (20x20 grid)
    grid_rows = 40
    grid_cols = 40

    grid_height = height / grid_rows
    grid_width = width / grid_cols

    if print_info:
        print(f"\n  Grid Filtering Analysis:")
        print(f"    Image size: {width}x{height}")
        print(f"    Grid size: {grid_cols} columns x {grid_rows} rows")
        print(f"    Each grid cell: {grid_width:.1f}x{grid_height:.1f} pixels")

    # Create grid map: for each grid cell, check if it contains RGB > 100 pixels
    grid_map = np.zeros((grid_rows, grid_cols), dtype=bool)

    for col in range(grid_cols):
        for row in range(grid_rows):
            # Calculate grid cell boundaries
            x_start = int(col * grid_width)
            x_end = int((col + 1) * grid_width) if col < grid_cols - 1 else width
            y_start = int(row * grid_height)
            y_end = int((row + 1) * grid_height) if row < grid_rows - 1 else height

            # Check if this grid cell has any RGB > 100 pixels
            grid_cell_mask = rgb_mask[y_start:y_end, x_start:x_end]
            grid_map[row, col] = np.any(grid_cell_mask)

    # Create filtered mask (start with copy of original)
    filtered_mask = rgb_mask.copy()

    # Check each vertical column
    valid_columns = 0
    removed_columns = 0

    for col in range(grid_cols):
        # Count how many horizontal grids in this column have RGB > 100
        count = np.sum(grid_map[:, col])

        # If less than 10 grids, remove highlighting from entire vertical strip
        if count < 20:
            x_start = int(col * grid_width)
            x_end = int((col + 1) * grid_width) if col < grid_cols - 1 else width

            # Remove highlighting for this entire vertical strip
            filtered_mask[:, x_start:x_end] = False
            removed_columns += 1

            if print_info:
                print(f"    Column {col}: {count} grids with RGB > 100 (< 10) → REMOVED")
        else:
            valid_columns += 1
            if print_info:
                print(f"    Column {col}: {count} grids with RGB > 100 (≥ 10) → KEPT")

    if print_info:
        original_pixels = np.sum(rgb_mask)
        filtered_pixels = np.sum(filtered_mask)
        removed_pixels = original_pixels - filtered_pixels
        print(f"\n  Filtering Results:")
        print(f"    Valid columns (≥10 grids): {valid_columns}")
        print(f"    Removed columns (<10 grids): {removed_columns}")
        print(f"    Original highlighted pixels: {original_pixels}")
        print(f"    Filtered highlighted pixels: {filtered_pixels}")
        print(f"    Removed pixels: {removed_pixels} ({removed_pixels/original_pixels*100:.1f}%)")

    return filtered_mask

# ================= Find largest cluster in filtered mask =================
def find_largest_cluster(filtered_mask, original_eye, print_info=False):
    """
    Find the largest connected cluster in the filtered mask,
    excluding pixels that are part of the pink/purple filler background.

    Args:
        filtered_mask: Boolean mask of filtered RGB > 100 pixels
        original_eye: Original cropped eye image (to check for pink/purple pixels)

    Returns:
        largest_cluster_mask: Boolean mask of the largest cluster (excluding filler)
        cluster_size: Number of pixels in the largest cluster
    """
    from scipy import ndimage

    if not filtered_mask.any():
        if print_info:
            print(f"\n  Largest Cluster Analysis:")
            print(f"    No pixels in filtered mask")
        return np.zeros_like(filtered_mask, dtype=bool), 0

    # Identify pink/purple filler regions in the original image
    # Purple filler is (128, 0, 128) in BGR
    purple_filler_mask = (
        (original_eye[:, :, 0] == 128) &  # B channel
        (original_eye[:, :, 1] == 0) &    # G channel
        (original_eye[:, :, 2] == 128)    # R channel
    )

    # Also check for near-purple colors (with some tolerance)
    # This catches any slightly different purple shades due to compression/interpolation
    b_channel = original_eye[:, :, 0]
    g_channel = original_eye[:, :, 1]
    r_channel = original_eye[:, :, 2]

    # Tolerance of ±5 for each channel
    tolerance = 5
    near_purple_mask = (
        (np.abs(b_channel - 128) <= tolerance) &
        (np.abs(g_channel - 0) <= tolerance) &
        (np.abs(r_channel - 128) <= tolerance)
    )

    # Combine exact and near-purple masks
    filler_mask = purple_filler_mask | near_purple_mask

    # Exclude filler regions from filtered mask
    filtered_mask_no_filler = filtered_mask & (~filler_mask)

    if print_info:
        total_filtered = np.sum(filtered_mask)
        filler_pixels = np.sum(filtered_mask & filler_mask)
        remaining_pixels = np.sum(filtered_mask_no_filler)
        print(f"\n  Filler Exclusion:")
        print(f"    Total filtered pixels: {total_filtered}")
        print(f"    Filler pixels (purple) removed: {filler_pixels}")
        print(f"    Remaining pixels after exclusion: {remaining_pixels}")

    if not filtered_mask_no_filler.any():
        if print_info:
            print(f"\n  Largest Cluster Analysis:")
            print(f"    No pixels remaining after filler exclusion")
        return np.zeros_like(filtered_mask, dtype=bool), 0

    # Label connected components (excluding filler)
    labeled_array, num_features = ndimage.label(filtered_mask_no_filler)

    if num_features == 0:
        if print_info:
            print(f"\n  Largest Cluster Analysis:")
            print(f"    No clusters found")
        return np.zeros_like(filtered_mask, dtype=bool), 0

    # Find the largest component
    component_sizes = np.bincount(labeled_array.ravel())
    component_sizes[0] = 0  # Ignore background (label 0)

    if len(component_sizes) <= 1:
        if print_info:
            print(f"\n  Largest Cluster Analysis:")
            print(f"    No valid clusters found")
        return np.zeros_like(filtered_mask, dtype=bool), 0

    largest_component_label = component_sizes.argmax()
    largest_cluster_mask = (labeled_array == largest_component_label)
    cluster_size = component_sizes[largest_component_label]

    if print_info:
        total_non_filler_pixels = np.sum(filtered_mask_no_filler)
        print(f"\n  Largest Cluster Analysis:")
        print(f"    Total non-filler pixels: {total_non_filler_pixels}")
        print(f"    Number of clusters found: {num_features}")
        print(f"    Largest cluster size: {cluster_size} pixels")
        if total_non_filler_pixels > 0:
            print(f"    Percentage of non-filler pixels: {cluster_size / total_non_filler_pixels * 100:.1f}%")

    return largest_cluster_mask, cluster_size

# ================= Calculate centroid of cluster =================
def calculate_centroid(cluster_mask):
    """
    Calculate the centroid (center of mass) of a cluster.

    Args:
        cluster_mask: Boolean mask of the cluster

    Returns:
        centroid: (x, y) coordinates of the centroid, or None if cluster is empty
    """
    if not cluster_mask.any():
        return None

    # Get coordinates of all pixels in the cluster
    y_coords, x_coords = np.where(cluster_mask)

    # Calculate centroid as mean of all coordinates
    centroid_x = int(np.mean(x_coords))
    centroid_y = int(np.mean(y_coords))

    return (centroid_x, centroid_y)

# ================= Find strongest continuous cluster of yellow OR red vertical strips =================
def find_yellow_cluster_boundaries(rgb_less_than_100_mask, largest_cluster_mask, height, width, print_info=False):
    """
    Find the strongest continuous cluster of vertical strips containing yellow OR red pixels.

    Args:
        rgb_less_than_100_mask: Boolean mask of yellow pixels
        largest_cluster_mask: Boolean mask of red cluster pixels
        height, width: Dimensions of the image
        print_info: Whether to print debug information

    Returns:
        cluster_left_x, cluster_right_x: X boundaries of the strongest cluster (or None if not found)
    """
    # Grid configuration (same as used elsewhere)
    grid_cols = 200
    grid_width = width / grid_cols

    # Check which vertical strips contain yellow OR red pixels
    strip_has_content = []
    for col in range(grid_cols):
        x_start = int(col * grid_width)
        x_end = int((col + 1) * grid_width) if col < grid_cols - 1 else width

        # Check if this vertical strip has any yellow pixels OR red pixels
        yellow_region = rgb_less_than_100_mask[:, x_start:x_end]
        red_region = largest_cluster_mask[:, x_start:x_end]
        has_content = np.any(yellow_region) or np.any(red_region)
        strip_has_content.append(has_content)

    if print_info:
        print(f"\n  Yellow/Red Cluster Detection:")
        print(f"    Grid columns: {grid_cols}")
        print(f"    Strips with yellow OR red: {sum(strip_has_content)}/{grid_cols}")

    # Find all continuous sequences (clusters) of strips with yellow OR red
    clusters = []
    current_cluster_start = None

    for col in range(grid_cols):
        if strip_has_content[col]:
            if current_cluster_start is None:
                # Start a new cluster
                current_cluster_start = col
        else:
            if current_cluster_start is not None:
                # End the current cluster
                clusters.append((current_cluster_start, col - 1))
                current_cluster_start = None

    # Don't forget the last cluster if it extends to the end
    if current_cluster_start is not None:
        clusters.append((current_cluster_start, grid_cols - 1))

    if len(clusters) == 0:
        if print_info:
            print(f"    No yellow/red clusters found")
        return None, None

    # Find the longest (strongest) cluster
    cluster_lengths = [(end - start + 1) for start, end in clusters]
    longest_cluster_idx = np.argmax(cluster_lengths)
    strongest_cluster = clusters[longest_cluster_idx]

    if print_info:
        print(f"    Found {len(clusters)} cluster(s):")
        for i, (start, end) in enumerate(clusters):
            length = end - start + 1
            marker = " ← STRONGEST" if i == longest_cluster_idx else ""
            print(f"      Cluster {i+1}: strips [{start}→{end}], length={length}{marker}")

    # Convert grid column indices to pixel X coordinates
    cluster_start_col, cluster_end_col = strongest_cluster
    cluster_left_x = int(cluster_start_col * grid_width)
    cluster_right_x = int((cluster_end_col + 1) * grid_width) if cluster_end_col < grid_cols - 1 else width - 1

    if print_info:
        print(f"    Strongest cluster boundaries: X=[{cluster_left_x}, {cluster_right_x}]")

    return cluster_left_x, cluster_right_x

# ================= Display results =================
def display_frame_results(frame_num, original_eye, adjusted_eye, inverted_eye, largest_cluster_mask, inverted_eye_for_rgb):
    """Display 4 images: original, adjusted, inverted, and visualization on WHITE background with normalized position

    Returns:
        tracking_info: dict with frame data for tracking (or None if no valid data)
    """
    tracking_info = None  # Will be populated if we have valid tracking data
    fig, axes = plt.subplots(1, 4, figsize=(24, 6))

    # Image 1: Original cropped eye
    axes[0].imshow(cv2.cvtColor(original_eye, cv2.COLOR_BGR2RGB))
    axes[0].set_title(f"Frame {frame_num}: Original Cropped Eye",
                      fontsize=14, fontweight='bold')
    axes[0].axis('off')

    # Image 2: After alpha=3, beta=-100 adjustment
    axes[1].imshow(cv2.cvtColor(adjusted_eye, cv2.COLOR_BGR2RGB))
    axes[1].set_title(f"Frame {frame_num}: After α=3, β=-100",
                      fontsize=14, fontweight='bold')
    axes[1].axis('off')

    # Image 3: After color inversion
    axes[2].imshow(cv2.cvtColor(inverted_eye, cv2.COLOR_BGR2RGB))
    axes[2].set_title(f"Frame {frame_num}: After Color Inversion",
                      fontsize=14, fontweight='bold')
    axes[2].axis('off')

    # Image 4: Yellow overlay for RGB < 10 + Red overlay for largest cluster + 20x20 grid + Centroid
    # Use WHITE background instead of original eye image
    height, width = inverted_eye_for_rgb.shape[:2]
    highlighted = np.ones((height, width, 3), dtype=np.uint8) * 255  # White background

    avg_rgb = np.mean(inverted_eye_for_rgb, axis=2)

    # Identify green background (inverted purple)
    green_bg_mask = (
        (inverted_eye_for_rgb[:, :, 0] == 127) &  # B channel
        (inverted_eye_for_rgb[:, :, 1] == 255) &  # G channel
        (inverted_eye_for_rgb[:, :, 2] == 127)    # R channel
    )

    # Create mask for RGB < 10 (excluding background)
    rgb_less_than_100_mask = (avg_rgb < 10) & (~green_bg_mask)

    # Paint yellow directly on white background
    highlighted[rgb_less_than_100_mask] = [0, 255, 255]  # Yellow in BGR

    # Paint red directly on white background
    highlighted[largest_cluster_mask] = [0, 0, 255]  # Red in BGR

    # Calculate and draw centroid
    centroid = calculate_centroid(largest_cluster_mask)
    centroid_text = ""
    normalized_pos_text = ""

    # Find yellow/red region cluster boundaries using grid-based approach
    cluster_left_x, cluster_right_x = find_yellow_cluster_boundaries(
        rgb_less_than_100_mask, largest_cluster_mask, height, width, print_info=True)

    if cluster_left_x is not None and cluster_right_x is not None:
        # Draw vertical lines to mark cluster boundaries
        cv2.line(highlighted, (cluster_left_x, 0), (cluster_left_x, height - 1),
                color=(0, 255, 0), thickness=2)  # Green line for left boundary
        cv2.line(highlighted, (cluster_right_x, 0), (cluster_right_x, height - 1),
                color=(0, 255, 0), thickness=2)  # Green line for right boundary

        print(f"    Yellow/Red cluster X boundaries: [{cluster_left_x}, {cluster_right_x}]")
        print(f"    Cropped eye image dimensions: {width}x{height}")

        if centroid is not None:
            centroid_x, centroid_y = centroid

            # Calculate normalized X position within yellow/red cluster boundaries
            yellow_width = cluster_right_x - cluster_left_x

            if yellow_width > 0:
                normalized_x = (centroid_x - cluster_left_x) / yellow_width
            else:
                normalized_x = 0.5

            # Calculate normalized Y position within FULL cropped eye image
            normalized_y = centroid_y / height

            # Clamp values to [0, 1] range in case centroid is slightly outside
            normalized_x = max(0.0, min(1.0, normalized_x))
            normalized_y = max(0.0, min(1.0, normalized_y))

            # Draw magenta dot at centroid (larger and more visible)
            cv2.circle(highlighted, (centroid_x, centroid_y), radius=5,
                      color=(255, 0, 255), thickness=-1)  # Magenta in BGR, filled circle
            # Draw a white outline for better visibility
            cv2.circle(highlighted, (centroid_x, centroid_y), radius=6,
                      color=(0, 0, 0), thickness=1)  # Black outline for contrast on white

            centroid_text = f", Centroid: ({centroid_x}, {centroid_y})"
            normalized_pos_text = f", Normalized: ({normalized_x:.2f}, {normalized_y:.2f})"

            print(f"    Centroid coordinates: ({centroid_x}, {centroid_y})")
            print(f"    Normalized position: ({normalized_x:.3f}, {normalized_y:.3f})")
            print(f"      → Horizontal: {normalized_x:.1%} from left edge of yellow/red cluster")
            print(f"      → Vertical: {normalized_y:.1%} from top of cropped eye image")

            # Store tracking data
            tracking_info = {
                'frame': frame_num,
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'normalized_x': normalized_x,
                'normalized_y': normalized_y,
                'left_end_x': cluster_left_x,
                'right_end_x': cluster_right_x,
                'top_end_y': 0,
                'bottom_end_y': height - 1
            }
    else:
        print(f"    No yellow/red cluster found in this frame")
        if centroid is not None:
            centroid_x, centroid_y = centroid
            cv2.circle(highlighted, (centroid_x, centroid_y), radius=5,
                      color=(255, 0, 255), thickness=-1)
            cv2.circle(highlighted, (centroid_x, centroid_y), radius=6,
                      color=(0, 0, 0), thickness=1)
            centroid_text = f", Centroid: ({centroid_x}, {centroid_y})"

    # Draw 20x20 grid as black lines
    grid_rows = 40
    grid_cols = 40

    grid_height = height / grid_rows
    grid_width = width / grid_cols

    # Draw vertical lines
    for col in range(1, grid_cols):
        x = int(col * grid_width)
        cv2.line(highlighted, (x, 0), (x, height - 1),
                color=(0, 0, 0), thickness=1)  # Black in BGR

    # Draw horizontal lines
    for row in range(1, grid_rows):
        y = int(row * grid_height)
        cv2.line(highlighted, (0, y), (width - 1, y),
                color=(0, 0, 0), thickness=1)  # Black in BGR

    axes[3].imshow(cv2.cvtColor(highlighted, cv2.COLOR_BGR2RGB))
    cluster_pixels = np.sum(largest_cluster_mask)
    rgb_less_pixels = np.sum(rgb_less_than_100_mask)
    axes[3].set_title(f"Frame {frame_num}: Yellow + Red Cluster + Grid + Centroid (Magenta) + Boundaries (Green)\n(Yellow: {rgb_less_pixels}px, Red: {cluster_pixels}px{centroid_text}{normalized_pos_text})",
                      fontsize=14, fontweight='bold')
    axes[3].axis('off')

    plt.tight_layout()
    plt.show()

    return tracking_info

# ================= MAIN =================
video_path = '/content/drive/MyDrive/Dataset/6 March/IMG_3299.MOV'
cap = cv2.VideoCapture(video_path)

# Frames to display (only first 10 frames)
DISPLAY_FRAMES = [300, 302, 303, 304, 305, 306, 307, 308, 309, 310]
MAX_FRAME = 500  # Process 500 frames for tracking data

frame_count = 0

# Data collection for tracking
tracking_data = []  # Will store: (frame_num, centroid_x, centroid_y, normalized_x, normalized_y, left_x, right_x)

print("="*80)
print("EYE TRACKING WITH NORMALIZED POSITION IN YELLOW/RED REGION")
print("="*80)
print(f"Processing first {MAX_FRAME} frames for tracking data")
print(f"Will DISPLAY only frames: {', '.join(map(str, DISPLAY_FRAMES))}")
print(f"Will TRACK all {MAX_FRAME} frames and generate movement plots")
print(f"\nProcessing Pipeline:")
print(f"  1. Crop left eye with purple background")
print(f"  2. Apply alpha=3, beta=-100 (increase contrast, darken)")
print(f"  3. Invert colors (255 - pixel_value)")
print(f"  4. Find regions where average RGB > 100 (excluding background and filler)")
print(f"  5. Apply 40x40 grid to filter vertical columns")
print(f"  6. Keep highlighting only in columns with 20+ grids having RGB > 100")
print(f"  7. Find largest connected cluster (excluding pink/purple filler)")
print(f"  8. Calculate centroid of largest cluster")
print(f"  9. Find strongest continuous cluster of yellow OR red vertical strips (grid-based)")
print(f" 10. Mark cluster boundaries with green lines (left_x, right_x)")
print(f" 11. Normalize centroid position within cluster: (0.0=left, 0.5=center, 1.0=right)")
print(f" 12. Display (first 10 frames only): WHITE background + Yellow + Red + Grid + Centroid + Boundaries")
print(f" 13. Track all {MAX_FRAME} frames and plot horizontal/vertical movement")
print(f" 14. Detect RIGHTWARD fast phases (increase ≥0.04) and LEFTWARD slow phases")
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

        # Detect and crop eye
        eye_crop, iris_points, original_frame = detect_and_crop_eyes(face_mesh, frame)

        # Skip if detection failed
        if eye_crop is None:
            if frame_count > MAX_FRAME:
                break
            continue

        # Process ALL frames for tracking data
        # Step 1: Original cropped eye
        original_eye = eye_crop.copy()

        # Step 2: Apply alpha=3, beta=-100
        alpha = 3.0
        beta = -100
        adjusted_eye = cv2.convertScaleAbs(eye_crop, alpha=alpha, beta=beta)

        # Step 3: Invert colors
        inverted_eye = 255 - adjusted_eye

        # Step 4: Find regions where RGB > 100 (excluding filler)
        print_info = (frame_count in DISPLAY_FRAMES)
        rgb_mask, pixel_count = find_rgb_greater_than_100(inverted_eye, original_eye, print_info=print_info)

        # Step 5: Filter RGB mask based on grid criteria
        filtered_mask = filter_rgb_mask_by_grid(inverted_eye, rgb_mask, print_info=print_info)

        # Step 6: Find largest cluster in filtered mask (excluding pink/purple filler)
        largest_cluster_mask, cluster_size = find_largest_cluster(filtered_mask, original_eye, print_info=print_info)

        # Calculate tracking data for this frame
        centroid = calculate_centroid(largest_cluster_mask)

        # Calculate yellow region boundaries and normalized position using cluster approach
        height, width = inverted_eye.shape[:2]
        avg_rgb = np.mean(inverted_eye, axis=2)
        green_bg_mask = (
            (inverted_eye[:, :, 0] == 127) &
            (inverted_eye[:, :, 1] == 255) &
            (inverted_eye[:, :, 2] == 127)
        )
        rgb_less_than_100_mask = (avg_rgb < 10) & (~green_bg_mask)

        # Use cluster-based boundary detection (now includes red pixels)
        cluster_left_x, cluster_right_x = find_yellow_cluster_boundaries(
            rgb_less_than_100_mask, largest_cluster_mask, height, width, print_info=False)

        if cluster_left_x is not None and cluster_right_x is not None and centroid is not None:
            centroid_x, centroid_y = centroid

            yellow_width = cluster_right_x - cluster_left_x

            if yellow_width > 0:
                normalized_x = (centroid_x - cluster_left_x) / yellow_width
            else:
                normalized_x = 0.5

            # Y normalization uses FULL cropped eye image height
            normalized_y = centroid_y / height

            normalized_x = max(0.0, min(1.0, normalized_x))
            normalized_y = max(0.0, min(1.0, normalized_y))

            # Store tracking data
            tracking_info = {
                'frame': frame_count,
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'normalized_x': normalized_x,
                'normalized_y': normalized_y,
                'left_end_x': cluster_left_x,
                'right_end_x': cluster_right_x,
                'top_end_y': 0,
                'bottom_end_y': height - 1
            }
            tracking_data.append(tracking_info)

            if print_info:
                print(f"    Frame {frame_count} tracking: Normalized position = ({normalized_x:.3f}, {normalized_y:.3f})")

        # Check if this is a frame we want to DISPLAY
        if frame_count in DISPLAY_FRAMES:
            print(f"\n{'='*80}")
            print(f"DISPLAYING FRAME {frame_count}")
            print(f"{'='*80}")

            # Display all four versions
            tracking_info = display_frame_results(frame_count, original_eye, adjusted_eye, inverted_eye,
                                largest_cluster_mask, inverted_eye)

            print(f"\nFrame {frame_count} display complete")
            print(f"{'='*80}")

        # Stop after MAX_FRAME
        if frame_count >= MAX_FRAME:
            break

cap.release()

print(f"\n{'='*80}")
print(f"Processing complete!")
print(f"{'='*80}")

# Print tracking summary
if len(tracking_data) > 0:
    print(f"\n{'='*80}")
    print(f"TRACKING SUMMARY ({len(tracking_data)} frames with valid data)")
    print(f"{'='*80}")

    # Extract data for plotting
    frames = [d['frame'] for d in tracking_data]
    norm_x_values = [d['normalized_x'] for d in tracking_data]
    norm_y_values = [d['normalized_y'] for d in tracking_data]

    print(f"\nNormalized X Position (Horizontal):")
    print(f"  Mean: {np.mean(norm_x_values):.3f}")
    print(f"  Std Dev: {np.std(norm_x_values):.3f}")
    print(f"  Min: {np.min(norm_x_values):.3f} (Frame {tracking_data[np.argmin(norm_x_values)]['frame']})")
    print(f"  Max: {np.max(norm_x_values):.3f} (Frame {tracking_data[np.argmax(norm_x_values)]['frame']})")
    print(f"  Range: {np.max(norm_x_values) - np.min(norm_x_values):.3f}")

    print(f"\nNormalized Y Position (Vertical):")
    print(f"  Mean: {np.mean(norm_y_values):.3f}")
    print(f"  Std Dev: {np.std(norm_y_values):.3f}")
    print(f"  Min: {np.min(norm_y_values):.3f} (Frame {tracking_data[np.argmin(norm_y_values)]['frame']})")
    print(f"  Max: {np.max(norm_y_values):.3f} (Frame {tracking_data[np.argmax(norm_y_values)]['frame']})")
    print(f"  Range: {np.max(norm_y_values) - np.min(norm_y_values):.3f}")

    # Save to CSV
    import csv
    csv_filename = 'eye_tracking_data.csv'
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = ['frame', 'centroid_x', 'centroid_y', 'normalized_x', 'normalized_y',
                     'left_end_x', 'right_end_x', 'top_end_y', 'bottom_end_y']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tracking_data)

    print(f"\n✓ Tracking data saved to '{csv_filename}'")

    # ================= DETECT RIGHTWARD FAST PHASES (INCREASES OF +0.04) =================
    print(f"\n{'='*80}")
    print(f"DETECTING SIGNIFICANT RIGHTWARD MOVEMENTS (+0.04 increase = FAST PHASE)")
    print(f"Phase 1: Connect all RIGHTWARD (incrementing) frames into continuous lines")
    print(f"Phase 2: Filter lines with total INCREASE ≥ 0.04")
    print(f"{'='*80}")

    # Phase 1: Find all continuous RIGHTWARD movement segments
    rightward_segments = []
    current_segment = None

    for i in range(len(norm_x_values) - 1):
        x_current = norm_x_values[i]
        x_next = norm_x_values[i + 1]

        # Check if next point is further RIGHT (rightward movement = INCREASE in x)
        if x_next > x_current:
            if current_segment is None:
                # Start a new segment
                current_segment = {
                    'start_idx': i,
                    'end_idx': i + 1,
                    'start_frame': frames[i],
                    'end_frame': frames[i + 1],
                    'start_x': x_current,
                    'end_x': x_next
                }
            else:
                # Continue the current segment
                current_segment['end_idx'] = i + 1
                current_segment['end_frame'] = frames[i + 1]
                current_segment['end_x'] = x_next
        else:
            # Leftward or flat movement - end current segment if exists
            if current_segment is not None:
                rightward_segments.append(current_segment)
                current_segment = None

    # Don't forget the last segment if it extends to the end
    if current_segment is not None:
        rightward_segments.append(current_segment)

    print(f"\nPhase 1 Results:")
    print(f"  Total rightward segments found: {len(rightward_segments)}")

    # Phase 2: Filter segments by total INCREASE ≥ 0.04
    fast_phase_regions = []

    for idx, segment in enumerate(rightward_segments):
        total_increase = segment['end_x'] - segment['start_x']  # CHANGED: end - start for rightward
        num_frames = segment['end_idx'] - segment['start_idx']

        print(f"\n  Segment {idx + 1}:")
        print(f"    Frames: {segment['start_frame']} → {segment['end_frame']} ({num_frames} step{'s' if num_frames > 1 else ''})")
        print(f"    X position: {segment['start_x']:.3f} → {segment['end_x']:.3f}")
        print(f"    Total increase: +{total_increase:.3f}")

        if total_increase >= 0.03:
            fast_phase_regions.append({
                'start_frame': segment['start_frame'],
                'end_frame': segment['end_frame'],
                'start_x': segment['start_x'],
                'end_x': segment['end_x'],
                'increase': total_increase,
                'num_frames': num_frames
            })
            print(f"    ✓ QUALIFIES (≥ 0.04) - FAST PHASE - Will be marked RED")
        else:
            print(f"    ✗ Too small (< 0.04) - Will remain GREEN")

    print(f"\nPhase 2 Results:")
    if len(fast_phase_regions) == 0:
        print(f"  No rightward segments with increase ≥ 0.04 detected")
    else:
        print(f"  Fast phase segments (≥ 0.04 increase): {len(fast_phase_regions)}")
        print(f"  Average increase: +{np.mean([r['increase'] for r in fast_phase_regions]):.3f}")
        print(f"  Max increase: +{np.max([r['increase'] for r in fast_phase_regions]):.3f}")
        print(f"  Min increase: +{np.min([r['increase'] for r in fast_phase_regions]):.3f}")

    # Create plots
    print(f"\n{'='*80}")
    print(f"GENERATING MOVEMENT PLOTS")
    print(f"{'='*80}")

    fig, axes = plt.subplots(4, 1, figsize=(14, 20))
    ax1, ax2, ax3, ax4 = axes

    # Plot 1: Normalized X (Horizontal movement)
    ax1.plot(frames, norm_x_values, 'b-o', linewidth=2, markersize=4)
    ax1.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Center (0.5)')
    ax1.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Normalized X Position', fontsize=12, fontweight='bold')
    ax1.set_title('Horizontal Eye Movement (Normalized X Position vs Frame)',
                  fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 1)
    ax1.legend()

    # Add reference text
    ax1.text(0.02, 0.98, '0.0 = Far Left\n0.5 = Center\n1.0 = Far Right',
             transform=ax1.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Plot 2: Normalized Y (Vertical movement)
    ax2.plot(frames, norm_y_values, 'g-o', linewidth=2, markersize=4)
    ax2.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Center (0.5)')
    ax2.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Normalized Y Position', fontsize=12, fontweight='bold')
    ax2.set_title('Vertical Eye Movement (Normalized Y Position vs Frame)',
                  fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0.3, 0.7)
    ax2.legend()

    # Add reference text
    ax2.text(0.02, 0.98, '0.0 = Top\n0.5 = Center\n1.0 = Bottom',
             transform=ax2.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

    # Plot 3: Horizontal Movement Analysis with Color-Coded Regions
    # Plot the line first
    ax3.plot(frames, norm_x_values, 'black', linewidth=2, marker='o', markersize=4, zorder=3)
    ax3.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Center (0.5)', zorder=2)

    # Color the background regions
    # Start with green background for entire plot
    ax3.axhspan(0, 1, facecolor='lightgreen', alpha=0.3, zorder=1)

    # Highlight red regions where +0.04 INCREASE occurred (FAST PHASES - rightward jumps)
    for region in fast_phase_regions:
        start_frame = region['start_frame']
        end_frame = region['end_frame']
        ax3.axvspan(start_frame, end_frame, facecolor='red', alpha=0.4, zorder=2)

        # Add text annotation for this region
        mid_frame = (start_frame + end_frame) / 2
        mid_x = (region['start_x'] + region['end_x']) / 2
        frames_text = f"{region['num_frames']}f" if region['num_frames'] == 1 else f"{region['num_frames']}frames"
        ax3.annotate(f"+{region['increase']:.3f}\n({frames_text})",
                    xy=(mid_frame, mid_x),
                    fontsize=9,
                    fontweight='bold',
                    color='darkred',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                    zorder=4)

    # ================= CONNECT CONSECUTIVE RED STRIPES (SLOW PHASES) =================
    print(f"\nConnecting consecutive red stripes (fast phases) with slow phase lines...")

    # Exclude 2 frames before the first red stripe for connection
    FRAMES_TO_EXCLUDE_BEFORE_FIRST = 2

    # Find the starting point for connections (2 frames before first red stripe)
    if len(fast_phase_regions) > 0:
        first_red_start_frame = fast_phase_regions[0]['start_frame']
        connection_start_frame = max(frames[0], first_red_start_frame - FRAMES_TO_EXCLUDE_BEFORE_FIRST)

        print(f"  First red stripe starts at frame: {first_red_start_frame}")
        print(f"  Connection will start from frame: {connection_start_frame}")

        # Draw connecting lines between consecutive red stripes (SLOW PHASES - leftward drift)
        for i in range(len(fast_phase_regions) - 1):
            # End of current red stripe (FAST PHASE 1)
            end_frame_1 = fast_phase_regions[i]['end_frame']
            end_x_1 = fast_phase_regions[i]['end_x']

            # Start of next red stripe (FAST PHASE 2)
            start_frame_2 = fast_phase_regions[i + 1]['start_frame']
            start_x_2 = fast_phase_regions[i + 1]['start_x']

            # Draw connecting line (SLOW PHASE - leftward drift)
            ax3.plot([end_frame_1, start_frame_2], [end_x_1, start_x_2],
                    color='blue', linewidth=3, linestyle='-', alpha=0.7, zorder=5,
                    label='Slow Phase (leftward drift)' if i == 0 else '')

            print(f"  Connected: Frame {end_frame_1} (x={end_x_1:.3f}) → Frame {start_frame_2} (x={start_x_2:.3f})")

        # Also draw line from excluded start point to first red stripe (if needed)
        if connection_start_frame < first_red_start_frame:
            # Find X value at connection_start_frame
            start_idx = frames.index(connection_start_frame) if connection_start_frame in frames else 0
            start_x = norm_x_values[start_idx]
            first_red_x = fast_phase_regions[0]['start_x']

            ax3.plot([connection_start_frame, first_red_start_frame], [start_x, first_red_x],
                    color='blue', linewidth=3, linestyle='-', alpha=0.7, zorder=5)

            print(f"  Initial connection: Frame {connection_start_frame} (x={start_x:.3f}) → Frame {first_red_start_frame} (x={first_red_x:.3f})")

        print(f"  Total slow phase connections drawn: {len(fast_phase_regions)}")

    ax3.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Normalized X Position', fontsize=12, fontweight='bold')
    ax3.set_title('Horizontal Movement: Fast Phases (Red, Rightward ≥0.04) + Slow Phases (Blue, Leftward Drift)',
                  fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3, zorder=0)
    ax3.set_ylim(0, 1)

    # Create custom legend
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    legend_elements = [
        Patch(facecolor='lightgreen', alpha=0.3, label='Normal Movement'),
        Patch(facecolor='red', alpha=0.4, label='Fast Phase (≥0.04 rightward increase)'),
        Line2D([0], [0], color='blue', linewidth=3, alpha=0.7, label='Slow Phase (leftward drift)'),
        Line2D([0], [0], color='r', linestyle='--', alpha=0.5, label='Center (0.5)')
    ]
    ax3.legend(handles=legend_elements, loc='upper right')

    # Add reference text
    info_text = f'Fast Phases (Rightward): {len(fast_phase_regions)} detected\nSlow Phases (Leftward): Blue connecting lines'
    ax3.text(0.02, 0.98, info_text,
             transform=ax3.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))

    # ================= PLOT 4: CLEAN FAST + SLOW PHASE VISUALIZATION =================
    # Only show the fast phase lines (red stripes as lines) and slow phase connections (blue lines)
    # No background colors, no annotations, just the movement pattern

    print(f"\nGenerating Plot 4: Clean Fast + Slow Phase visualization...")

    # Draw slow phase connections first (blue lines - leftward drift)
    if len(fast_phase_regions) > 0:
        # Initial connection from excluded start to first fast phase
        first_red_start_frame = fast_phase_regions[0]['start_frame']
        connection_start_frame = max(frames[0], first_red_start_frame - FRAMES_TO_EXCLUDE_BEFORE_FIRST)

        if connection_start_frame < first_red_start_frame:
            start_idx = frames.index(connection_start_frame) if connection_start_frame in frames else 0
            start_x = norm_x_values[start_idx]
            first_red_x = fast_phase_regions[0]['start_x']
            ax4.plot([connection_start_frame, first_red_start_frame], [start_x, first_red_x],
                    color='blue', linewidth=3, linestyle='-', alpha=0.8, label='Slow Phase (leftward)')

        # Connections between consecutive fast phases
        for i in range(len(fast_phase_regions) - 1):
            end_frame_1 = fast_phase_regions[i]['end_frame']
            end_x_1 = fast_phase_regions[i]['end_x']
            start_frame_2 = fast_phase_regions[i + 1]['start_frame']
            start_x_2 = fast_phase_regions[i + 1]['start_x']

            ax4.plot([end_frame_1, start_frame_2], [end_x_1, start_x_2],
                    color='blue', linewidth=3, linestyle='-', alpha=0.8)

    # Draw fast phase lines (red lines showing the rightward segments)
    for i, region in enumerate(fast_phase_regions):
        start_frame = region['start_frame']
        end_frame = region['end_frame']
        start_x = region['start_x']
        end_x = region['end_x']

        ax4.plot([start_frame, end_frame], [start_x, end_x],
                color='red', linewidth=3, linestyle='-', alpha=0.8,
                label='Fast Phase (rightward)' if i == 0 else '')

    ax4.set_xlabel('Frame Number', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Normalized X Position', fontsize=12, fontweight='bold')
    ax4.set_title('Clean View: Fast Phases (Red, Rightward) + Slow Phases (Blue, Leftward) Only',
                  fontsize=14, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim(0, 1)
    ax4.legend(loc='upper right')

    print(f"  Plot 4 complete: {len(fast_phase_regions)} fast phases + {len(fast_phase_regions)} slow phase connections")

    plt.tight_layout()
    plt.savefig('eye_movement_plots_with_analysis.png', dpi=150, bbox_inches='tight')
    print(f"✓ Movement plots with analysis saved to 'eye_movement_plots_with_analysis.png'")
    plt.show()

    print(f"{'='*80}")
else:
    print(f"\nNo valid tracking data collected.")
    print(f"{'='*80}")



# ================= PLOT 5: SPV ANALYSIS WITH TIME AND DEGREE AXES =================
print(f"\n{'='*80}")
print(f"CALCULATING SPV (Slow Phase Velocity) FOR ALL SLOW PHASES")
print(f"{'='*80}")

# Constants for conversion
FPS = 30  # frames per second
DEG_PER_NORMALIZED = 193  # 1 normalized unit = 193 degrees
SPV_THRESHOLD = 25  # deg/sec - exclude SPV over this value for peak detection
MIN_BEAT_TIME_SEC = 0.1  # exclude beats shorter than this

# Calculate SPV for each slow phase (RIGHTWARD drift between leftward fast phases)
spv_data = []

if len(fast_phase_regions) > 0:
    # Initial slow phase (from excluded start to first fast phase)
    first_red_start_frame = fast_phase_regions[0]['start_frame']
    connection_start_frame = max(frames[0], first_red_start_frame - FRAMES_TO_EXCLUDE_BEFORE_FIRST)

    if connection_start_frame < first_red_start_frame:
        start_idx = frames.index(connection_start_frame) if connection_start_frame in frames else 0
        start_x = norm_x_values[start_idx]
        first_red_x = fast_phase_regions[0]['start_x']

        num_frames = first_red_start_frame - connection_start_frame
        normalized_diff = abs(first_red_x - start_x)

        # Convert to degrees and seconds
        deg_diff = normalized_diff * DEG_PER_NORMALIZED
        time_sec = num_frames / FPS

        # Calculate SPV in deg/sec
        spv = deg_diff / time_sec if time_sec > 0 else 0

        spv_data.append({
            'beat': 0,
            'start_frame': connection_start_frame,
            'end_frame': first_red_start_frame,
            'start_x': start_x,
            'end_x': first_red_x,
            'num_frames': num_frames,
            'normalized_diff': normalized_diff,
            'deg_diff': deg_diff,
            'time_sec': time_sec,
            'spv': spv
        })

    # Slow phases between consecutive fast phases
    for i in range(len(fast_phase_regions) - 1):
        end_frame_1 = fast_phase_regions[i]['end_frame']
        end_x_1 = fast_phase_regions[i]['end_x']
        start_frame_2 = fast_phase_regions[i + 1]['start_frame']
        start_x_2 = fast_phase_regions[i + 1]['start_x']

        num_frames = start_frame_2 - end_frame_1
        normalized_diff = abs(start_x_2 - end_x_1)

        # Convert to degrees and seconds
        deg_diff = normalized_diff * DEG_PER_NORMALIZED
        time_sec = num_frames / FPS

        # Calculate SPV in deg/sec
        spv = deg_diff / time_sec if time_sec > 0 else 0

        spv_data.append({
            'beat': i + 1,
            'start_frame': end_frame_1,
            'end_frame': start_frame_2,
            'start_x': end_x_1,
            'end_x': start_x_2,
            'num_frames': num_frames,
            'normalized_diff': normalized_diff,
            'deg_diff': deg_diff,
            'time_sec': time_sec,
            'spv': spv
        })

# Find peak SPV (only considering beats with time >= 0.1 sec and SPV <= threshold)
peak_spv_data = None
if len(spv_data) > 0:
    # Filter to only include valid beats
    valid_spv = [
        s for s in spv_data
        if s['spv'] <= SPV_THRESHOLD and s['time_sec'] >= MIN_BEAT_TIME_SEC
    ]

    if len(valid_spv) > 0:
        peak_spv_idx = np.argmax([s['spv'] for s in valid_spv])
        peak_spv_data = valid_spv[peak_spv_idx]

        print(f"\nPeak SPV detected (threshold: ≤{SPV_THRESHOLD} deg/sec, time: ≥{MIN_BEAT_TIME_SEC} sec):")
        print(f"  Beat: {peak_spv_data['beat']}")
        print(f"  SPV: {peak_spv_data['spv']:.2f} deg/sec")
        print(f"  Frames: {peak_spv_data['start_frame']} → {peak_spv_data['end_frame']}")
        print(f"  Time: {peak_spv_data['time_sec']:.3f} sec")
        print(f"  Angular displacement: {peak_spv_data['deg_diff']:.2f} degrees")

        # Report excluded beats
        excluded_spv = [
            s for s in spv_data
            if s['spv'] > SPV_THRESHOLD or s['time_sec'] < MIN_BEAT_TIME_SEC
        ]
        if len(excluded_spv) > 0:
            print(f"\n  Excluded {len(excluded_spv)} beat(s):")
            for exc in excluded_spv:
                reasons = []
                if exc['spv'] > SPV_THRESHOLD:
                    reasons.append(f"SPV > {SPV_THRESHOLD} deg/sec")
                if exc['time_sec'] < MIN_BEAT_TIME_SEC:
                    reasons.append(f"time < {MIN_BEAT_TIME_SEC} sec")
                print(f"    Beat {exc['beat']}: {exc['spv']:.2f} deg/sec, {exc['time_sec']:.3f} sec ({', '.join(reasons)})")
    else:
        print(f"\nNo valid SPV values found (all beats exceed {SPV_THRESHOLD} deg/sec and/or are shorter than {MIN_BEAT_TIME_SEC} sec)")

# ================= CREATE PLOT 5 =================
from matplotlib.patches import Rectangle

fig5, ax5 = plt.subplots(figsize=(14, 8))

# Convert all data to time (seconds) and degrees
frames_in_sec = np.array(frames) / FPS
norm_x_in_deg = np.array(norm_x_values) * DEG_PER_NORMALIZED

# Draw slow phase connections (blue lines - rightward drift)
if len(fast_phase_regions) > 0:
    # Initial connection from excluded start to first fast phase
    first_red_start_frame = fast_phase_regions[0]['start_frame']
    connection_start_frame = max(frames[0], first_red_start_frame - FRAMES_TO_EXCLUDE_BEFORE_FIRST)

    if connection_start_frame < first_red_start_frame:
        start_idx = frames.index(connection_start_frame) if connection_start_frame in frames else 0
        start_x_deg = norm_x_values[start_idx] * DEG_PER_NORMALIZED
        first_red_x_deg = fast_phase_regions[0]['start_x'] * DEG_PER_NORMALIZED

        start_time = connection_start_frame / FPS
        end_time = first_red_start_frame / FPS

        ax5.plot([start_time, end_time], [start_x_deg, first_red_x_deg],
                color='blue', linewidth=3, linestyle='-', alpha=0.8, label='Slow Phase (rightward)')

    # Connections between consecutive fast phases
    for i in range(len(fast_phase_regions) - 1):
        end_frame_1 = fast_phase_regions[i]['end_frame']
        end_x_1_deg = fast_phase_regions[i]['end_x'] * DEG_PER_NORMALIZED
        start_frame_2 = fast_phase_regions[i + 1]['start_frame']
        start_x_2_deg = fast_phase_regions[i + 1]['start_x'] * DEG_PER_NORMALIZED

        end_time_1 = end_frame_1 / FPS
        start_time_2 = start_frame_2 / FPS

        ax5.plot([end_time_1, start_time_2], [end_x_1_deg, start_x_2_deg],
                color='blue', linewidth=3, linestyle='-', alpha=0.8)

# Draw fast phase lines (red lines - leftward jumps)
for i, region in enumerate(fast_phase_regions):
    start_frame = region['start_frame']
    end_frame = region['end_frame']
    start_x_deg = region['start_x'] * DEG_PER_NORMALIZED
    end_x_deg = region['end_x'] * DEG_PER_NORMALIZED

    start_time = start_frame / FPS
    end_time = end_frame / FPS

    ax5.plot([start_time, end_time], [start_x_deg, end_x_deg],
            color='red', linewidth=3, linestyle='-', alpha=0.8,
            label='Fast Phase (leftward)' if i == 0 else '')

# Highlight peak SPV slow phase with a box (only if valid peak found)
if peak_spv_data is not None:
    peak = peak_spv_data
    start_time = peak['start_frame'] / FPS
    end_time = peak['end_frame'] / FPS
    start_x_deg = peak['start_x'] * DEG_PER_NORMALIZED
    end_x_deg = peak['end_x'] * DEG_PER_NORMALIZED

    # Calculate box dimensions
    box_left = start_time
    box_width = end_time - start_time
    box_bottom = min(start_x_deg, end_x_deg)
    box_height = abs(end_x_deg - start_x_deg)

    # Add some padding to the box
    padding_x = box_width * 0.1
    padding_y = box_height * 0.5  # RESTORED from first code

    # Draw rectangle around the peak SPV slow phase
    rect = Rectangle((box_left - padding_x, box_bottom - padding_y),
                     box_width + 2*padding_x,
                     box_height + 2*padding_y,
                     linewidth=3, edgecolor='orange', facecolor='none',
                     linestyle='-', zorder=10, label='Peak SPV')
    ax5.add_patch(rect)

    # Add annotation for peak SPV
    mid_time = (start_time + end_time) / 2
    mid_x_deg = max(start_x_deg, end_x_deg) + padding_y * 0.4  # RESTORED from first code

    ax5.annotate(f'Peak SPV\n{peak["spv"]:.2f} deg/sec',
                xy=(mid_time, mid_x_deg),
                xytext=(10, 20), textcoords='offset points',
                fontsize=11, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', lw=2),
                zorder=11)

# Add average SPV of non-excluded beats to top-left of graph (RESTORED from first code)
valid_spv_values = [s['spv'] for s in spv_data if s['spv'] <= SPV_THRESHOLD]
if len(valid_spv_values) > 0:
    avg_spv = np.mean(valid_spv_values)
    ax5.text(
        0.02, 0.98,
        f'SPV: {avg_spv:.2f} deg/sec',
        transform=ax5.transAxes,
        fontsize=20,
        fontweight='bold',
        va='top',
        ha='left',
        bbox=dict(boxstyle='round,pad=0.6', facecolor='yellow', alpha=0.9, edgecolor='black', linewidth=2)
    )

ax5.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
ax5.set_ylabel('Horizontal Position (degrees)', fontsize=12, fontweight='bold')
ax5.set_title(f'Horizontal Nystagmus', fontsize=14, fontweight='bold')
ax5.grid(True, alpha=0.3)

# Set Y-axis limits
ax5.set_ylim(0, 1 * DEG_PER_NORMALIZED)

ax5.legend(loc='upper right')

plt.tight_layout()
plt.savefig('plot5_spv_analysis.png', dpi=150, bbox_inches='tight')
print(f"\n✓ Plot 5 saved to 'plot5_spv_analysis.png'")
plt.show()

# ================= PRINT ALL SPV VALUES =================
print(f"\n{'='*80}")
print(f"SPV VALUES FOR ALL SLOW PHASES (BEATS)")
print(f"{'='*80}")
print(f"{'Beat':<6} {'Frames':<15} {'Time (sec)':<12} {'Deg Diff':<12} {'SPV (deg/sec)':<15} {'Status':<25}")
print(f"{'-'*95}")

for spv in spv_data:
    is_peak = "★ PEAK" if peak_spv_data and spv['beat'] == peak_spv_data['beat'] else ""

    excluded_reasons = []
    if spv['spv'] > SPV_THRESHOLD:
        excluded_reasons.append("SPV EXCLUDED")
    if spv['time_sec'] < MIN_BEAT_TIME_SEC:
        excluded_reasons.append("TIME EXCLUDED")

    status = is_peak if is_peak else ", ".join(excluded_reasons)

    frame_range = f"{spv['start_frame']}-{spv['end_frame']}"
    print(f"{spv['beat']:<6} {frame_range:<15} {spv['time_sec']:<12.3f} {spv['deg_diff']:<12.2f} {spv['spv']:<15.2f} {status:<25}")

print(f"{'-'*95}")
print(f"\nSummary Statistics:")
if len(spv_data) > 0:
    spv_values = [s['spv'] for s in spv_data]
    valid_spv_values = [
        s['spv'] for s in spv_data
        if s['spv'] <= SPV_THRESHOLD and s['time_sec'] >= MIN_BEAT_TIME_SEC
    ]

    excluded_count = len([
        s for s in spv_data
        if s['spv'] > SPV_THRESHOLD or s['time_sec'] < MIN_BEAT_TIME_SEC
    ])

    print(f"  Total beats analyzed: {len(spv_data)}")
    print(f"  Valid beats (SPV ≤{SPV_THRESHOLD} deg/sec and time ≥{MIN_BEAT_TIME_SEC} sec): {len(valid_spv_values)}")
    print(f"  Excluded beats: {excluded_count}")

    if len(valid_spv_values) > 0:
        print(f"\n  Valid SPV Statistics:")
        print(f"    Mean SPV: {np.mean(valid_spv_values):.2f} deg/sec")
        print(f"    Std Dev: {np.std(valid_spv_values):.2f} deg/sec")
        print(f"    Min SPV: {np.min(valid_spv_values):.2f} deg/sec")
        print(f"    Max SPV: {np.max(valid_spv_values):.2f} deg/sec (Beat {peak_spv_data['beat']})")

    print(f"\n  All SPV Statistics (including excluded):")
    print(f"    Mean: {np.mean(spv_values):.2f} deg/sec")
    print(f"    Max: {np.max(spv_values):.2f} deg/sec")

print(f"{'='*80}")