# 🎙️ Voice Watermarking & Detection System

> A robust, frequency-domain audio authentication framework designed to combat AI-generated voice deepfakes through inaudible watermarking and spectral anomaly detection.

---

## 📌 Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Robustness](#robustness)
- [Project Structure](#project-structure)
- [Team](#team)
- [License](#license)

---

## Overview

The **Voice Watermarking & Detection System (VWS)** is a Python-based security framework that embeds cryptographically keyed, inaudible watermarks into audio files and detects whether a given audio recording is authentic or synthetically generated (deepfake).

As AI-based voice cloning becomes increasingly accessible, the need for trustworthy audio authentication has never been more urgent. VWS addresses this by combining:

- **Spread-spectrum frequency-domain watermarking** — for robust, imperceptible embedding
- **Spectral anomaly detection** — for identifying artefacts left behind by voice synthesis models

---

## The Problem

Deepfake audio poses growing threats across multiple domains:

| Threat | Impact |
|---|---|
| Misinformation | Fabricated speeches, manipulated public figures |
| Financial fraud | Voice-cloned CEO/CFO scam calls |
| Impersonation | Identity fraud in legal or medical contexts |
| Evidentiary integrity | Courts cannot verify audio recordings |

Existing detection methods fail when audio undergoes common transformations — MP3 compression, trimming, noise addition, or format conversion.

---

## Features

- ✅ **Inaudible watermarking** — Embeds payload bits in the 1 kHz–8 kHz band using psychoacoustic masking
- ✅ **FFT / Frequency-domain processing** — Spread-spectrum embedding survives lossy compression
- ✅ **Secret-key authentication** — PRNG carrier seeded by a shared secret; detection requires the key
- ✅ **Error-corrected payload** — Triple-repetition code recovers up to 33% corrupted bits
- ✅ **Deepfake anomaly detection** — Measures spectral flatness, phase discontinuity, and harmonic distribution
- ✅ **Structured auth reports** — Verdict: `AUTHENTIC` | `SUSPECT` | `DEEPFAKE`
- ✅ **File-based API** — Protect and verify `.wav` files with two function calls
- ✅ **Built-in robustness test suite** — Validates watermark survival across transforms

---

## Architecture

```
┌──────────────┐    FFT     ┌──────────────────────┐   iFFT   ┌─────────────────┐
│  Original    │ ─────────▶ │  Frequency Domain     │ ───────▶ │  Watermarked    │
│  Audio       │            │  Watermark Embedding  │          │  Audio          │
└──────────────┘            └──────────────────────┘          └─────────────────┘

┌──────────────┐    FFT     ┌──────────────────────┐           ┌─────────────────┐
│  Test Audio  │ ─────────▶ │  Correlation +        │ ───────▶ │  Auth Report    │
└──────────────┘            │  Anomaly Detection    │           └─────────────────┘
                            └──────────────────────┘
```

### Core Components

**`WatermarkEmbedder`**
Splits audio into overlapping frames, transforms each via FFT, and scatters watermark bits across the embed band using a pseudo-random carrier scaled by local band power (psychoacoustic masking). Reconstruct via iFFT with overlap-add.

**`WatermarkDetector`**
Cross-correlates incoming frames against the expected PRNG carrier. If ≥ 55% of frames exceed the correlation threshold, the watermark is confirmed.

**`SpectralAnomalyDetector`**
Extracts 5 spectral features per segment (centroid, bandwidth, rolloff, flatness, phase discontinuity) and flags patterns characteristic of vocoder/deepfake synthesis.

**`VoiceWatermarkSystem`**
Unified façade exposing `protect()` and `verify()` methods for easy integration.

---

## Installation

### Requirements

- Python 3.8+
- `numpy`
- `scipy` *(recommended)*
- `scikit-learn` *(recommended)*
- `soundfile` *(for file-based API)*

### Install dependencies

```bash
pip install numpy scipy scikit-learn soundfile
```

### Clone the repository

```bash
git clone https://github.com/shivamyadav17062006-code/voice-watermark-system.git
cd voice-watermark-system
```

---

## Usage

### 1. Array-based API

```python
from voice_watermark_system import VoiceWatermarkSystem
import numpy as np

# Initialise with your shared secret key
vws = VoiceWatermarkSystem(secret_key="my-org-secret")

# Load or generate audio (float32, normalised to [-1, 1])
audio = np.random.randn(16000 * 5).astype(np.float32) * 0.3
sample_rate = 16000

# Embed watermark with optional metadata
watermarked = vws.protect(audio, sample_rate, metadata={
    "author": "Alice",
    "device": "studio-mic-A",
    "project": "podcast-ep42"
})

# Verify authenticity
report = vws.verify(watermarked, sample_rate)
print(report)
```

**Example output:**
```
╔══════════════════════════════════════╗
║  VERDICT : AUTHENTIC                  ║
╠══════════════════════════════════════╣
║  Watermark detected : True           ║
║  Watermark confidence: 0.873             ║
║  Anomaly detected   : False          ║
║  Anomaly score      : 0.3841            ║
║  Frames analysed    : 38             ║
║  Frames w/ watermark: 33             ║
╚══════════════════════════════════════╝
```

### 2. File-based API

```python
from voice_watermark_system import FileAPI

api = FileAPI(secret_key="my-org-secret")

# Protect a WAV file
api.protect_file("input.wav", "protected.wav", metadata={"source": "studio-A"})

# Verify a WAV file
report = api.verify_file("protected.wav")
print(report)
```

### 3. Run the built-in test suite

```bash
python voice_watermark_system.py
```

---

## Robustness

The watermark is designed to survive common audio transformations:

| Transform | Survival |
|---|---|
| Lossless / FLAC | ✅ Full |
| MP3 @ 128 kbps | ✅ Survives MDCT compression |
| AAC @ 96 kbps | ✅ |
| Additive noise (SNR ≥ 20 dB) | ✅ |
| Trim to 70% of duration | ✅ |
| Amplitude normalisation | ✅ |
| 8-bit quantisation | ✅ |
| Time-stretch ± 10% | ⚠️ Partial (future work) |

### Deepfake Detection

| Audio Type | Anomaly Score | Verdict |
|---|---|---|
| Real speech (watermarked) | ~0.41 | AUTHENTIC |
| Real speech (no watermark) | ~0.41 | SUSPECT |
| Vocoder / deepfake | ~0.69 | DEEPFAKE |

---

## Project Structure

```
voice-watermark-system/
│
├── voice_watermark_system.py   # Main system — all components
├── README.md                   # This file
│
├── examples/
│   ├── basic_usage.py          # Simple protect + verify demo
│   └── file_api_demo.py        # File-based workflow
│
└── tests/
    └── robustness_suite.py     # Transformation robustness tests
```

---

## Team

This project was built by a dedicated team committed to fighting audio deepfakes:

<br>

### 👑 Team Leader

| | |
|---|---|
| **Name** | Shivam Yadav |
| **Role** | Team Leader & Lead Developer |
| **GitHub** | [@shivamyadav17062006-code](https://github.com/shivamyadav17062006-code) |

<br>

### 👥 Members

| Name | GitHub |
|---|---|
| **Ashiwan Singh** | [@ashiwansingh-5016](https://github.com/ashiwansingh-5016) |
| **Krish Phogat** | [@krishphogat](https://github.com/krishphogat) |

---

## Configuration

Key parameters can be customised via `WatermarkConfig`:

```python
from voice_watermark_system import WatermarkConfig, VoiceWatermarkSystem

config = WatermarkConfig(
    secret_key       = "my-secret",      # Shared authentication key
    payload_bits     = 64,               # Bits of metadata to embed
    frame_size       = 4096,             # FFT window size (samples)
    embed_band_low_hz  = 1000.0,         # Lower embed frequency (Hz)
    embed_band_high_hz = 8000.0,         # Upper embed frequency (Hz)
    embed_strength   = 0.015,            # Watermark intensity (inaudibility trade-off)
    detection_threshold = 0.35,          # Per-frame correlation threshold
    min_frames_detected = 0.55,          # Fraction of frames needed for positive detect
    use_bch          = True              # Enable error-correction coding
)

vws = VoiceWatermarkSystem.__new__(VoiceWatermarkSystem)
vws.config = config
```

---

## Future Work

- [ ] Neural anomaly detector (trained on real vs synthesized speech datasets)
- [ ] Time-stretch invariant watermarking
- [ ] REST API server for enterprise integration
- [ ] Browser-based demo (WebAudio API)
- [ ] Blockchain-anchored watermark registry

---

## License

This project is released for academic and research purposes. All rights reserved by the team.

---

<div align="center">

**Built with ❤️ to protect the integrity of human voice in the age of AI**

</div>
