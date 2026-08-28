#!/usr/bin/env python3
"""
Sakura ML Detector - FFT-based Real vs AI Image Classification

Fast Fourier Transform feature extraction + weighted scoring classifier.
Runs fully offline, no external APIs or GPU required.

Usage:
    python3 ml_detector.py --image path/to/image.jpg
    python3 ml_detector.py --image test.jpg --debug
    python3 ml_detector.py --batch input_images/ --output results.json
"""

import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional

import numpy as np
from PIL import Image
from scipy import signal


class SakuraDetector:
    """FFT-based image classifier: REAL vs AI detection."""
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.45,
        debug: bool = False
    ):
        """
        Initialize detector with configurable weights and threshold.
        
        Args:
            weights: Feature weights {ratio_high_mid, peakiness, anisotropy}
            threshold: Classification threshold (score > T → AI, else REAL)
            debug: Enable verbose logging
        """
        # Default weights (balanced for general use)
        self.weights = weights or {
            'ratio_high_mid': 0.40,
            'peakiness': 0.35,
            'anisotropy': 0.25
        }
        self.threshold = threshold
        self.debug = debug
        
        # Validate weights sum to 1.0
        weight_sum = sum(self.weights.values())
        if not np.isclose(weight_sum, 1.0):
            raise ValueError(
                f"Weights must sum to 1.0, got {weight_sum}. "
                f"Weights: {self.weights}"
            )
    
    def extract_features(self, image: Image.Image) -> Dict[str, float]:
        """
        Extract FFT-based features from image.
        
        Features:
        - ratio_high_mid: High-to-mid frequency energy ratio
        - peakiness: Spectral concentration (max/mean magnitude)
        - anisotropy: Directional bias (horizontal/vertical preference)
        
        Args:
            image: PIL Image (any format, any size)
            
        Returns:
            Dict with computed features
        """
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Resize to max 1024×1024 for efficiency
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
        # Compute 2D FFT
        img_array = np.array(image, dtype=np.float32)
        fft_2d = np.fft.fft2(img_array)
        fft_shifted = np.fft.fftshift(fft_2d)
        magnitude = np.abs(fft_shifted)
        
        # Normalize by image size
        magnitude = magnitude / (img_array.size)
        
        if self.debug:
            print(f"[DEBUG] Image shape: {img_array.shape}")
            print(f"[DEBUG] FFT magnitude range: [{magnitude.min():.4f}, {magnitude.max():.4f}]")
        
        # Feature 1: ratio_high_mid (high-to-mid frequency ratio)
        # AI images have sharp edges → more high-frequency energy
        threshold_high = 0.8 * magnitude.max()
        threshold_mid = 0.4 * magnitude.max()
        
        high_energy = np.sum(magnitude[magnitude > threshold_high])
        mid_energy = np.sum(magnitude[(magnitude > threshold_mid) & (magnitude <= threshold_high)])
        
        ratio_high_mid = (high_energy / (mid_energy + 1e-8)) if mid_energy > 0 else high_energy
        ratio_high_mid = np.clip(ratio_high_mid, 0, 10)  # Normalize to [0, 10] range
        
        # Feature 2: peakiness (spectral concentration)
        # AI images have sharp peaks at specific frequencies
        peakiness = magnitude.max() / (magnitude.mean() + 1e-8)
        peakiness = np.clip(peakiness, 0, 100)  # Normalize to [0, 100]
        
        # Feature 3: anisotropy (directional bias)
        # AI images prefer horizontal/vertical patterns
        h, w = magnitude.shape
        h_center, w_center = h // 2, w // 2
        
        # Horizontal slice (center row)
        h_energy = np.sum(magnitude[h_center - 5:h_center + 5, :])
        
        # Vertical slice (center column)
        v_energy = np.sum(magnitude[:, w_center - 5:w_center + 5])
        
        total_energy = h_energy + v_energy + 1e-8
        anisotropy = max(h_energy, v_energy) / total_energy
        anisotropy = np.clip(anisotropy, 0, 1)  # Naturally [0, 1]
        
        if self.debug:
            print(f"[DEBUG] ratio_high_mid: {ratio_high_mid:.4f}")
            print(f"[DEBUG] peakiness: {peakiness:.4f}")
            print(f"[DEBUG] anisotropy: {anisotropy:.4f}")
        
        return {
            'ratio_high_mid': float(ratio_high_mid),
            'peakiness': float(peakiness),
            'anisotropy': float(anisotropy)
        }
    
    def normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize features to [0, 1] range for scoring.
        
        Args:
            features: Raw extracted features
            
        Returns:
            Normalized features
        """
        normalized = {
            'ratio_high_mid': min(features['ratio_high_mid'] / 10.0, 1.0),
            'peakiness': min(features['peakiness'] / 100.0, 1.0),
            'anisotropy': features['anisotropy']  # Already [0, 1]
        }
        
        if self.debug:
            print(f"[DEBUG] Normalized features: {normalized}")
        
        return normalized
    
    def compute_score(self, features: Dict[str, float]) -> float:
        """
        Compute classification score via weighted sum.
        
        Score = w_1 × f_1 + w_2 × f_2 + w_3 × f_3
        
        Args:
            features: Normalized features [0, 1]
            
        Returns:
            Score in range [0, 1]
        """
        score = (
            self.weights['ratio_high_mid'] * features['ratio_high_mid'] +
            self.weights['peakiness'] * features['peakiness'] +
            self.weights['anisotropy'] * features['anisotropy']
        )
        return float(np.clip(score, 0, 1))
    
    def classify(self, image_path: str) -> Dict:
        """
        Full classification pipeline: load → extract → score → classify.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with classification result and metadata
        """
        # Load image
        try:
            image = Image.open(image_path)
            if self.debug:
                print(f"[DEBUG] Loaded image: {image_path} ({image.format}, {image.size})")
        except Exception as e:
            return {
                'error': f"Failed to load image: {str(e)}",
                'image_path': image_path,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Extract features
        features = self.extract_features(image)
        
        # Normalize
        normalized_features = self.normalize_features(features)
        
        # Score
        score = self.compute_score(normalized_features)
        
        # Classify
        classification = 'AI' if score > self.threshold else 'REAL'
        confidence = abs(score - self.threshold) / max(self.threshold, 1 - self.threshold)
        
        # Compute image hash for audit trail
        with open(image_path, 'rb') as f:
            image_hash = hashlib.sha256(f.read()).hexdigest()
        
        result = {
            'image_path': image_path,
            'classification': classification,
            'score': score,
            'confidence': min(confidence, 1.0),
            'features': features,
            'normalized_features': normalized_features,
            'weights': self.weights,
            'threshold': self.threshold,
            'image_hash': image_hash,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if self.debug:
            print(f"[DEBUG] Result: {json.dumps(result, indent=2)}")
        
        return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Sakura ML Detector - FFT-based Real vs AI image classification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ml_detector.py --image photo.jpg
  python3 ml_detector.py --image test.jpg --debug
  python3 ml_detector.py --batch input_images/ --output results.json
  python3 ml_detector.py --image test.jpg --weights weights.json --threshold 0.5
        """
    )
    
    parser.add_argument('--image', type=str, help='Single image to classify')
    parser.add_argument('--batch', type=str, help='Batch process directory')
    parser.add_argument('--output', type=str, default='results.jsonl', 
                        help='Output file for results (default: results.jsonl)')
    parser.add_argument('--weights', type=str, help='JSON file with custom weights')
    parser.add_argument('--threshold', type=float, default=0.45, 
                        help='Classification threshold (default: 0.45)')
    parser.add_argument('--debug', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Load custom weights if provided
    weights = None
    if args.weights:
        try:
            with open(args.weights) as f:
                weights = json.load(f)
                print(f"Loaded weights: {weights}")
        except Exception as e:
            print(f"Error loading weights: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Initialize detector
    detector = SakuraDetector(weights=weights, threshold=args.threshold, debug=args.debug)
    
    results = []
    
    # Single image
    if args.image:
        if not Path(args.image).exists():
            print(f"Error: Image not found: {args.image}", file=sys.stderr)
            sys.exit(1)
        
        result = detector.classify(args.image)
        results.append(result)
        
        # Print to stdout
        print(json.dumps(result, indent=2))
    
    # Batch processing
    elif args.batch:
        batch_path = Path(args.batch)
        if not batch_path.is_dir():
            print(f"Error: Directory not found: {args.batch}", file=sys.stderr)
            sys.exit(1)
        
        # Find all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        image_files = [
            f for f in batch_path.iterdir()
            if f.suffix.lower() in image_extensions
        ]
        
        print(f"Processing {len(image_files)} images from {args.batch}")
        
        for image_file in image_files:
            result = detector.classify(str(image_file))
            results.append(result)
            
            # Print progress
            classification = result.get('classification', 'ERROR')
            score = result.get('score', 0)
            print(f"  {image_file.name}: {classification} (score: {score:.3f})")
        
        # Write results to file
        with open(args.output, 'w') as f:
            for result in results:
                f.write(json.dumps(result) + '\n')
        
        print(f"\nResults saved to: {args.output}")
        print(f"Summary: {len(results)} images processed")
        
        # Print summary
        ai_count = sum(1 for r in results if r.get('classification') == 'AI')
        real_count = sum(1 for r in results if r.get('classification') == 'REAL')
        print(f"  AI: {ai_count} ({100*ai_count/len(results):.1f}%)")
        print(f"  REAL: {real_count} ({100*real_count/len(results):.1f}%)")
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
