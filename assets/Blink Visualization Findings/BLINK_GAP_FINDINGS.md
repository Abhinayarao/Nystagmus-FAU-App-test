# Blink Gap Visualization : Complete Findings

## What was implemented
When a blink is detected (bilateral EAR below threshold), the corresponding frames are removed. In the SPV graph, instead of connecting across the missing frames, the graph now shows an empty space.

---

## Two approaches were tested

### Approach 1 : Skip entire slow phase connection (original)
When a blink is detected anywhere between two fast phases, the entire slow phase line connecting them is removed. The gap size depends on how long the slow phase was, not how long the blink lasted. In code, this was implemented by checking if any frame gap exists between two fast phases and skipping the call entirely if a blink is found.

### Approach 2 : Split at blink point (refined)
The line stops exactly where the blink starts, leaves a small empty space for the blink duration, then continues after. The gap size matches the actual blink duration. In code, this was implemented by finding the exact frame where the gap occurs, interpolating the degree value at that point, and drawing two separate line segments — one before and one after the blink.

---

## 6 Scenarios tested (EAR 0.22 and 0.25 × Gap threshold 1, 3, 5)

| Scenario | EAR Threshold | Gap Threshold | Result |
|----------|--------------|---------------|--------|
| 1 | 0.22 | 1 | Gaps visible |
| 2 | 0.22 | 3 | Same gaps as Scenario 1 |
| 3 | 0.22 | 5 | No gaps |
| 4 | 0.25 | 1 | Gaps visible |
| 5 | 0.25 | 3 | Gaps visible |
| 6 | 0.25 | 5 | Gaps visible |

---

## Key Finding
The EAR threshold has a bigger impact on gap visibility than the gap threshold. EAR 0.25 consistently produced gaps across all three thresholds, while EAR 0.22 only showed gaps at thresholds 1 and 3.

---

## Note on EAR values in dataset
The minimum EAR observed across tested videos was **0.294**. EAR 0.25 detected more blinks because it is closer to the observed minimum EAR of 0.294, making it more sensitive to the slight eye closures present in the dataset videos.

---

## Results
Both sets of results (Approach 1 and Approach 2) for all 6 scenarios are attached in `assets/Blink Visualization/`.

