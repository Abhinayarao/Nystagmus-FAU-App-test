import React, {useEffect, useState, useRef, useCallback} from 'react';
import {StyleSheet, View, Text, Dimensions, TouchableOpacity, Alert, PermissionsAndroid, Platform, Image, Animated, PanResponder, useWindowDimensions, ScrollView, RefreshControl} from 'react-native';
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
} from 'react-native-vision-camera';
import Svg, { Circle, Polygon, Path } from 'react-native-svg';
import { CameraRoll } from '@react-native-camera-roll/camera-roll';
import DocumentPicker from 'react-native-document-picker';
import AsyncStorage from '@react-native-async-storage/async-storage';
import RNFS from 'react-native-fs';
import { NativeModules } from 'react-native';
import Slider from '@react-native-community/slider';
const { TorchPlugin } = NativeModules;
import ReactNativeBlobUtil from 'react-native-blob-util';


const BACKEND_URL = 'https://nystagmus-backend-852795190390.us-central1.run.app/process_frame';

const ONBOARDING_STEPS = [
  {
    icon: 'camera',
    title: 'Position the camera',
    description: 'Hold the phone 10–12cm from the face. Both eyes should be clearly visible in the frame.',
  },
  {
    icon: 'record',
    title: 'Record eye movement',
    description: 'Press record and capture the eye movement for 10–15 seconds.',
  },
  {
    icon: 'analyze',
    title: 'Analyze and save',
    description: 'Tap Analyze to detect Nystagmus.',
  },
];

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
const skeletonAnim = useRef(new Animated.Value(0)).current;
const [showHistory, setShowHistory] = useState(false);
const [historyItems, setHistoryItems] = useState<any[]>([]);
const [historyLoading, setHistoryLoading] = useState(false);
const [showOnboarding, setShowOnboarding] = useState(false);
const [onboardingStep, setOnboardingStep] = useState(0);
const [selectedHistoryItem, setSelectedHistoryItem] = useState<any>(null);
const [selectedForDelete, setSelectedForDelete] = useState<string[]>([]);
const [isSelecting, setIsSelecting] = useState(false);
const drawerAnim = useRef(new Animated.Value(0)).current;
const showHistoryRef = useRef(false);
const pullDownAnim = useRef(new Animated.Value(0)).current;
const [isPulling, setIsPulling] = useState(false);
const [isRefreshing, setIsRefreshing] = useState(false);
const [isUploading, setIsUploading] = useState(false);
const [isSilentUploading, setIsSilentUploading] = useState(false);
const [uploadedPath, setUploadedPath] = useState<string | null>(null);
const [torchLevel, setTorchLevel] = useState(1.0);
const torchLevelRef = useRef(1.0);
const TORCH_LEVELS = [0.25, 0.5, 0.75, 1.0];
const { width: screenWidth, height: screenHeight } = useWindowDimensions();

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
    uploadRecordingToCloud(video.path, true);
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

// Delete selected items from history
const deleteSelectedFromHistory = useCallback(async () => {
  try {
    const existing = await AsyncStorage.getItem('spv_history');
    const history = existing ? JSON.parse(existing) : [];
    const updated = history.filter((item: any) => !selectedForDelete.includes(item.id));
    await AsyncStorage.setItem('spv_history', JSON.stringify(updated));
    setHistoryItems(updated);
    setSelectedForDelete([]);
    setIsSelecting(false);
  } catch (error) {
    console.error('Failed to delete from history:', error);
  }
}, [selectedForDelete]);
// Save graph to history
// Delete item from history
const deleteFromHistory = useCallback(async (id: string) => {
  try {
    const existing = await AsyncStorage.getItem('spv_history');
    const history = existing ? JSON.parse(existing) : [];
    const updated = history.filter((item: any) => item.id !== id);
    await AsyncStorage.setItem('spv_history', JSON.stringify(updated));
    setHistoryItems(updated);
    setSpvGraph(null);
    setSelectedHistoryItem(null);
    showHistoryRef.current = true;
    setShowHistory(true);
    setHistoryLoading(true);
    setTimeout(() => {
    loadHistory();
  }, 100);
    Animated.spring(drawerAnim, {
  toValue: 400,
  useNativeDriver: false,
}).start();
  } catch (error) {
    console.error('Failed to delete from history:', error);
  }
}, []);
const saveToHistory = useCallback(async (graph: string, direction: string) => {
  try {
    const existing = await AsyncStorage.getItem('spv_history');
    const history = existing ? JSON.parse(existing) : [];
    const newItem = {
      id: Date.now().toString(),
      graph,
      direction,
      date: new Date().toLocaleString(),
    };
    history.unshift(newItem);
    await AsyncStorage.setItem('spv_history', JSON.stringify(history));
    setHistoryItems(history);
  } catch (error) {
    console.error('Failed to save to history:', error);
  }
}, []);

