/// Model for Reciter Information
class ReciterModel {
  final int id;
  final String name;
  final String nameEnglish;
  final String country;
  final String bio;
  final String birthYear;
  final String? deathYear;
  final String imageUrl;
  final String recitationStyle;
  final double? confidence;
  final double? similarityScore;

  ReciterModel({
    required this.id,
    required this.name,
    required this.nameEnglish,
    required this.country,
    required this.bio,
    required this.birthYear,
    this.deathYear,
    required this.imageUrl,
    required this.recitationStyle,
    this.confidence,
    this.similarityScore,
  });

  /// Create from API JSON response
  factory ReciterModel.fromJson(Map<String, dynamic> json) {
    return ReciterModel(
      id: json['id'] ?? 0,
      name: json['reciter_name'] ?? json['name'] ?? '',
      nameEnglish: json['reciter_name_english'] ?? json['name_english'] ?? '',
      country: json['country'] ?? '',
      bio: json['bio'] ?? '',
      birthYear: json['birth_year'] ?? '',
      deathYear: json['death_year'],
      imageUrl: json['image_url'] ?? '',
      recitationStyle: json['recitation_style'] ?? '',
      confidence: json['confidence']?.toDouble(),
      similarityScore: json['similarity_score']?.toDouble(),
    );
  }

  /// Convert to JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'name_english': nameEnglish,
      'country': country,
      'bio': bio,
      'birth_year': birthYear,
      'death_year': deathYear,
      'image_url': imageUrl,
      'recitation_style': recitationStyle,
      'confidence': confidence,
      'similarity_score': similarityScore,
    };
  }

  /// Check if reciter is alive
  bool get isAlive => deathYear == null;

  /// Get formatted years string
  String get yearsString {
    if (deathYear != null) {
      return '$birthYear - $deathYear';
    }
    return 'مواليد $birthYear';
  }

  /// Get confidence percentage string
  String get confidencePercent {
    if (confidence != null) {
      return '${(confidence! * 100).toStringAsFixed(0)}%';
    }
    return 'N/A';
  }
}
