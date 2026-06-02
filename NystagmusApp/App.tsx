import React, {useEffect, useState, useRef, useCallback} from 'react';
import {StyleSheet, View, Text, Dimensions, TouchableOpacity, Alert, PermissionsAndroid, Platform, Image, Animated} from 'react-native';
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
} from 'react-native-vision-camera';
import Svg, { Circle, Polygon, Path } from 'react-native-svg';
import { CameraRoll } from '@react-native-camera-roll/camera-roll';
import DocumentPicker from 'react-native-document-picker';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');
// Calculate scale and offset to match camera preview with overlay


const BACKEND_URL = 'https://nystagmus-backend-852795190390.us-central1.run.app/process_frame';


function App(): React.JSX.Element {
  
const { hasPermission, requestPermission } = useCameraPermission();
const [cameraPosition, setCameraPosition] = useState<'front' | 'back'>('front');
const device = useCameraDevice(cameraPosition);
const camera = useRef<Camera>(null);
const isCapturing = useRef(false);
const [eyeData, setEyeData] = useState<any>(null);
const [isRecording, setIsRecording] = useState(false);
const [spvGraph, setSpvGraph] = useState<string | null>(null);
const [isAnalyzing, setIsAnalyzing] = useState(false);
const [recordedVideoPath, setRecordedVideoPath] = useState<string | null>(null);
const progressAnim = useRef(new Animated.Value(0)).current;

// Returns: eye distances, centering scores, iris positions
const captureAndSend = useCallback(async () => {
  if (camera.current == null) return;
  if (isCapturing.current) return;
  isCapturing.current = true;
  try {
    const photo = await camera.current.takePhoto({
    flash: 'off',
    enableShutterSound: false,
    } as any);
    const formData = new FormData();
    formData.append('file', {
      uri: `file://${photo.path}`,
      type: 'image/jpeg',
      name: 'frame.jpg',
    } as any);
    const response = await fetch(BACKEND_URL, {
      method: 'POST',
      body: formData,
    });

      const data = await response.json();
      setEyeData(data);

  } catch (error) {
    
  } finally {
    isCapturing.current = false;
  }
}, []);

// Start video recording
const startRecording = useCallback(() => {
  if (camera.current == null) return;
  isCapturing.current = true;
  setIsRecording(true);
  camera.current.startRecording({
    onRecordingFinished: async (video) => {
      try {
        await CameraRoll.saveAsset(`file://${video.path}`, { type: 'video' });
        setRecordedVideoPath(video.path);
      } catch (error) {
        Alert.alert('Error', `Failed to save video: ${JSON.stringify(error)}`);
      }
      isCapturing.current = false;
      setIsRecording(false);
    },
    onRecordingError: (error) => {
      
      isCapturing.current = false;
      setIsRecording(false);
    },
  });
}, []);



// Auto analyze video using Decide_Beat.py
const analyzeVideoAuto = useCallback(async () => {
  if (!recordedVideoPath) {
    Alert.alert('Error', 'No recorded video found. Please record first.');
    return;
  }
  setIsAnalyzing(true);
  setSpvGraph(null);
  progressAnim.setValue(0);
  Animated.timing(progressAnim, {
    toValue: 90,
    duration: 8000,
    useNativeDriver: false,
  }).start();
  try {
    const formData = new FormData();
    formData.append('file', {
      uri: `file://${recordedVideoPath}`,
      type: 'video/mp4',
      name: 'recording.mp4',
    } as any);
    const response = await fetch('https://nystagmus-backend-852795190390.us-central1.run.app/analyze_auto', {
      method: 'POST',
      body: formData,
    });
    const data = await response.json();
    if (data.success) {
      setSpvGraph(data.graph);
    } else {
      Alert.alert('Error', data.error || 'Analysis failed');
    }
  } catch (error) {
    Alert.alert('Error', `Analysis failed: ${error}`);
  } finally {
    setIsAnalyzing(false);
  }
}, [recordedVideoPath]);

// Pick video from gallery for analysis
const pickAndAnalyzeVideo = useCallback(async () => {
  try {
    const result = await DocumentPicker.pickSingle({
      type: DocumentPicker.types.video,
    });
    setRecordedVideoPath(result.uri);
  } catch (error) {
    if (!DocumentPicker.isCancel(error)) {
      Alert.alert('Error', 'Failed to pick video');
    }
  }
}, []);

// Stop video recording
const stopRecording = useCallback(async () => {
  if (camera.current == null) return;
  
  await camera.current.stopRecording();
}, []);


useEffect(() => {
  requestPermission();
}, []);

useEffect(() => {
  if (Platform.OS === 'android') {
    PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.CAMERA,
      {
        title: 'Camera Permission',
        message: 'NystagmusApp needs access to your camera',
        buttonPositive: 'Allow',
        buttonNegative: 'Deny',
      }
    );
  }
}, []);

