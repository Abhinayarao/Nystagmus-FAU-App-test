# Development Log

---

## Issue 1 - Set up React Native Project
**Date:** May 13, 2026

**Status:** ✅ Closed

**What I did:**
- Cloned the GitHub repository
- Set up React Native project using @react-native-community/cli
- Confirmed app runs on iOS simulator

**What failed:**
- CocoaPods installation failed due to outdated Ruby version (2.6)
- Homebrew permission issues required manual ownership fixes

**What I did to fix it:**
- Installed CocoaPods via Homebrew instead of gem
- Fixed Homebrew permissions using sudo chown commands

**Result:** ✅ React Native app running on iOS simulator

---

## Issue 2 - Live Camera Feed
**Date:** May 15, 2026

**Status:** ✅ Closed

**What I did:**
- Installed Vision Camera library
- Added live front camera feed to the app
- Tested on iPhone physical device

**What failed:**
- Camera.requestCameraPermission() does not exist as static method
- device variable was undefined because useCameraDevice was placed incorrectly

**What I did to fix it:**
- Switched to useCameraPermission hook
- Moved useCameraDevice right after permission hook

**Result:** ✅ Live front camera working on iPhone

---

## Issue 3 - Add Crosshair Overlay
**Date:** May 15, 2026

**Status:** ✅ Closed

**What I did:**
- Added two gray lines on top of camera feed
- Vertical line at 50% of screen width
- Horizontal line at 50% of screen height

**Result:** ✅ Gray crosshair lines dividing screen into 4 equal parts

## Issue 4 - Eye distance calculation

### Implement real-time eye distance Using Fast API

**The real-time eye distance was calculated Using Fast API**

MediaPipe does not have a stable mobile SDK for React Native. so Two options were considered:
**Option 1 - On-device processing**

- Run MediaPipe directly on iPhone
- Complex native setup
- Limited React Native support


Option 2 - FastAPI Python backend

- MediaPipe already written and tested in Python
- No rewriting needed
- Easier to debug and validate against results
- Backend can be deployed to cloud (AWS) later

Decision: Started with FastAPI backend approach to get it working first. On-device processing can be explored later for offline/telemedicine use where internet may not be available.

**Vision Camera Version Journey:**

**Started with Vision Camera v5 (latest)**
- Installed v5 thinking latest = best
- v5 completely redesigned the frame processor API
- useFrameProcessor hook was removed
- Replaced with a new system called useFrameOutput which is more complex and poorly documented
- Most tutorials and examples online are written for v4 (we can explore Vision Camera v5’s new useFrameOutput API once the documentation improves)
```tsx
// Vision Camera v5 frame processor attempt
const frameProcessor = useFrameProcessor((frame) => {
  'worklet';
  runOnJS(sendFrameToBackend)(frame.toString());
}, [sendFrameToBackend]);
```
**Downgraded to Vision Camera v4**

- v4 has useFrameProcessor which is well documented
- Tried two approaches to send frames to backend from frame processor
- Both failed due to plugin compatibility issues
- Frame processor worklet thread cannot directly call fetch to backend
```tsx
// vision-camera-base64 attempt
import { toBase64 } from 'vision-camera-base64';
const frameProcessor = useFrameProcessor((frame) => {
  'worklet';
  const base64 = toBase64(frame);
  runOnJS(sendFrameToBackend)(base64);
}, [sendFrameToBackend]);
```
**What worked: takePhoto() every 200ms**

## Issue 6 - Real Time Tracking, Overlay Scaling
**Date:** May 18, 2026

**Status:** ✅ Closed

### 1. Real Time Tracking Interval
**What I did:**
Tested capture intervals from 200ms down to 25ms.

**Result:** 25ms works stably without errors. The `isCapturing` flag prevents overlapping captures.

