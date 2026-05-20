import React, {useEffect, useState, useRef, useCallback} from 'react';
import {StyleSheet, View, Text, Dimensions, TouchableOpacity, Alert, PermissionsAndroid, Platform} from 'react-native';
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
} from 'react-native-vision-camera';
import Svg, { Circle, Polygon, Path } from 'react-native-svg';
import { CameraRoll } from '@react-native-camera-roll/camera-roll';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');
// Calculate scale and offset to match camera preview with overlay


const BACKEND_URL = 'http://10.0.0.36:8000/process_frame';


function App(): React.JSX.Element {
  
const { hasPermission, requestPermission } = useCameraPermission();
const [cameraPosition, setCameraPosition] = useState<'front' | 'back'>('front');
const device = useCameraDevice(cameraPosition);
const camera = useRef<Camera>(null);
const isCapturing = useRef(false);
const [eyeData, setEyeData] = useState(null);
const [isRecording, setIsRecording] = useState(false);

// Returns: eye distances, centering scores, iris positions
const captureAndSend = useCallback(async () => {
  if (camera.current == null) return;
  if (isCapturing.current) return;
  isCapturing.current = true;
  try {
    const photo = await camera.current.takePhoto({
      flash: 'off',
    });
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
      console.log('Frame size:', data.frame_width, data.frame_height);
      console.log('Screen size:', screenWidth, screenHeight);
      setEyeData(data);

  } catch (error) {
    console.log('Capture error:', error);
  } finally {
    isCapturing.current = false;
  }
}, []);

// Start video recording
const startRecording = useCallback(() => {
  if (camera.current == null) return;
  setIsRecording(true);
  camera.current.startRecording({
    onRecordingFinished: async (video) => {
  try {
    console.log('Video path:', video.path);
    await CameraRoll.saveAsset(`file://${video.path}`, { type: 'video' });
    Alert.alert('Video Saved', 'Video has been saved to your camera roll!');
  } catch (error) {
    console.log('Save error details:', JSON.stringify(error));
    Alert.alert('Error', `Failed to save video: ${JSON.stringify(error)}`);
  }
  setIsRecording(false);

    },
    onRecordingError: (error) => {
      console.log('Recording error:', error);
      setIsRecording(false);
    },
  });
}, []);

// Stop video recording
const stopRecording = useCallback(async () => {
  if (camera.current == null) return;
  console.log('Stopping recording...');
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
  const interval = setInterval(() => {
    captureAndSend();
  }, 200);
  return () => clearInterval(interval);
}, [captureAndSend]);

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
      />
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


    {/* Eye and iris overlays */}
{eyeData && eyeData.face_detected && (
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
{/* Face status - always visible */}
{eyeData && (
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
});

export default App;