// Auto analyze video using Decide_Beat.py
const analyzeVideoAuto = useCallback(async () => {
  if (!recordedVideoPath) {
    Alert.alert('Error', 'No recorded video found. Please record first.');
    return;
  }
  const savedVideoPath = recordedVideoPath;
  setIsAnalyzing(true);
  setSpvGraph(null);
  progressAnim.setValue(0);
  Animated.timing(progressAnim, {
    toValue: 90,
    duration: 15000,
    useNativeDriver: false,
  }).start();
  
  try {
    const uri = recordedVideoPath.startsWith('file://') ? recordedVideoPath : `file://${recordedVideoPath}`;
    const isMov = uri.toLowerCase().includes('.mov');
    const filename = isMov ? `video_${Date.now()}.mov` : `video_${Date.now()}.mp4`;
    const contentType = isMov ? 'video/quicktime' : 'video/mp4';

    const urlResponse = await fetch(`https://nystagmus-backend-852795190390.us-central1.run.app/get_upload_url?filename=${filename}`);
    const urlData = await urlResponse.json();
    if (!urlResponse.ok || urlData.error) {
      Alert.alert('Error', `Failed to get upload URL: ${urlData.error || urlResponse.status}`);
      return;
    }

    const videoBlob = await fetch(uri).then(r => r.blob());
    await fetch(urlData.url, {
      method: 'PUT',
      headers: { 'Content-Type': contentType },
      body: videoBlob,
    });

    const analyzeResponse = await fetch(
      `https://nystagmus-backend-852795190390.us-central1.run.app/analyze_from_gcs?gcs_path=${filename}`,
      { method: 'POST' }
    );
    const text = await analyzeResponse.text();
    if (!analyzeResponse.ok || text.startsWith('<')) {
      Alert.alert('Backend Error', `Status: ${analyzeResponse.status}\n${text.substring(0, 200)}`);
      return;
    }
    const data = JSON.parse(text);
    if (data.success) {
  setSpvGraph(data.graph);
  const currentVideoPath = savedVideoPath;
  setTimeout(() => {
    Alert.alert(
      'Analysis Complete',
      'Would you like to save this analysis?',
      [
        {
          text: 'Discard',
          style: 'destructive',
        },
{
  text: 'Save Only',
  onPress: () => {
    saveToHistory(data.graph, data.direction || 'unknown');
    Alert.alert('Analysis saved to your history ✓');
  },
},
        {
  text: 'Save',
  onPress: () => {
    saveToHistory(data.graph, data.direction || 'unknown');
  },
},
      ]
    );
  }, 500);
}else {
      Alert.alert('Error', data.error || 'Analysis failed');
    }

  } finally {
    setIsAnalyzing(false);
    setRecordedVideoPath(null);
    isCapturing.current = false;
  }
  }, [recordedVideoPath]);

// Pick video from gallery for analysis
const pickAndAnalyzeVideo = useCallback(async () => {
  try {
    const result = await DocumentPicker.pickSingle({
      type: DocumentPicker.types.video,
    });
    isCapturing.current = true;
    // Copy immediately to stable location
    const isMov = result.uri.toLowerCase().includes('.mov');
    const destPath = `${RNFS.TemporaryDirectoryPath}picked_${Date.now()}.${isMov ? 'mov' : 'mp4'}`;
    const sourcePath = result.uri.replace('file://', '');
    await RNFS.copyFile(sourcePath, destPath);
    setRecordedVideoPath(`file://${destPath}`);
  } catch (error) {
    if (!DocumentPicker.isCancel(error)) {
      Alert.alert('Error', 'Failed to pick video');
    }
  }
}, []);

