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


