import 'dart:io';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../models/reciter_model.dart';

/// API Service for communicating with the backend
class ApiService {
  // Base URL - change this to your server IP if testing on physical device
  static const String baseUrl = 'http://localhost:8000';
  
  // For Android Emulator, use: 'http://10.0.2.2:8000'
  // For physical device, use your computer's IP: 'http://192.168.x.x:8000'

  /// Check server health
  Future<bool> checkHealth() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/health'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 5));

      return response.statusCode == 200;
    } catch (e) {
      print('Health check failed: $e');
      return false;
    }
  }

  /// Identify reciter from audio file
  Future<ReciterModel?> identifyReciter(String audioFilePath) async {
    try {
      final uri = Uri.parse('$baseUrl/identify-reciter');
      final request = http.MultipartRequest('POST', uri);

      // Add audio file
      final file = await http.MultipartFile.fromPath(
        'audio_file',
        audioFilePath,
        filename: 'recording.wav',
      );
      request.files.add(file);

      // Send request
      print('Sending audio to server...');
      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 30),
      );

      // Get response
      final response = await http.Response.fromStream(streamedResponse);

      print('Response status: ${response.statusCode}');
      print('Response body: ${response.body}');

      if (response.statusCode == 200) {
        final jsonData = json.decode(response.body);
        return ReciterModel.fromJson(jsonData);
      } else {
        final errorData = json.decode(response.body);
        throw Exception(errorData['detail'] ?? 'Unknown error');
      }
    } catch (e) {
      print('Error identifying reciter: $e');
      rethrow;
    }
  }

  /// Get list of all reciters
  Future<List<ReciterModel>> getAllReciters() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/list-reciters'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final jsonData = json.decode(response.body);
        final reciters = (jsonData['reciters'] as List)
            .map((json) => ReciterModel.fromJson(json))
            .toList();
        return reciters;
      } else {
        throw Exception('Failed to load reciters');
      }
    } catch (e) {
      print('Error loading reciters: $e');
      rethrow;
    }
  }

  /// Get database stats
  Future<Map<String, dynamic>> getStats() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/stats'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to load stats');
      }
    } catch (e) {
      print('Error loading stats: $e');
      rethrow;
    }
  }
}