// Upload recording to GCS for research monitoring
const uploadRecordingToCloud = useCallback(async (videoPath: string, silent: boolean = false) => {
  try {
    if (silent) {
      setIsSilentUploading(true);
    } else {
      setIsUploading(true);
      progressAnim.setValue(0);
      Animated.timing(progressAnim, {
        toValue: 90,
        duration: 10000,
        useNativeDriver: false,
      }).start();
    }
    const isMov = videoPath.toLowerCase().includes('.mov');
    const timestamp = Date.now();
    const filename = `recordings/${timestamp}_${isMov ? 'recording.mov' : 'recording.mp4'}`;
    const contentType = isMov ? 'video/quicktime' : 'video/mp4';

    // Get signed upload URL
    const urlResponse = await fetch(`https://nystagmus-backend-852795190390.us-central1.run.app/get_upload_url?filename=${filename}&content_type=${encodeURIComponent(contentType)}`);
    const urlData = await urlResponse.json();
    if (!urlResponse.ok || urlData.error) {
      Alert.alert('Upload Failed', 'Could not get upload URL.');
      return;
    }

    // Copy file to temp location handling both ph:// and file:// URIs
    const destPath = `${RNFS.TemporaryDirectoryPath}upload_${timestamp}.mov`;
    const sourcePath = videoPath.startsWith('file://') ? videoPath.replace('file://', '') : videoPath;
    
    // Upload to GCS
    const uploadResult = await ReactNativeBlobUtil.fetch('PUT', urlData.url, {
      'Content-Type': contentType,
    }, ReactNativeBlobUtil.wrap(destPath));

    if (uploadResult.respInfo.status === 200) {
      setUploadedPath(filename);
      if (!silent) {
        Animated.timing(progressAnim, {
          toValue: 100,
          duration: 300,
          useNativeDriver: false,
        }).start();
        Alert.alert('Uploaded', 'Recording uploaded successfully for research monitoring.');
      }
    } else {
      if (!silent) {
        Alert.alert('Upload Failed', 'Could not upload to cloud.');
      }
    }
    // Clean up temp file
    await RNFS.unlink(destPath).catch(() => {});
  } catch (error) {
    if (!silent) {
      Alert.alert('Upload Failed', `Error: ${error}`);
    }
  } finally {
    if (silent) {
      setIsSilentUploading(false);
    } else {
      setIsUploading(false);
    }
  }
}, []);
const onRefresh = useCallback(() => {
  setIsRefreshing(true);
  setEyeData(null);
  setSpvGraph(null);
  setRecordedVideoPath(null);
  setIsAnalyzing(false);
  isCapturing.current = false;
  setTimeout(() => setIsRefreshing(false), 800);
}, []);
// Pull to refresh gesture handler
const pullResponder = useRef(PanResponder.create({
  onStartShouldSetPanResponder: () => true,
  onMoveShouldSetPanResponder: (_, gestureState) => gestureState.dy > 2 && gestureState.vy > 0,
  onPanResponderMove: (_, gestureState) => {
    if (gestureState.dy > 0) {
      pullDownAnim.setValue(Math.min(gestureState.dy, 80));
      setIsPulling(true);
    }
  },
  onPanResponderRelease: (_, gestureState) => {
    if (gestureState.dy > 60) {
      setEyeData(null);
      setSpvGraph(null);
      setRecordedVideoPath(null);
      setIsAnalyzing(false);
      isCapturing.current = false;
    }
    Animated.spring(pullDownAnim, {
      toValue: 0,
      useNativeDriver: false,
    }).start();
    setIsPulling(false);
  },
})).current;

// Drawer gesture handler
const panResponder = useRef(PanResponder.create({
  onStartShouldSetPanResponder: () => true,
  onMoveShouldSetPanResponder: (_, gestureState) => Math.abs(gestureState.dy) > 5,
  onPanResponderMove: (_, gestureState) => {
    if (gestureState.dy < 0) {
      drawerAnim.setValue(Math.min(Math.abs(gestureState.dy), 400));
    }
  },
  onPanResponderRelease: (_, gestureState) => {
    if (gestureState.dy < -80) {
      Animated.spring(drawerAnim, {
        toValue: 400,
        useNativeDriver: false,
      }).start();
      showHistoryRef.current = true;
      setShowHistory(true);
      setHistoryLoading(true);
      setTimeout(() => loadHistory(), 100);
    } else if (gestureState.dy > 80 && showHistoryRef.current) {
      Animated.spring(drawerAnim, {
        toValue: 0,
        useNativeDriver: false,
      }).start();
      showHistoryRef.current = false;
      setShowHistory(false);
    } else {
      Animated.spring(drawerAnim, {
        toValue: showHistoryRef.current ? 400 : 0,
        useNativeDriver: false,
      }).start();
    }
  },
})).current;


