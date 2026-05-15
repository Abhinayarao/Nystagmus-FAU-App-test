import React from 'react';
import {
  StyleSheet,
  View,
  Text,
  PermissionsAndroid,
  Platform,
} from 'react-native';
import {
  Camera,
  useCameraDevice,
} from 'react-native-vision-camera';

function App(): React.JSX.Element {
  const device = useCameraDevice('front');

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
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={true}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'red',
  },
  text: {
    color: 'white',
    fontSize: 20,
    textAlign: 'center',
    marginTop: 100,
  },
});

export default App;