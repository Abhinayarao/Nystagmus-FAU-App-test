# AI Input/Output Flow

The diagram maps the current AI input/output flow of the app.

### Explanation:

* **Client Layer (top)**: iOS users access the app via TestFlight and Android users via APK. Both are built with React Native.
* **Backend (middle)**: Both clients connect to a REST API hosted on Google Cloud Run.
* **Processing Services**: The backend has three main services:
  * **Frame Processor** - handles live camera frames, runs real-time eye detection and returns overlay coordinates back to the app.
  * **SPV Engine** - receives the recorded video, runs `Decide_Beat.py` to auto-detect direction, then runs Left or Right Beat script and returns the SPV graph as an image.
  * **Upload Handler** - generates a secure signed URL for the app to upload videos directly to Google Cloud Storage.
* **Storage Layer (bottom)**: Three storage types:
  * **Local Storage** - SPV graph history stored on device
  * **Cloud Storage** - patient recordings stored permanently in `nystagmus-videos-fau` bucket on Google Cloud
  * **Temporary Storage** - files used during analysis in `/tmp`, cleared after use
* **Supporting Services**: App Distribution (TestFlight and APK), Monitoring via GCP Console, and Access Control via IAM.
