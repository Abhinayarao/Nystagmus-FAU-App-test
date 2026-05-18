import React, {useEffect, useState, useRef, useCallback} from 'react';
import {StyleSheet, View, Text, Dimensions} from 'react-native';
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
} from 'react-native-vision-camera';
import Svg, { Circle, Polygon } from 'react-native-svg';
const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

const BACKEND_URL = 'http://10.0.0.36:8000/process_frame';


function App(): React.JSX.Element {
  
const { hasPermission, requestPermission } = useCameraPermission();
const device = useCameraDevice('front');
const camera = useRef<Camera>(null);
const isCapturing = useRef(false);
const [eyeData, setEyeData] = useState(null);

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
    setEyeData(data);
  } catch (error) {
    console.log('Capture error:', error);
  } finally {
    isCapturing.current = false;
  }
}, []);

useEffect(() => {
  requestPermission();
}, []);

//Takes a photo every 500ms and sends to backend
useEffect(() => {
  const interval = setInterval(() => {
    captureAndSend();
  }, 500);
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
  
  return (
    <View style={styles.container}>
      <Camera
        ref={camera}
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={true}
        photo={true}
      />
      {/* Vertical crosshair line */}
    <View style={styles.verticalLine} />

      {/* Horizontal crosshair line */}
    <View style={styles.horizontalLine} />

    {/* Eye and iris overlays */}
{eyeData && eyeData.face_detected && (
  <Svg style={StyleSheet.absoluteFill}>
    {/* Left eye polygon */}
    <Polygon
      points={eyeData.left_eye_poly.map((p: number[]) => 
        `${(p[0] / eyeData.frame_width) * screenWidth},${(p[1] / eyeData.frame_height) * screenHeight}`
      ).join(' ')}
      fill="none"
      stroke="green"
      strokeWidth="2"
    />
    {/* Right eye polygon */}
    <Polygon
      points={eyeData.right_eye_poly.map((p: number[]) => 
        `${(p[0] / eyeData.frame_width) * screenWidth},${(p[1] / eyeData.frame_height) * screenHeight}`
      ).join(' ')}
      fill="none"
      stroke="green"
      strokeWidth="2"
    />
    {/* Left iris circle */}
    <Circle
      cx={(eyeData.left_iris_center[0] / eyeData.frame_width) * screenWidth}
      cy={(eyeData.left_iris_center[1] / eyeData.frame_height) * screenHeight}
      r={(eyeData.left_iris_radius / eyeData.frame_width) * screenWidth}
      fill="none"
      stroke="yellow"
      strokeWidth="2"
    />
    {/* Left iris center dot */}
    <Circle
      cx={(eyeData.left_iris_center[0] / eyeData.frame_width) * screenWidth}
      cy={(eyeData.left_iris_center[1] / eyeData.frame_height) * screenHeight}
      r="3"
      fill="red"
    />
    {/* Right iris circle */}
    <Circle
      cx={(eyeData.right_iris_center[0] / eyeData.frame_width) * screenWidth}
      cy={(eyeData.right_iris_center[1] / eyeData.frame_height) * screenHeight}
      r={(eyeData.right_iris_radius / eyeData.frame_width) * screenWidth}
      fill="none"
      stroke="yellow"
      strokeWidth="2"
    />
    {/* Right iris center dot */}
    <Circle
      cx={(eyeData.right_iris_center[0] / eyeData.frame_width) * screenWidth}
      cy={(eyeData.right_iris_center[1] / eyeData.frame_height) * screenHeight}
      r="3"
      fill="red"
    />
  </Svg>
)}

    {/* Eye distance display */}
{eyeData && eyeData.face_detected && (
  <View style={styles.infoBox}>
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
});

export default App;