// Load history on app start
const loadHistory = useCallback(async () => {
  try {
    setHistoryLoading(true);
    const [existing] = await Promise.all([
      AsyncStorage.getItem('spv_history'),
      new Promise<void>(resolve => setTimeout(resolve, 800)),
    ]);
    if (existing) {
      setHistoryItems(JSON.parse(existing));
    }
  } catch (error) {
    console.error('Failed to load history:', error);
  } finally {
    setHistoryLoading(false);
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
  AsyncStorage.getItem('onboarding_complete').then((val) => {
    if (!val) setShowOnboarding(true);
  });
}, []);

useEffect(() => {
  loadHistory();
}, []);

useEffect(() => {
  Animated.loop(
    Animated.sequence([
      Animated.timing(skeletonAnim, {
        toValue: 1,
        duration: 700,
        useNativeDriver: true,
      }),
      Animated.timing(skeletonAnim, {
        toValue: 0,
        duration: 700,
        useNativeDriver: true,
      }),
    ])
  ).start();
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
  if (spvGraph) return;
  if (isAnalyzing) return;
  if (showHistory) return;
  const interval = setInterval(() => {
    captureAndSend();
  }, 25);
  return () => clearInterval(interval);
}, [captureAndSend, spvGraph, isAnalyzing, showHistory]);

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

    {/* Onboarding overlay */}
{showOnboarding && (
  <View style={styles.onboardingOverlay}>
    <View style={styles.onboardingCard}>
      <View style={styles.onboardingIconContainer}>
        {onboardingStep === 0 && (
          <Svg width="32" height="32" viewBox="0 0 24 24">
            <Path d="M3 9a2 2 0 0 1 2-2h.93a2 2 0 0 0 1.664-.89l.812-1.22A2 2 0 0 1 10.07 4h3.86a2 2 0 0 1 1.664.89l.812 1.22A2 2 0 0 0 18.07 7H19a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke="rgba(0,122,255,0.9)" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
            <Circle cx="12" cy="13" r="3" stroke="rgba(0,122,255,0.9)" strokeWidth="1.5" fill="none"/>
          </Svg>
        )}
        {onboardingStep === 1 && (
          <Svg width="32" height="32" viewBox="0 0 24 24">
            <Circle cx="12" cy="12" r="8" stroke="rgba(255,80,80,0.9)" strokeWidth="1.5" fill="none"/>
            <Circle cx="12" cy="12" r="3" fill="rgba(255,80,80,0.9)"/>
          </Svg>
        )}
        {onboardingStep === 2 && (
          <Svg width="32" height="32" viewBox="0 0 24 24">
            <Path d="M9 11l3 3L22 4" stroke="rgba(52,199,89,0.9)" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            <Path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" stroke="rgba(52,199,89,0.9)" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
          </Svg>
        )}
      </View>
      <Text style={styles.onboardingTitle}>{ONBOARDING_STEPS[onboardingStep].title}</Text>
      <Text style={styles.onboardingDescription}>{ONBOARDING_STEPS[onboardingStep].description}</Text>
      <View style={styles.onboardingDots}>
        {ONBOARDING_STEPS.map((_, i) => (
          <View key={i} style={[styles.onboardingDot, i === onboardingStep && styles.onboardingDotActive]} />
        ))}
      </View>
      <TouchableOpacity
        style={styles.onboardingButton}
        onPress={() => {
          if (onboardingStep < ONBOARDING_STEPS.length - 1) {
            setOnboardingStep(prev => prev + 1);
          } else {
            AsyncStorage.setItem('onboarding_complete', 'true');
            setShowOnboarding(false);
          }
        }}
      >
        <Text style={styles.onboardingButtonText}>
          {onboardingStep < ONBOARDING_STEPS.length - 1 ? 'Next' : 'Get Started'}
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
  onPress={() => {
    AsyncStorage.setItem('onboarding_complete', 'true');
    setShowOnboarding(false);
  }}
  hitSlop={{ top: 20, bottom: 20, left: 40, right: 40 }}
>
  <Text style={styles.onboardingSkip}>Skip</Text>
</TouchableOpacity>
    </View>
  </View>
)}
    {/* Dim overlay when video recorded */}
    {recordedVideoPath && !isRecording && !isAnalyzing && !spvGraph && (
    <View style={styles.dimOverlay} pointerEvents="none" />
    )}

{/* Pull to refresh area */}
{!isAnalyzing && !isUploading && (
  <ScrollView
    style={styles.pullScrollView}
    scrollEnabled={true}
    refreshControl={
      <RefreshControl
        refreshing={isRefreshing}
        onRefresh={onRefresh}
        tintColor="white"
        colors={['white']}
      />
    }
  />
)}

      {/* Vertical crosshair line */}
    <View style={styles.verticalLine} />

      {/* Horizontal crosshair line */}
    <View style={styles.horizontalLine} />


    {/* Swipe up handle */}
{!isAnalyzing && !spvGraph && !recordedVideoPath && (
  <View style={styles.swipeHandle} {...panResponder.panHandlers}>
    <View style={styles.swipeHandleBar} />
  </View>
)}

{/* History drawer */}
<Animated.View style={[styles.historyDrawer, {
  transform: [{
    translateY: drawerAnim.interpolate({
      inputRange: [0, 400],
      outputRange: [screenHeight, 0],
    })
  }]
}]} {...panResponder.panHandlers}>
  <TouchableOpacity
    style={styles.drawerCloseArea}
    onPress={() => {
      Animated.spring(drawerAnim, {
        toValue: 0,
        useNativeDriver: false,
      }).start();
      showHistoryRef.current = false;
      setShowHistory(false);
    }}
  >
    <View style={styles.drawerHandle} />
  </TouchableOpacity>
  <Text style={styles.historyTitle}>Past Analyses</Text>
  {historyLoading ? (
    <View style={styles.historyGrid}>
      {[1,2,3,4,5,6].map((i) => (
      <Animated.View key={i} style={[styles.historyGridItem, {
        opacity: skeletonAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [0.4, 0.9],
        })
      }]}>
        <View style={styles.skeletonThumb} />
        <View style={styles.skeletonText} />
      </Animated.View>
    ))}
  </View>
) : historyItems.length === 0 ? (
  <Text style={styles.historyEmpty}>No analyses yet</Text>
) : (
    <View>
      <View style={styles.historyGrid}>
  {historyItems.map((item) => (
    <TouchableOpacity
      key={item.id}
      style={[styles.historyGridItem, selectedForDelete.includes(item.id) && styles.historyGridItemSelected]}
      onPress={() => {
        if (isSelecting) {
          setSelectedForDelete(prev =>
            prev.includes(item.id)
              ? prev.filter(id => id !== item.id)
              : [...prev, item.id]
          );
        } else {
          Animated.spring(drawerAnim, {
            toValue: 0,
            useNativeDriver: false,
          }).start();
          showHistoryRef.current = false;
          setShowHistory(false);
          setSelectedHistoryItem(item);
          setSpvGraph(item.graph);
        }
      }}
      onLongPress={() => {
        setIsSelecting(true);
        setSelectedForDelete([item.id]);
      }}
    >
      <Image
        source={{uri: `data:image/png;base64,${item.graph}`}}
        style={styles.historyGridThumb}
        resizeMode="cover"
      />
      {selectedForDelete.includes(item.id) && (
        <View style={styles.historyGridCheckmark}>
          <Text style={styles.historyGridCheckmarkText}>✓</Text>
        </View>
      )}
      <Text style={styles.historyGridDirection}>{item.direction}</Text>
    </TouchableOpacity>
  ))}
</View>

{/* Selection mode toolbar */}
{isSelecting && (
  <View style={styles.selectionToolbar}>
    <TouchableOpacity
      style={styles.selectionCancelButton}
      onPress={() => {
        setIsSelecting(false);
        setSelectedForDelete([]);
      }}
    >
      <Text style={styles.selectionCancelText}>Cancel</Text>
    </TouchableOpacity>
    <TouchableOpacity
      style={[styles.selectionDeleteButton, selectedForDelete.length === 0 && styles.selectionDeleteButtonDisabled]}
      onPress={() => {
        if (selectedForDelete.length === 0) return;
        Alert.alert(
          'Delete Selected',
          `Delete ${selectedForDelete.length} analysis${selectedForDelete.length > 1 ? 'es' : ''}?`,
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Delete', style: 'destructive', onPress: deleteSelectedFromHistory },
          ]
        );
      }}
    >
      <Text style={styles.selectionDeleteText}>Delete {selectedForDelete.length > 0 ? `(${selectedForDelete.length})` : ''}</Text>
    </TouchableOpacity>
  </View>
)}
  </View>
  )}
