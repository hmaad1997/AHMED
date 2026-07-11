import 'package:flutter/material.dart';
import '../services/audio_service.dart';
import '../services/api_service.dart';
import '../models/reciter_model.dart';
import 'result_screen.dart';
import 'dart:async';

/// Recording screen with waveform visualization
class RecordingScreen extends StatefulWidget {
  const RecordingScreen({Key? key}) : super(key: key);

  @override
  State<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends State<RecordingScreen>
    with SingleTickerProviderStateMixin {
  final AudioService _audioService = AudioService();
  final ApiService _apiService = ApiService();

  bool _isRecording = false;
  bool _isProcessing = false;
  int _recordingDuration = 0;
  Timer? _durationTimer;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _durationTimer?.cancel();
    _pulseController.dispose();
    _audioService.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    try {
      await _audioService.startRecording();
      setState(() {
        _isRecording = true;
        _recordingDuration = 0;
      });

      // Start duration timer
      _durationTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (mounted) {
          setState(() {
            _recordingDuration++;
          });
        }
      });
    } catch (e) {
      _showError('فشل التسجيل: ${e.toString()}');
    }
  }

  Future<void> _stopRecording() async {
    try {
      _durationTimer?.cancel();

      if (_recordingDuration < 3) {
        _showError('يجب أن يكون التسجيل 3 ثواني على الأقل');
        await _audioService.cancelRecording();
        setState(() {
          _isRecording = false;
          _recordingDuration = 0;
        });
        return;
      }

      final path = await _audioService.stopRecording();

      setState(() {
        _isRecording = false;
        _isProcessing = true;
      });

      if (path != null) {
        // Send to API
        final reciter = await _apiService.identifyReciter(path);

        if (mounted) {
          setState(() {
            _isProcessing = false;
          });

          if (reciter != null) {
            // Navigate to result screen
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => ResultScreen(reciter: reciter),
              ),
            );
          } else {
            _showError('لم يتم التعرف على القارئ');
          }
        }
      } else {
        setState(() {
          _isProcessing = false;
        });
        _showError('فشل حفظ التسجيل');
      }
    } catch (e) {
      setState(() {
        _isProcessing = false;
        _isRecording = false;
      });
      _showError('خطأ: ${e.toString()}');
    }
  }

  void _showError(String message) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  String _formatDuration(int seconds) {
    final mins = seconds ~/ 60;
    final secs = seconds % 60;
    return '${mins.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.teal.shade50,
            Colors.white,
          ],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Title
          const Padding(
            padding: EdgeInsets.all(24.0),
            child: Text(
              'اضغط على الميكروفون لبدء التسجيل',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 20,
                color: Colors.black87,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),

          const SizedBox(height: 40),

          // Recording visualization
          if (_isRecording)
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Container(
                  width: 200 + (_pulseController.value * 40),
                  height: 200 + (_pulseController.value * 40),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.teal.withOpacity(0.1 + _pulseController.value * 0.2),
                  ),
                  child: child,
                );
              },
              child: Center(
                child: Container(
                  width: 200,
                  height: 200,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.teal.shade400,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.teal.withOpacity(0.3),
                        blurRadius: 20,
                        spreadRadius: 10,
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.mic,
                    size: 80,
                    color: Colors.white,
                  ),
                ),
              ),
            )
          else if (_isProcessing)
            Container(
              width: 200,
              height: 200,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.orange.shade100,
              ),
              child: const Center(
                child: CircularProgressIndicator(
                  strokeWidth: 6,
                  valueColor: AlwaysStoppedAnimation(Colors.orange),
                ),
              ),
            )
          else
            // Idle state - record button
            GestureDetector(
              onTap: _startRecording,
              child: Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.teal.shade600,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.teal.withOpacity(0.4),
                      blurRadius: 15,
                      spreadRadius: 5,
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.mic,
                  size: 80,
                  color: Colors.white,
                ),
              ),
            ),

          const SizedBox(height: 40),

          // Duration display
          if (_isRecording)
            Text(
              _formatDuration(_recordingDuration),
              style: TextStyle(
                fontSize: 48,
                fontWeight: FontWeight.bold,
                color: Colors.teal.shade700,
              ),
            )
          else if (_isProcessing)
            const Text(
              'جاري التحليل...',
              style: TextStyle(
                fontSize: 24,
                color: Colors.orange,
                fontWeight: FontWeight.bold,
              ),
            )
          else
            Text(
              'اضغط للتسجيل',
              style: TextStyle(
                fontSize: 18,
                color: Colors.grey.shade600,
              ),
            ),

          const SizedBox(height: 60),

          // Stop button (only show when recording)
          if (_isRecording)
            ElevatedButton.icon(
              onPressed: _stopRecording,
              icon: const Icon(Icons.stop, size: 28),
              label: const Text(
                'إيقاف وتحليل',
                style: TextStyle(fontSize: 20),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 40,
                  vertical: 16,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(30),
                ),
              ),
            ),

          const SizedBox(height: 20),

          // Instructions
          if (!_isRecording && !_isProcessing)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(
                'نصيحة: سجّل 5-10 ثواني من التلاوة للحصول على أفضل النتائج',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey.shade600,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