//Takes a photo every 500ms and sends to backend
useEffect(() => {
  if (spvGraph) return; // Pause when graph is showing
  const interval = setInterval(() => {
    captureAndSend();
  }, 25);
  return () => clearInterval(interval);
}, [captureAndSend, spvGraph]);

//Permission Check
  if (!hasPermission) {
    return (
      <View style={styles.container}>
        <Text style={styles.text}>Requesting camera permission...</Text>
      </View>
    );
  }

  if (device == null) {
    return (
      <View style={styles.container}>
        <Text style={styles.text}>No camera found</Text>
      </View>
    );
  }
  
const frameW = eyeData?.frame_width ?? 2268;
const frameH = eyeData?.frame_height ?? 4032;
const frameAspect = frameW / frameH;
const screenAspect = screenWidth / screenHeight;

let scaleX: number;
let scaleY: number;
let offsetX = 0;
let offsetY = 0;

if (screenAspect > frameAspect) {
  scaleX = screenWidth / frameW;
  scaleY = scaleX;
  offsetY = (screenHeight - frameH * scaleY) / 2;
} else {
  scaleY = screenHeight / frameH;
  scaleX = scaleY;
  offsetX = (screenWidth - frameW * scaleX) / 2;
}


  return (
    <View style={styles.container}>
      <Camera
        ref={camera}
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={true}
        photo={true}
        resizeMode="cover"
        video={true}
        {...(cameraPosition === 'back' && { torch: isRecording ? 'on' : 'off' })}
      />
    {/* Dim overlay when video recorded */}
    {recordedVideoPath && !isRecording && !isAnalyzing && !spvGraph && (
    <View style={styles.dimOverlay} />
    )}

      {/* Vertical crosshair line */}
    <View style={styles.verticalLine} />

      {/* Horizontal crosshair line */}
    <View style={styles.horizontalLine} />

    {/* Camera switch button */}
  <TouchableOpacity 
  style={styles.switchButton}
  onPress={() => setCameraPosition(prev => prev === 'front' ? 'back' : 'front')}
  >
    
  <Svg width="30" height="30" viewBox="0 0 24 24">
    <Path
      d="M20,5h-3.17L15,3H9L7.17,5H4C2.9,5,2,5.9,2,7v12c0,1.1,0.9,2,2,2h16c1.1,0,2-0.9,2-2V7C22,5.9,21.1,5,20,5z M12,18c-2.76,0-5-2.24-5-5H5l2.5-2.5L10,13H8c0,2.21,1.79,4,4,4c0.58,0,1.13-0.13,1.62-0.35l0.74,0.74C13.65,17.76,12.86,18,12,18z M16.5,15.5L14,13h2c0-2.21-1.79-4-4-4c-0.58,0-1.13,0.13-1.62,0.35L9.64,8.62C10.35,8.24,11.14,8,12,8c2.76,0,5,2.24,5,5h2L16.5,15.5z"
      fill="white"
    />
  </Svg>
  </TouchableOpacity>


  {/* Record button */}
  <TouchableOpacity
  style={[styles.recordButton, {backgroundColor: isRecording ? 'red' : 'white'}]}
  onPress={isRecording ? stopRecording : startRecording}
  >
  <View style={[styles.recordInner, {backgroundColor: isRecording ? 'white' : 'red'}]} />
  </TouchableOpacity>

  {/* Upload video button */}
<TouchableOpacity style={styles.uploadButton} onPress={pickAndAnalyzeVideo}>
  <Svg width="54" height="54" viewBox="0 0 512 512">
    <Path fill="#285EFE" d="M256 0c140.799 0 256 115.201 256 256 0 140.803-115.201 256-256 256C115.197 512 0 396.803 0 256S115.197 0 256 0z"/>
    <Path fill="#fff" fillRule="nonzero" d="M198.263 206.44c-4.235-.179-7.245-1.591-8.982-4.231-4.718-7.068 1.722-14.055 6.181-18.971 12.678-13.901 43.72-47.321 49.976-54.682 4.736-5.234 11.487-5.234 16.219 0 6.462 7.548 39.073 42.492 51.118 56.011 4.178 4.707 9.349 11.128 4.995 17.642-1.779 2.64-4.752 4.052-8.99 4.231h-25.722v63.571c0 6.788-5.567 12.363-12.359 12.363h-34.348c-6.791 0-12.359-5.564-12.359-12.363V206.44h-25.729zm-77.738 64.484c-1.415-5.844.969-10.435 4.777-13.156a13.352 13.352 0 014.579-2.078 13.35 13.35 0 015.006-.255c4.639.666 8.866 3.658 10.293 9.521a362.674 362.674 0 012.459 10.899l1.943 9.577c2.539 12.813 4.422 20.851 9.155 24.853 5.002 4.235 14.478 5.699 32.637 5.699h127.541c16.759 0 25.509-1.606 30.106-5.762 4.433-4.006 6.17-11.846 8.42-23.876l.124-.622c1.18-6.35 2.475-13.212 4.302-20.768 1.427-5.859 5.65-8.855 10.293-9.521a13.354 13.354 0 015.005.255c1.629.393 3.205 1.1 4.579 2.078 3.808 2.71 6.193 7.301 4.778 13.152-1.667 6.889-2.947 13.722-4.119 19.998l-.067.363c-3.287 17.578-6.017 29.668-15.062 38.167-8.956 8.416-22.989 11.981-48.359 11.981H191.374c-26.531 0-41.114-3.194-50.493-11.502-9.615-8.518-12.527-20.877-16.238-39.624l-1.969-9.779a334.588 334.588 0 00-2.149-9.6z"/>
  </Svg>
</TouchableOpacity>

  {/* Analyzing overlay - full screen */}
  {isAnalyzing && (
  <View style={styles.analyzingOverlay}>
  
    <View style={styles.analyzingContainer}>
      <Text style={styles.analyzingTitle}>Analyzing video...</Text>
      <View style={styles.progressBarBackground}>
        <Animated.View style={[styles.progressBarFill, {
          width: progressAnim.interpolate({
            inputRange: [0, 90],
            outputRange: ['0%', '90%'],
          })
        }]} />
      </View>
      <Text style={styles.analyzingSubtitle}>Detecting eye movements</Text>
    </View>
  </View>
)}
  {/* Analyze button - show after recording */}
{recordedVideoPath && !isRecording && !isAnalyzing && (
  <View style={styles.analyzeButtonContainer}>
    <TouchableOpacity style={styles.analyzeButton} onPress={analyzeVideoAuto}>
      <Text style={styles.analyzeButtonText}>Analyze</Text>
    </TouchableOpacity>
  </View>
)}
      
    
{/* SPV Graph display */}
{spvGraph && (
  <View style={styles.graphContainer}>
    <TouchableOpacity 
      style={styles.closeButton}
      onPress={() => setSpvGraph(null)}
    >
      <Text style={styles.closeButtonText}>✕</Text>
    </TouchableOpacity>
    <Image
      source={{uri: `data:image/png;base64,${spvGraph}`}}
      style={styles.graphImage}
      resizeMode="contain"
    />
  </View>
)}

    {/* Eye and iris overlays */}
{eyeData && eyeData.face_detected && !spvGraph && !isAnalyzing && !recordedVideoPath && (
  <Svg style={StyleSheet.absoluteFill} pointerEvents="none">
    {/* Left eye polygon */}
    <Polygon
      points={eyeData.left_eye_poly.map((p: number[]) => 
        `${p[0] * scaleX + offsetX},${p[1] * scaleY + offsetY}`
      ).join(' ')}
      fill="none"
      stroke="green"
      strokeWidth="2"
    />
    {/* Right eye polygon */}
    <Polygon
      points={eyeData.right_eye_poly.map((p: number[]) => 
        `${p[0] * scaleX + offsetX},${p[1] * scaleY + offsetY}`
      ).join(' ')}
      fill="none"
      stroke="green"
      strokeWidth="2"
    />
  
    {/* Left iris circle */}
  <Circle
    cx={eyeData.left_iris_center[0] * scaleX + offsetX}
    cy={eyeData.left_iris_center[1] * scaleY + offsetY}
    r={eyeData.left_iris_radius * scaleX}
    fill="none"
    stroke="yellow"
    strokeWidth="2"
  />
    {/* Left iris center dot */}
  <Circle
    cx={eyeData.left_iris_center[0] * scaleX + offsetX}
    cy={eyeData.left_iris_center[1] * scaleY + offsetY}
    r="3"
    fill="red"
  />
    {/* Right iris circle */}
  <Circle
    cx={eyeData.right_iris_center[0] * scaleX + offsetX}
    cy={eyeData.right_iris_center[1] * scaleY + offsetY}
    r={eyeData.right_iris_radius * scaleX}
    fill="none"
    stroke="yellow"
    strokeWidth="2"
  />
    {/* Right iris center dot */}
  <Circle
    cx={eyeData.right_iris_center[0] * scaleX + offsetX}
    cy={eyeData.right_iris_center[1] * scaleY + offsetY}
    r="3"
    fill="red"
  />
  </Svg>
  )}


{/* Eye distance display */}
{eyeData && !spvGraph && !isAnalyzing && !recordedVideoPath && (
  <View style={styles.infoBox}>
    <Text style={[styles.infoText, {color: eyeData.face_detected ? 'green' : 'red', fontWeight: 'bold'}]}>
      {eyeData.face_detected ? 'Face: DETECTED' : 'Face: NOT DETECTED'}
    </Text>
    {eyeData.face_detected && (
      <>
        <Text style={styles.infoText}>
          LEFT eye: {eyeData.left_eye_distance} cm
        </Text>
        <Text style={styles.infoText}>
          RIGHT eye: {eyeData.right_eye_distance} cm
        </Text>
        <Text style={[styles.infoText, {color: eyeData.horiz_pct >= 90 ? 'green' : eyeData.horiz_pct >= 70 ? 'blue' : 'red'}]}>
          H Center: {eyeData.horiz_pct}%
        </Text>
        <Text style={[styles.infoText, {color: eyeData.vert_pct >= 90 ? 'green' : eyeData.vert_pct >= 70 ? 'blue' : 'red'}]}>
          V Center: {eyeData.vert_pct}%
        </Text>
      </>
    )}
  </View>
)}
    </View>
  );
}