</Animated.View>
  {/* Camera switch button */}
    {!showHistory && (
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
    )}

{/* Torch level */}
{!showHistory && isRecording && cameraPosition === 'back' && (
  <TouchableOpacity
    style={styles.torchSliderContainer}
    onPress={() => {
      const currentIndex = TORCH_LEVELS.indexOf(torchLevel);
      const nextIndex = (currentIndex + 1) % TORCH_LEVELS.length;
      const nextLevel = TORCH_LEVELS[nextIndex];
      setTorchLevel(nextLevel);
      TorchPlugin?.setTorchLevel(nextLevel);
    }}
  >
    <Svg width="16" height="16" viewBox="0 0 24 24">
      <Path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="rgba(255,220,80,0.9)" strokeWidth="2" strokeLinecap="round" fill="none"/>
      <Circle cx="12" cy="12" r="4" stroke="rgba(255,220,80,0.9)" strokeWidth="2" fill="none"/>
    </Svg>
    {[...TORCH_LEVELS].reverse().map((level, index) => (
  <View
    key={level}
    style={[
      styles.torchDot,
      torchLevel >= level ? {
        backgroundColor: `rgba(255,220,80,${1 - index * 0.2})`,
        borderColor: `rgba(255,220,80,${1 - index * 0.2})`,
      } : {
        backgroundColor: 'rgba(255,255,255,0.15)',
        borderColor: 'rgba(255,255,255,0.2)',
      }
    ]}
  />
))}
    <Text style={styles.torchPercent}>{Math.round(torchLevel * 100)}%</Text>
  </TouchableOpacity>
)}

{/* Record button */}
{!showHistory && (
<>
  <TouchableOpacity
  style={[styles.recordButton, {backgroundColor: isRecording ? 'red' : 'white'}]}
    onPress={isRecording ? stopRecording : startRecording}
    >
    <View style={[styles.recordInner, isRecording ? styles.recordInnerSquare : styles.recordInnerCircle, {backgroundColor: isRecording ? 'white' : 'red'}]} />
    </TouchableOpacity>
  {isRecording && (
    <Text style={styles.recordingTooltip}>Recording...</Text>
  )}
</>
)}

