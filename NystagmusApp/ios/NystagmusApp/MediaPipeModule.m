#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE(MediaPipeModule, NSObject)

RCT_EXTERN_METHOD(initialize:(RCTResponseSenderBlock)resolve
                  rejecter:(RCTResponseSenderBlock)reject)

RCT_EXTERN_METHOD(processFrame:(NSString *)base64Image
                  resolver:(RCTResponseSenderBlock)resolve
                  rejecter:(RCTResponseSenderBlock)reject)

@end