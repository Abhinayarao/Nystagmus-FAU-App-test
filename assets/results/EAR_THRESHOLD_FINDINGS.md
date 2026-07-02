# EAR Threshold Comparison: Technical Findings

## Objective
Compare the effect of two EAR (Eye Aspect Ratio) blink detection thresholds (0.22 vs 0.25) on SPV (Slow Phase Velocity) output across 8 dataset videos.

---

## Results

| Video | SPV at 0.22 (deg/sec) | SPV at 0.25 (deg/sec) | Difference |
|-------|----------------------|----------------------|------------|
| IMG_2856.MOV | — | — | Errored (no fast phases detected) |
| IMG_2858.MOV | 9.74 | 9.69 | -0.05 |
| IMG_2861.MOV | identical | identical | No change |
| IMG_2864.MOV | identical | identical | No change |
| IMG_2992.MOV | identical | identical | No change |
| IMG_2993.MOV | identical | identical | No change |
| IMG_2995.MOV | identical | identical | No change |
| IMG_3299.MOV | identical | identical | No change |

---

## Findings
- The difference between EAR threshold 0.22 and 0.25 was minimal across all tested videos
- Only one video (IMG_2858.MOV) showed a slight SPV change of 0.05 deg/sec
- All other videos produced identical SPV values regardless of threshold


