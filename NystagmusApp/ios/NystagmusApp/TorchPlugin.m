#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE(TorchPlugin, NSObject)
RCT_EXTERN_METHOD(setTorchLevel:(float)level)
@end