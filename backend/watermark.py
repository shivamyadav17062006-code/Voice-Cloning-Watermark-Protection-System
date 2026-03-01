"""
VoiceGuard — FFT Watermarking & Voice Fingerprint Module
"""

import numpy as np
import librosa
import soundfile as sf
import subprocess
import tempfile
import os

# ── Constants ──────────────────────────────────────────────────────────────────
SECRET_KEY          = [42, 137, 256, 389, 512, 701, 1024, 1337, 2048, 2500]
WATERMARK_STRENGTH  = 60
DETECTION_THRESHOLD = 1.4
N_MFCC              = 40
VOICE_MATCH_THRESH  = 0.78


# ── Audio Loading Utilities ────────────────────────────────────────────────────

def convert_to_wav(input_path: str) -> str:
    """Convert any audio file to a temporary 16kHz mono WAV using ffmpeg."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out = tmp.name
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", input_path,
             "-ar", "16000", "-ac", "1", "-f", "wav", out],
            capture_output=True, timeout=30
        )
        if result.returncode == 0 and os.path.getsize(out) > 0:
            return out
        # ffmpeg failed — clean up and return original
        try: os.unlink(out)
        except: pass
        return input_path
    except Exception:
        try: os.unlink(out)
        except: pass
        return input_path


def safe_load(audio_path: str, sr_target=None):
    """Load audio, converting to WAV first if needed. Returns (audio, sr, tmp_path)."""
    temp_path = None
    converted = convert_to_wav(audio_path)
    if converted != audio_path:
        temp_path = converted
    try:
        audio, sr = librosa.load(converted, sr=sr_target, mono=True)
        return audio, sr, temp_path
    except Exception:
        # Fall back to original file
        audio, sr = librosa.load(audio_path, sr=sr_target, mono=True)
        return audio, sr, None


def cleanup(path: str):
    """Remove a temporary file, ignoring errors."""
    if path:
        try: os.unlink(path)
        except: pass


# ── Watermark Embedding ────────────────────────────────────────────────────────

def embed_watermark(input_path: str, output_path: str) -> dict:
    """
    Embed an invisible FFT watermark into the audio file.

    Returns:
        dict with keys: success, sample_rate, duration_seconds (or error)
    """
    temp_path = None
    try:
        audio, sr, temp_path = safe_load(input_path)

        # Work in frequency domain
        fft = np.fft.fft(audio)
        for bin_idx in SECRET_KEY:
            if bin_idx < len(fft):
                fft[bin_idx]  += WATERMARK_STRENGTH
                fft[-bin_idx] += WATERMARK_STRENGTH  # Maintain conjugate symmetry

        # Convert back to time domain
        watermarked = np.fft.ifft(fft).real.astype(np.float32)

        # Normalise to prevent clipping
        peak = np.max(np.abs(watermarked))
        if peak > 1.0:
            watermarked /= peak

        sf.write(output_path, watermarked, sr)
        return {
            "success": True,
            "sample_rate": int(sr),
            "duration_seconds": round(len(audio) / sr, 2)
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        cleanup(temp_path)


# ── Watermark Detection ────────────────────────────────────────────────────────

def detect_watermark(audio_path: str) -> dict:
    """
    Detect whether the audio contains a valid VoiceGuard watermark.

    Returns:
        dict with verdict, authenticated, confidence, score, risk, color, etc.
    """
    temp_path = None
    try:
        audio, sr, temp_path = safe_load(audio_path)
        fft = np.fft.fft(audio)
        magnitudes = np.abs(fft)

        scores = []
        for bin_idx in SECRET_KEY:
            if bin_idx < len(magnitudes):
                target_mag = magnitudes[bin_idx]
                lo = max(0, bin_idx - 15)
                hi = min(len(magnitudes), bin_idx + 15)
                neighbours = np.concatenate([magnitudes[lo:bin_idx], magnitudes[bin_idx + 1:hi]])
                ratio = target_mag / (np.mean(neighbours) + 1e-10)
                scores.append(ratio)

        avg_score = float(np.mean(scores)) if scores else 0.0
        duration  = round(len(audio) / sr, 2)

        if avg_score >= DETECTION_THRESHOLD:
            confidence = min(99, int(40 + (avg_score - DETECTION_THRESHOLD) * 35))
            return {
                "verdict":          "WATERMARK DETECTED",
                "authenticated":    True,
                "confidence":       confidence,
                "score":            round(avg_score, 3),
                "risk":             "LOW",
                "risk_label":       "Original Protected Audio",
                "color":            "green",
                "duration_seconds": duration,
                "sample_rate":      int(sr)
            }
        else:
            confidence = min(99, int(40 + (DETECTION_THRESHOLD - avg_score) * 35))
            return {
                "verdict":          "NO WATERMARK / TAMPERED",
                "authenticated":    False,
                "confidence":       confidence,
                "score":            round(avg_score, 3),
                "risk":             "HIGH",
                "risk_label":       "Possible Deepfake or Tampered Audio",
                "color":            "red",
                "duration_seconds": duration,
                "sample_rate":      int(sr)
            }
    except Exception as exc:
        return {
            "verdict":       "ANALYSIS FAILED",
            "authenticated": False,
            "confidence":    0,
            "score":         0,
            "risk":          "UNKNOWN",
            "risk_label":    f"Error: {str(exc)}",
            "color":         "yellow",
            "error":         str(exc)
        }
    finally:
        cleanup(temp_path)


# ── Voice Fingerprinting ───────────────────────────────────────────────────────

def extract_voice_fingerprint(audio_path: str) -> np.ndarray:
    """
    Extract an MFCC-based voice fingerprint from audio.

    Returns:
        numpy array of shape (2 * N_MFCC,) — mean + std of MFCCs
    """
    temp_path = None
    try:
        audio, sr, temp_path = safe_load(audio_path, sr_target=16000)

        # Remove silence
        trimmed, _ = librosa.effects.trim(audio, top_db=20)
        if len(trimmed) < sr * 0.5:
            trimmed = audio  # too short after trim, use original

        mfccs = librosa.feature.mfcc(y=trimmed, sr=16000, n_mfcc=N_MFCC)
        fingerprint = np.concatenate([np.mean(mfccs, axis=1), np.std(mfccs, axis=1)])
        return fingerprint.astype(np.float64)
    finally:
        cleanup(temp_path)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def compare_voices(stored_fp: np.ndarray, login_audio_path: str) -> dict:
    """
    Compare a stored voice fingerprint with a new audio recording.

    Returns:
        dict with matched, similarity, confidence, verdict, color
    """
    try:
        login_fp = extract_voice_fingerprint(login_audio_path)

        # Align lengths in case of minor dimension mismatch
        if len(stored_fp) != len(login_fp):
            mn = min(len(stored_fp), len(login_fp))
            stored_fp = stored_fp[:mn]
            login_fp  = login_fp[:mn]

        similarity = cosine_similarity(stored_fp, login_fp)
        matched    = similarity >= VOICE_MATCH_THRESH
        # Scale confidence: 0.5 sim → 0%, 1.0 sim → 100%
        confidence = int(max(0, min(100, (similarity - 0.5) / 0.5 * 100)))

        return {
            "matched":    matched,
            "similarity": round(float(similarity), 4),
            "confidence": confidence,
            "verdict":    "VOICE VERIFIED ✓" if matched else "VOICE NOT RECOGNISED ✗",
            "color":      "green" if matched else "red"
        }
    except Exception as exc:
        return {
            "matched":    False,
            "similarity": 0.0,
            "confidence": 0,
            "verdict":    "ANALYSIS FAILED",
            "color":      "yellow",
            "error":      str(exc)
        }