{/* Upload video button */}
{!showHistory && (
<TouchableOpacity style={styles.uploadButton} onPress={pickAndAnalyzeVideo}>
  <Svg width="54" height="54" viewBox="0 0 512 512">
    <Path fill="#285EFE" d="M256 0c140.799 0 256 115.201 256 256 0 140.803-115.201 256-256 256C115.197 512 0 396.803 0 256S115.197 0 256 0z"/>
    <Path fill="#fff" fillRule="nonzero" d="M198.263 206.44c-4.235-.179-7.245-1.591-8.982-4.231-4.718-7.068 1.722-14.055 6.181-18.971 12.678-13.901 43.72-47.321 49.976-54.682 4.736-5.234 11.487-5.234 16.219 0 6.462 7.548 39.073 42.492 51.118 56.011 4.178 4.707 9.349 11.128 4.995 17.642-1.779 2.64-4.752 4.052-8.99 4.231h-25.722v63.571c0 6.788-5.567 12.363-12.359 12.363h-34.348c-6.791 0-12.359-5.564-12.359-12.363V206.44h-25.729zm-77.738 64.484c-1.415-5.844.969-10.435 4.777-13.156a13.352 13.352 0 014.579-2.078 13.35 13.35 0 015.006-.255c4.639.666 8.866 3.658 10.293 9.521a362.674 362.674 0 012.459 10.899l1.943 9.577c2.539 12.813 4.422 20.851 9.155 24.853 5.002 4.235 14.478 5.699 32.637 5.699h127.541c16.759 0 25.509-1.606 30.106-5.762 4.433-4.006 6.17-11.846 8.42-23.876l.124-.622c1.18-6.35 2.475-13.212 4.302-20.768 1.427-5.859 5.65-8.855 10.293-9.521a13.354 13.354 0 015.005.255c1.629.393 3.205 1.1 4.579 2.078 3.808 2.71 6.193 7.301 4.778 13.152-1.667 6.889-2.947 13.722-4.119 19.998l-.067.363c-3.287 17.578-6.017 29.668-15.062 38.167-8.956 8.416-22.989 11.981-48.359 11.981H191.374c-26.531 0-41.114-3.194-50.493-11.502-9.615-8.518-12.527-20.877-16.238-39.624l-1.969-9.779a334.588 334.588 0 00-2.149-9.6z"/>
  </Svg>
</TouchableOpacity>
)}
{/* Uploading overlay */}
{isUploading && (
  <View style={styles.uploadingOverlay}>
    <View style={styles.uploadingContainer}>
      <Text style={styles.uploadingIcon}>⬆</Text>
      <Text style={styles.uploadingTitle}>Uploading to cloud...</Text>
      <View style={styles.progressBarBackground}>
        <Animated.View style={[styles.progressBarFill, {
          width: progressAnim.interpolate({
            inputRange: [0, 90],
            outputRange: ['0%', '90%'],
          })
        }]} />
      </View>
      <Text style={styles.uploadingSubtitle}>Storing recording securely</Text>
    </View>
  </View>
)}

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
{/* Analyze / Discard buttons - show after recording */}
{recordedVideoPath && !isRecording && !isAnalyzing && (
<View style={styles.analyzeButtonContainer}>
  <TouchableOpacity
    style={styles.discardButton}
    onPress={() => {
      setRecordedVideoPath(null);
      isCapturing.current = false;
    }}
  >
    <Text style={styles.discardButtonText}>Discard</Text>
  </TouchableOpacity>
  <TouchableOpacity style={styles.analyzeButton} onPress={analyzeVideoAuto}>
    <Text style={styles.analyzeButtonText}>Analyze</Text>
  </TouchableOpacity>
</View>
)}
      
    
{/* SPV Graph display */}
{spvGraph && !isUploading && (
  <View style={styles.graphContainer}>
    <TouchableOpacity 
      style={styles.closeButton}
      onPress={() => {
        setSpvGraph(null);
        setRecordedVideoPath(null);
        setSelectedHistoryItem(null);
      }}
    >
      <Text style={styles.closeButtonText}>✕</Text>
    </TouchableOpacity>

    {selectedHistoryItem && (
      <TouchableOpacity
        style={styles.deleteButton}
        onPress={() => {
          Alert.alert(
            'Delete Analysis',
            'Are you sure you want to delete this analysis?',
            [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Delete', style: 'destructive', onPress: () => deleteFromHistory(selectedHistoryItem.id) },
            ]
          );
        }}
      >
        <Svg width="22" height="22" viewBox="0 0 24 24">
          <Path
            d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
          <Path
            d="M10 11v6M14 11v6"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
          />
        </Svg>
      </TouchableOpacity>
    )}
    {selectedHistoryItem && (
      <View style={styles.graphInfo}>
        <Text style={styles.graphInfoDirection}>{selectedHistoryItem.direction} beat</Text>
        <Text style={styles.graphInfoDate}>{selectedHistoryItem.date}</Text>
      </View>
    )}
    <Image
      source={{uri: `data:image/png;base64,${spvGraph}`}}
      style={[styles.graphImage, { width: screenWidth, height: screenHeight * 0.8 }]}
      resizeMode="contain"
    />
  </View>
)}

    {/* Eye and iris overlays */}
{eyeData && eyeData.face_detected && !spvGraph && !isAnalyzing && !recordedVideoPath && !showHistory && (
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
{eyeData && !spvGraph && !isAnalyzing && !recordedVideoPath && !showHistory && (
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
  backgroundColor: 'red',
},
recordInnerCircle: {
  borderRadius: 25,
},
recordInnerSquare: {
  width: 28,
  height: 28,
  borderRadius: 6,
  borderWidth: 2,
  borderColor: 'white',
},
recordingTooltip: {
  position: 'absolute',
  bottom: 122,
  alignSelf: 'center',
  color: 'red',
  fontSize: 14,
  fontWeight: '600',
  backgroundColor: 'white',
  paddingHorizontal: 16,
  paddingVertical: 6,
  borderRadius: 14,
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
  backgroundColor: '#000000',
  justifyContent: 'center',
  alignItems: 'center',
},
graphImage: {
  width: '100%',
  height: '80%',
},
graphInfo: {
  position: 'absolute',
  bottom: 100,
  left: 20,
  right: 80,
},
graphInfoDirection: {
  color: 'white',
  fontSize: 14,
  fontWeight: '500',
  textTransform: 'capitalize',
},
graphInfoDate: {
  color: 'rgba(255,255,255,0.5)',
  fontSize: 12,
  marginTop: 2,
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
  left: 30,
  right: 30,
  flexDirection: 'row',
  justifyContent: 'space-between',
  alignItems: 'center',
},
actionButtonRow: {
  position: 'absolute',
  left: 0,
  right: 0,
  flexDirection: 'row',
  alignItems: 'center',
},
discardButton: {
  backgroundColor: 'rgba(255,255,255,0.1)',
  paddingVertical: 14,
  paddingHorizontal: 32,
  borderRadius: 14,
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: 110,
},
discardButtonText: {
  color: 'rgba(255,255,255,0.6)',
  fontSize: 14,
  fontWeight: '500',
},
analyzeButton: {
  backgroundColor: '#1557c0',
  paddingVertical: 14,
  paddingHorizontal: 32,
  borderRadius: 14,
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: 110,
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
  fontSize: 14,
  fontWeight: '600',
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
uploadingOverlay: {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'black',
  justifyContent: 'center',
  alignItems: 'center',
},
uploadingContainer: {
  alignItems: 'center',
  gap: 14,
  paddingHorizontal: 40,
  width: '100%',
},
uploadingIcon: {
  fontSize: 40,
  color: 'white',
},
uploadingTitle: {
  color: 'white',
  fontSize: 15,
  fontWeight: '500',
},
uploadingSubtitle: {
  color: 'rgba(255,255,255,0.4)',
  fontSize: 11,
  letterSpacing: 0.5,
},
pullScrollView: {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  height: 150,
  backgroundColor: 'transparent',
},
swipeHandle: {
  position: 'absolute',
  bottom: 100,
  left: 0,
  right: 0,
  height: 60,
  alignItems: 'center',
  justifyContent: 'center',
},
swipeHandleBar: {
  width: 40,
  height: 4,
  backgroundColor: 'rgba(255,255,255,0.4)',
  borderRadius: 2,
},
historyDrawer: {
  position: 'absolute',
  top: 0,
  bottom: 0,
  left: 0,
  right: 0,
  backgroundColor: 'rgba(15,15,15,0.97)',
  padding: 20,
  paddingTop: 60,
},
drawerCloseArea: {
  alignItems: 'center',
  paddingBottom: 16,
},
drawerHandle: {
  width: 40,
  height: 4,
  backgroundColor: 'rgba(255,255,255,0.3)',
  borderRadius: 2,
},
historyTitle: {
  color: 'white',
  fontSize: 16,
  fontWeight: '500',
  marginBottom: 16,
},
historyEmpty: {
  color: 'rgba(255,255,255,0.4)',
  fontSize: 14,
  textAlign: 'center',
  marginTop: 40,
},
historyGrid: {
  flexDirection: 'row',
  flexWrap: 'wrap',
  gap: 6,
},
historyGridItem: {
  width: '31%',
  backgroundColor: 'rgba(255,255,255,0.08)',
  borderRadius: 8,
  overflow: 'hidden',
},
historyGridThumb: {
  width: '100%',
  height: 70,
  backgroundColor: 'rgba(255,255,255,0.05)',
},
historyGridDirection: {
  color: 'rgba(255,255,255,0.6)',
  fontSize: 9,
  textTransform: 'capitalize',
  padding: 4,
},
skeletonThumb: {
  width: '100%',
  height: 70,
  backgroundColor: 'rgba(255,255,255,0.08)',
  borderRadius: 8,
},
skeletonText: {
  width: '60%',
  height: 6,
  backgroundColor: 'rgba(255,255,255,0.08)',
  borderRadius: 3,
  margin: 6,
},
historyGridItemSelected: {
  borderWidth: 2,
  borderColor: '#1a73e8',
},
historyGridCheckmark: {
  position: 'absolute',
  top: 4,
  right: 4,
  width: 20,
  height: 20,
  borderRadius: 10,
  backgroundColor: '#1a73e8',
  justifyContent: 'center',
  alignItems: 'center',
},
historyGridCheckmarkText: {
  color: 'white',
  fontSize: 12,
  fontWeight: 'bold',
},
selectionToolbar: {
  flexDirection: 'row',
  justifyContent: 'space-between',
  alignItems: 'center',
  paddingTop: 16,
  paddingHorizontal: 8,
  borderTopWidth: 0.5,
  borderTopColor: 'rgba(255,255,255,0.1)',
  marginTop: 12,
},
selectionCancelButton: {
  padding: 10,
},
selectionCancelText: {
  color: 'rgba(255,255,255,0.6)',
  fontSize: 14,
},
selectionDeleteButton: {
  backgroundColor: '#e24b4a',
  paddingVertical: 8,
  paddingHorizontal: 20,
  borderRadius: 10,
},
selectionDeleteButtonDisabled: {
  backgroundColor: 'rgba(255,255,255,0.1)',
},
selectionDeleteText: {
  color: 'white',
  fontSize: 14,
  fontWeight: '500',
},
onboardingOverlay: {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'rgba(0,0,0,0.85)',
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 100,
},
onboardingCard: {
  backgroundColor: 'rgba(20,20,20,0.98)',
  borderRadius: 24,
  padding: 28,
  width: '82%',
  alignItems: 'center',
  gap: 12,
  borderWidth: 0.5,
  borderColor: 'rgba(255,255,255,0.1)',
},
onboardingIconContainer: {
  width: 64,
  height: 64,
  borderRadius: 32,
  backgroundColor: 'rgba(255,255,255,0.06)',
  justifyContent: 'center',
  alignItems: 'center',
  marginBottom: 4,
},
onboardingTitle: {
  color: 'white',
  fontSize: 17,
  fontWeight: '500',
  textAlign: 'center',
},
onboardingDescription: {
  color: 'rgba(255,255,255,0.5)',
  fontSize: 13,
  textAlign: 'center',
  lineHeight: 20,
},
onboardingDots: {
  flexDirection: 'row',
  gap: 6,
  marginTop: 4,
},
onboardingDot: {
  width: 6,
  height: 6,
  borderRadius: 3,
  backgroundColor: 'rgba(255,255,255,0.2)',
},
onboardingDotActive: {
  width: 18,
  backgroundColor: '#007AFF',
},
onboardingButton: {
  backgroundColor: '#007AFF',
  borderRadius: 12,
  paddingVertical: 12,
  paddingHorizontal: 40,
  marginTop: 4,
  width: '100%',
  alignItems: 'center',
},
onboardingButtonText: {
  color: 'white',
  fontSize: 15,
  fontWeight: '500',
},
onboardingSkip: {
  color: 'rgba(255,255,255,0.3)',
  fontSize: 13,
  marginTop: 4,
},
deleteButton: {
  position: 'absolute',
  bottom: 104,
  right: 20,
  backgroundColor: 'rgba(255,255,255,0.15)',
  width: 36,
  height: 36,
  borderRadius: 18,
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 10,
},
torchSliderContainer: {
  position: 'absolute',
  right: 14,
  top: '30%',
  width: 52,
  backgroundColor: 'rgba(255,255,255,0.08)',
  borderRadius: 26,
  paddingVertical: 16,
  alignItems: 'center',
  gap: 10,
},
torchDot: {
  width: 22,
  height: 22,
  borderRadius: 11,
  backgroundColor: 'rgba(255,255,255,0.15)',
  borderWidth: 1,
  borderColor: 'rgba(255,255,255,0.2)',
},
torchDotActive: {
  backgroundColor: 'rgba(255,220,80,0.9)',
  borderColor: 'rgba(255,220,80,0.9)',
},
torchPercent: {
  color: 'rgba(255,220,80,0.7)',
  fontSize: 9,
  fontWeight: '500',
},

});

export default App;