**Key finding:**
MediaPipe backend processing time is only ~10ms. The real bottleneck is network round trip (~300-400ms). Going below 25ms doesn't improve perceived speed since the `isCapturing` flag skips frames when backend is busy.
(See screenshot in Issue 6 for backend timing results)

**Conclusion:** On-device MediaPipe would eliminate network bottleneck entirely and give true 30fps tracking.

---

### 2. Eye Overlay Size Mismatch (iOS & Android)
**Problem:**
Eye overlays appeared smaller and misaligned compared to actual eye position.

**Root Cause:**
Resolution mismatch between camera frame and screen:

| Platform  | Frame Size | Screen Size|
|-----------|------------|------------|
| iOS       | 2268 × 4032| 430 × 932  |
| Android   | 1728 × 2304| 360 × 720  |

**What failed:**
- Hardcoded iOS frame dimensions — broke on Android
- Simple width/height ratio scaling — ignored aspect ratio mismatch

**What worked:**
Dynamic scaling using frame dimensions returned by backend. Calculated scale and offset based on actual frame vs screen aspect ratio using "cover" mode logic.

**Result:** ✅ Eye overlays correctly aligned on both iOS and Android

---

### 4. Android Support
**What I did:**

- Added camera permissions to AndroidManifest.xml
- Added runtime permission request for Android
- Fixed backend URL for Android device
- Tested on Realme 7 physical device

**Result:** ✅ App running on Android with eye tracking working

---

### 5. Frame Resize Optimization
**What I did:**
Resized frame to 640×480 before MediaPipe processing on backend.

**Result:**
- MediaPipe processing: ~10ms ✅
- No improvement in perceived speed — bottleneck is network not processing

---

### 6. Video Recording
**What I did:**
- Added record button using Vision Camera's startRecording()
- Raw camera feed saved to camera roll — no overlays in recorded video
- SVG overlays are React Native UI elements — don't appear in native video recording
- Added camera flip button
- Fixed conflict between takePhoto() and startRecording()

**Result:** ✅ Clean video recording without overlays on both iOS and Android

## Issue 7 - Beat Analysis Feature
**Date:** May 27, 2026
**Status:** ✅ Complete

**What I did:**
- After recording stops, 4 buttons appear: Left Beat, Right Beat, Up Beat, Down Beat
- Tapping a button sends the recorded video to backend
- Backend runs the corresponding Python script and replaces hardcoded `video_path` with actual recorded video path
- Added `matplotlib.use('Agg')` to disable interactive display — was causing script timeouts
- SPV graph returned as base64 PNG and displayed full screen in app
- Eye overlays and camera capture pause during analysis and graph display
- Close button (✕) to return to camera view after viewing graph

## Issue 8 - Flashlight & Auto Beat Detection
**Date:** May 29, 2026
**Status:** ✅ Complete

- Back camera torch turns on automatically when recording starts and off when stopped
- Front camera has no hardware torch (hardware limitation): white overlay was considered as an alternative but decided against - no implementation for now
- Integrated `Decide_Beat.py` : runs first to detect dominant eye movement direction
- Based on `classification['direction']` output (`'rightward'` or `'leftward'`), automatically runs `Right_Beat.py` or `Left_Beat.py`
- Up and Down beat execution commented out as instructed - app only detects left and right beats
- Replaced 4 beat buttons with single **Analyze** button
- After recording, camera feed dims and eye overlays/numbers stop - focus on Analyze button
- Weak/mixed classification handled — uses best guess based on count when direction is uncertain

**Backend Deployment - Google Cloud Run**

- Deployed FastAPI backend to Google Cloud Run
- App now works from anywhere and no longer requires Mac to be running or same WiFi
- Tested and working on both iOS and Android
- Free tier used - no cost for current usage level

**App Distribution**
- Deployed backend to **Google Cloud Run** 
- App now works from anywhere with internet — no Mac or WiFi dependency

**Android:**
- Built release APK, any teammate with an Android phone can install it directly

**iOS:**
- App uploaded to TestFlight and ready to distribute

