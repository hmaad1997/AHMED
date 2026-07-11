import 'dart:io';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

/// Audio recording service
class AudioService {
  final AudioRecorder _recorder = AudioRecorder();
  String? _recordingPath;
  bool _isRecording = false;

  bool get isRecording => _isRecording;
  String? get recordingPath => _recordingPath;

  /// Request microphone permission
  Future<bool> requestPermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  /// Check if permission is granted
  Future<bool> hasPermission() async {
    final status = await Permission.microphone.status;
    return status.isGranted;
  }

  /// Start recording
  Future<void> startRecording() async {
    try {
      // Check permission
      if (!await hasPermission()) {
        final granted = await requestPermission();
        if (!granted) {
          throw Exception('Microphone permission denied');
        }
      }

      // Get temp directory
      final directory = await getTemporaryDirectory();
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      _recordingPath = '${directory.path}/recording_$timestamp.wav';

      // Start recording
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: _recordingPath!,
      );

      _isRecording = true;
      print('Recording started: $_recordingPath');
    } catch (e) {
      print('Error starting recording: $e');
      rethrow;
    }
  }

  /// Stop recording
  Future<String?> stopRecording() async {
    try {
      if (!_isRecording) {
        return null;
      }

      final path = await _recorder.stop();
      _isRecording = false;

      print('Recording stopped: $path');

      // Verify file exists
      if (path != null && await File(path).exists()) {
        final file = File(path);
        final size = await file.length();
        print('Recording file size: ${size / 1024} KB');

        if (size < 1000) {
          // Less than 1KB is likely invalid
          throw Exception('Recording file too small');
        }

        return path;
      }

      return null;
    } catch (e) {
      print('Error stopping recording: $e');
      _isRecording = false;
      rethrow;
    }
  }

  /// Cancel recording
  Future<void> cancelRecording() async {
    try {
      if (_isRecording) {
        await _recorder.stop();
        _isRecording = false;
      }

      // Delete the file if it exists
      if (_recordingPath != null) {
        final file = File(_recordingPath!);
        if (await file.exists()) {
          await file.delete();
        }
      }

      _recordingPath = null;
    } catch (e) {
      print('Error canceling recording: $e');
    }
  }

  /// Get recording duration (while recording)
  Stream<int> getRecordingDuration() async* {
    int seconds = 0;
    while (_isRecording) {
      await Future.delayed(const Duration(seconds: 1));
      seconds++;
      yield seconds;
    }
  }

  /// Dispose resources
  void dispose() {
    _recorder.dispose();
  }
}
