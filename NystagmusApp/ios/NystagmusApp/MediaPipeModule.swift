import Foundation
import MediaPipeTasksVision

@objc(MediaPipeModule)
class MediaPipeModule: NSObject {
  
  private var faceLandmarker: FaceLandmarker?
  
  @objc func initialize(_ resolve: RCTResponseSenderBlock,
                         rejecter reject: RCTResponseSenderBlock) {
    do {
      let modelPath = Bundle.main.path(forResource: "face_landmarker", ofType: "task")!
      let options = FaceLandmarkerOptions()
      options.baseOptions.modelAssetPath = modelPath
      options.runningMode = .image
      options.numFaces = 1
      options.minFaceDetectionConfidence = 0.2
      options.minFacePresenceConfidence = 0.2
      faceLandmarker = try FaceLandmarker(options: options)
      resolve(["initialized"])
    } catch {
      reject([error.localizedDescription])
    }
  }
  
  @objc func processFrame(_ base64Image: String,
                           resolver resolve: RCTResponseSenderBlock,
                           rejecter reject: RCTResponseSenderBlock) {
    guard let imageData = Data(base64Encoded: base64Image),
          let uiImage = UIImage(data: imageData),
          let mpImage = try? MPImage(uiImage: uiImage) else {
      reject(["Could not decode image"])
      return
    }
    
    guard let result = try? faceLandmarker?.detect(image: mpImage),
          let landmarks = result.faceLandmarks.first else {
      resolve([["face_detected": false]])
      return
    }
    
    let w = Float(uiImage.size.width)
    let h = Float(uiImage.size.height)
    
    let leftIrisIdx = [474, 475, 476, 477]
    let rightIrisIdx = [469, 470, 471, 472]
    let leftEyeIdx = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
    let rightEyeIdx = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]
    
    func px(_ idx: Int) -> (Float, Float) {
      return (landmarks[idx].x * w, landmarks[idx].y * h)
    }
    
    let leftIrisPoints = leftIrisIdx.map { px($0) }
    let leftIrisCX = leftIrisPoints.map { $0.0 }.reduce(0, +) / Float(leftIrisPoints.count)
    let leftIrisCY = leftIrisPoints.map { $0.1 }.reduce(0, +) / Float(leftIrisPoints.count)
    let leftIrisRadius = leftIrisPoints.map {
      sqrt(($0.0 - leftIrisCX) * ($0.0 - leftIrisCX) + ($0.1 - leftIrisCY) * ($0.1 - leftIrisCY))
    }.reduce(0, +) / Float(leftIrisPoints.count)
    
    let rightIrisPoints = rightIrisIdx.map { px($0) }
    let rightIrisCX = rightIrisPoints.map { $0.0 }.reduce(0, +) / Float(rightIrisPoints.count)
    let rightIrisCY = rightIrisPoints.map { $0.1 }.reduce(0, +) / Float(rightIrisPoints.count)
    let rightIrisRadius = rightIrisPoints.map {
      sqrt(($0.0 - rightIrisCX) * ($0.0 - rightIrisCX) + ($0.1 - rightIrisCY) * ($0.1 - rightIrisCY))
    }.reduce(0, +) / Float(rightIrisPoints.count)
    
    let REAL_IRIS_DIAMETER_MM: Float = 11.8
    let FOCAL_LENGTH_PIXELS: Float = 1000.0
    let leftSpan = sqrt(
      (leftIrisPoints[0].0 - leftIrisPoints[2].0) * (leftIrisPoints[0].0 - leftIrisPoints[2].0) +
      (leftIrisPoints[0].1 - leftIrisPoints[2].1) * (leftIrisPoints[0].1 - leftIrisPoints[2].1)
    )
    let leftDistCm = (REAL_IRIS_DIAMETER_MM * FOCAL_LENGTH_PIXELS / max(leftSpan, 1)) / 10.0
    
    let rightSpan = sqrt(
      (rightIrisPoints[0].0 - rightIrisPoints[2].0) * (rightIrisPoints[0].0 - rightIrisPoints[2].0) +
      (rightIrisPoints[0].1 - rightIrisPoints[2].1) * (rightIrisPoints[0].1 - rightIrisPoints[2].1)
    )
    let rightDistCm = (REAL_IRIS_DIAMETER_MM * FOCAL_LENGTH_PIXELS / max(rightSpan, 1)) / 10.0
    
    let leftEyePoints = leftEyeIdx.map { px($0) }
    let rightEyePoints = rightEyeIdx.map { px($0) }
    
    let centerX = w / 2.0
    let centerY = h / 2.0
    let leftEyeHorizCenter = (leftEyePoints.map { $0.0 }.min()! + leftEyePoints.map { $0.0 }.max()!) / 2.0
    let rightEyeHorizCenter = (rightEyePoints.map { $0.0 }.min()! + rightEyePoints.map { $0.0 }.max()!) / 2.0
    let residualDx = (leftEyeHorizCenter - centerX) + (rightEyeHorizCenter - centerX)
    let horizPct = max(0, 100.0 * (1.0 - abs(residualDx) / (w / 2.0)))
    let dyL = leftIrisCY - centerY
    let dyR = rightIrisCY - centerY
    let vertDev = (abs(dyL) + abs(dyR)) / 2.0
    let vertPct = max(0, 100.0 * (1.0 - vertDev / (h / 2.0)))
    
    let map: [String: Any] = [
      "face_detected": true,
      "frame_width": Int(w),
      "frame_height": Int(h),
      "left_eye_distance": round(Double(leftDistCm) * 100) / 100,
      "right_eye_distance": round(Double(rightDistCm) * 100) / 100,
      "horiz_pct": round(Double(horizPct) * 10) / 10,
      "vert_pct": round(Double(vertPct) * 10) / 10,
      "left_iris_center": [leftIrisCX, leftIrisCY],
      "left_iris_radius": leftIrisRadius,
      "right_iris_center": [rightIrisCX, rightIrisCY],
      "right_iris_radius": rightIrisRadius,
      "left_eye_poly": leftEyePoints.map { [$0.0, $0.1] },
      "right_eye_poly": rightEyePoints.map { [$0.0, $0.1] },
    ]
    
    resolve([map])
  }
  
  @objc static func requiresMainQueueSetup() -> Bool {
    return false
  }
}