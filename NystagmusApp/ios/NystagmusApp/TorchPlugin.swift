import AVFoundation
import Foundation

@objc(TorchPlugin)
class TorchPlugin: NSObject {
  
  @objc func setTorchLevel(_ level: Float) {
    guard let device = AVCaptureDevice.default(for: .video),
          device.hasTorch else { return }
    do {
      try device.lockForConfiguration()
      if level <= 0 {
        device.torchMode = .off
      } else {
        try device.setTorchModeOn(level: min(max(level, 0.01), 1.0))
      }
      device.unlockForConfiguration()
    } catch {
      print("Torch error: \(error)")
    }
  }
  
  @objc static func requiresMainQueueSetup() -> Bool {
    return false
  }
}