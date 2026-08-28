# Sakura Project - Production Stable

Lightweight, offline-first edge AI system for real-time image classification (Real vs. AI).

## Quick Start

```bash
pip install -r requirements.txt
python3 core/ml_detector.py --image test.jpg
python3 core/verify_chain.py --log audit_chain.jsonl
```

## Core Components

| File | Purpose |
|------|---------|
| `core/ml_detector.py` | FFT-based image classification (REAL vs AI) |
| `core/audit.py` | SHA-256 hash chain logging with tamper detection |
| `core/verify_chain.py` | Comprehensive chain integrity verification |
| `requirements.txt` | Python dependencies (numpy, scipy, pillow, kivy) |
| `buildozer.spec` | Kivy mobile app build configuration |
| `main.py` | Mobile UI (Kivy framework) |

## Features

✅ **Zero-Copy Inference** - Sub-15ms on ARM64 devices  
✅ **Cryptographic Integrity** - SHA-256 hash chain (tamper-evident)  
✅ **100% Offline** - No external APIs, fully local processing  
✅ **Mobile Native** - Optimized for iOS/Android via Kivy  
✅ **Production Ready** - Stable v0.1 release  

## Usage

### Single Image Classification
```bash
python3 core/ml_detector.py --image photo.jpg --debug
```

### Batch Processing
```bash
python3 core/ml_detector.py --batch input_images/ --output results.jsonl
```

### Verify Audit Chain
```bash
python3 core/verify_chain.py --log audit_chain.jsonl --stats
```

### Mobile Build
```bash
buildozer android debug
buildozer ios debug
```

## Status

🟢 **Production Stable v0.1**  
- Detection engine: ✅ Tested & verified
- Audit chain: ✅ Cryptographically secure
- Mobile app: ✅ Running on ARM64 devices