const styles = StyleSheet.create({
  
  container: {
    flex: 1,
    backgroundColor: 'black',
  },
  text: {
    color: 'white',
    fontSize: 20,
    textAlign: 'center',
    marginTop: 100,
  },
  verticalLine: {
  position: 'absolute',
  width: 2,
  height: '100%',
  left: '50%',
  backgroundColor: 'rgba(200, 200, 200, 0.8)',
},
horizontalLine: {
  position: 'absolute',
  height: 2,
  width: '100%',
  top: '50%',
  backgroundColor: 'rgba(200, 200, 200, 0.8)',
},
infoBox: {
  position: 'absolute',
  top: 60,
  left: 20,
  backgroundColor: 'rgba(255, 255, 255, 0.85)',
  padding: 10,
  borderRadius: 5,
},
infoText: {
  color: 'black',
  fontSize: 14,
},
switchButton: {
  position: 'absolute',
  bottom: 40,
  left: 30,
  backgroundColor: 'rgba(0, 122, 255, 0.8)',
  padding: 12,
  borderRadius: 12,
},
switchText: {
  color: 'white',
  fontSize: 30,
},

faceStatus: {
  position: 'absolute',
  top: 20,
  alignSelf: 'center',
  backgroundColor: 'rgba(0,0,0,0.6)',
  padding: 8,
  borderRadius: 10,
},
faceStatusText: {
  fontSize: 14,
  fontWeight: 'bold',
},
recordButton: {
  position: 'absolute',
  bottom: 40,
  alignSelf: 'center',
  width: 70,
  height: 70,
  borderRadius: 35,
  backgroundColor: 'white',
  justifyContent: 'center',
  alignItems: 'center',
},
recordInner: {
  width: 50,
  height: 50,
  borderRadius: 25,
  backgroundColor: 'red',
},

analyzingText: {
  color: 'white',
  fontSize: 16,
  fontWeight: 'bold',
  backgroundColor: 'rgba(0,0,0,0.7)',
  padding: 10,
  borderRadius: 8,
},
graphContainer: {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'rgba(0,0,0,0.9)',
  justifyContent: 'center',
  alignItems: 'center',
},
graphImage: {
  width: '100%',
  height: '80%',
},
closeButton: {
  position: 'absolute',
  top: 40,
  right: 20,
  backgroundColor: 'rgba(255,255,255,0.3)',
  width: 40,
  height: 40,
  borderRadius: 20,
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 10,
},
closeButtonText: {
  color: 'white',
  fontSize: 18,
  fontWeight: 'bold',
},
analyzingOverlay: {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'black',
  justifyContent: 'center',
  alignItems: 'center',
},
analyzingContainer: {
  alignItems: 'center',
  gap: 14,
  paddingHorizontal: 40,
  width: '100%',
},
analyzeButtonContainer: {
  position: 'absolute',
  bottom: 130,
  left: 0,
  right: 0,
  alignItems: 'center',
},
analyzeButton: {
  backgroundColor: '#1557c0',
  paddingVertical: 14,
  paddingHorizontal: 40,
  borderRadius: 14,
  alignItems: 'center',
  elevation: 5,
  shadowColor: '#000',
  shadowOffset: {width: 0, height: 2},
  shadowOpacity: 0.3,
  shadowRadius: 4,
  
},
analyzingTitle: {
  color: 'white',
  fontSize: 15,
  fontWeight: '500',
},
analyzingSubtitle: {
  color: 'rgba(255,255,255,0.4)',
  fontSize: 11,
  letterSpacing: 0.5,
},
analyzeButtonText: {
  color: 'white',
  fontSize: 16,
  fontWeight: '700',
  letterSpacing: 0.5,
},
progressBarBackground: {
  width: '100%',
  height: 5,
  backgroundColor: 'rgba(255,255,255,0.1)',
  borderRadius: 99,
  overflow: 'hidden',
},
progressBarFill: {
  height: '100%',
  backgroundColor: '#1a73e8',
  borderRadius: 99,
},
dimOverlay: {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'rgba(14, 13, 13, 0.5)',
},
uploadButton: {
  position: 'absolute',
  bottom: 40,
  right: 30,
},
uploadButtonText: {
  color: 'white',
  fontSize: 30,
},
});

export default App;