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
