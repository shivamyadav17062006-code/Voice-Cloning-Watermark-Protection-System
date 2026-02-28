import numpy as np
import librosa
import soundfile as sf
import subprocess
import tempfile
import os

SECRET_KEY          = [42, 137, 256, 389, 512, 701, 1024, 1337, 2048, 2500]
WATERMARK_STRENGTH  = 60
DETECTION_THRESHOLD = 1.4
N_MFCC             = 40
VOICE_MATCH_THRESH = 0.78

# Spaced-key configuration: when USE_SPACED_KEYS is True, watermark/detection
# will use generated bins at regular intervals instead of the static SECRET_KEY.
USE_SPACED_KEYS = False
KEY_OFFSET = 42       # starting bin index
KEY_SPACING = 200     # bins between keys
KEY_COUNT = 10        # how many keys to generate


def build_spaced_keys(offset=KEY_OFFSET, spacing=KEY_SPACING, count=KEY_COUNT):
    """Return a list of frequency-bin indices spaced across the spectrum."""
    return [offset + i * spacing for i in range(count)]

# Frame-based watermark settings (more robust to trimming)
USE_FRAME_WM = True
FRAME_N_FFT = 2048
FRAME_HOP = 512
# Minimum number of frames that should contain the watermark bins to consider it present
FRAME_MIN_FRAMES_REQUIRED = 2


def convert_to_wav(input_path):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out = tmp.name
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-f", "wav", out],
            capture_output=True, timeout=30
        )
        if r.returncode == 0 and os.path.getsize(out) > 0:
            return out
        os.unlink(out)
        return input_path
    except Exception:
        try: os.unlink(out)
        except: pass
        return input_path


def safe_load(audio_path, sr_target=None):
    temp_path = None
    converted = convert_to_wav(audio_path)
    if converted != audio_path:
        temp_path = converted
    try:
        audio, sr = librosa.load(converted, sr=sr_target, mono=True)
        return audio, sr, temp_path
    except Exception:
        audio, sr = librosa.load(audio_path, sr=sr_target, mono=True)
        return audio, sr, None


def cleanup(p):
    if p:
        try: os.unlink(p)
        except: pass


def embed_watermark(input_path, output_path):
    tp = None
    try:
        audio, sr, tp = safe_load(input_path)
        if USE_FRAME_WM:
            # frame-based STFT embedding: add magnitude to selected frequency bins across frames
            S = librosa.stft(audio, n_fft=FRAME_N_FFT, hop_length=FRAME_HOP)
            mag, phase = np.abs(S), np.angle(S)
            bins = build_spaced_keys() if USE_SPACED_KEYS else SECRET_KEY
            max_bin = mag.shape[0]
            for b in bins:
                if b < max_bin:
                    # boost magnitude across all frames for that bin
                    mag[b, :] += WATERMARK_STRENGTH
            S2 = mag * np.exp(1j * phase)
            wm = librosa.istft(S2, hop_length=FRAME_HOP, length=len(audio))
            wm = wm.astype(np.float32)
        else:
            fft = np.fft.fft(audio)
            bins = build_spaced_keys() if USE_SPACED_KEYS else SECRET_KEY
            for b in bins:
                if b < len(fft):
                    fft[b]  += WATERMARK_STRENGTH
                    fft[-b] += WATERMARK_STRENGTH
            wm = np.fft.ifft(fft).real.astype(np.float32)
        mx = np.max(np.abs(wm))
        if mx > 1.0: wm /= mx
        sf.write(output_path, wm, sr)
        return {"success": True, "sample_rate": sr, "duration_seconds": round(len(audio)/sr, 2)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        cleanup(tp)


def detect_watermark(audio_path):
    tp = None
    try:
        audio, sr, tp = safe_load(audio_path)
        dur = round(len(audio)/sr, 2)
        if USE_FRAME_WM:
            # STFT-based detection: compute per-frame ratios for each key bin and aggregate
            S = librosa.stft(audio, n_fft=FRAME_N_FFT, hop_length=FRAME_HOP)
            mag = np.abs(S)
            bins = build_spaced_keys() if USE_SPACED_KEYS else SECRET_KEY
            frame_scores = []
            for b in bins:
                if b < mag.shape[0]:
                    # for each frame compute ratio of bin to local neighbors
                    lo = max(0, b-15)
                    hi = min(mag.shape[0], b+15)
                    # neighbors exclude the bin itself
                    nb = np.concatenate([mag[lo:b, :], mag[b+1:hi, :]]) if hi-lo > 1 else None
                    if nb is None or nb.size == 0:
                        continue
                    # compute ratio per frame
                    denom = np.mean(nb, axis=0) + 1e-10
                    ratios = mag[b, :] / denom
                    # measure how many frames exceed threshold-like behavior
                    frame_scores.append(ratios)
            if not frame_scores:
                avg = 0.0
            else:
                # stack and take median across bins for each frame
                stack = np.vstack(frame_scores)
                per_frame = np.median(stack, axis=0)
                # consider frames where the median ratio is high
                strong_frames = per_frame >= DETECTION_THRESHOLD
                # compute a score based on fraction of strong frames and mean ratio
                frac = float(np.sum(strong_frames)) / max(1, per_frame.size)
                avg = float(np.mean(per_frame)) * (0.5 + 0.5 * frac)
            score_val = round(float(avg), 3)
            if avg >= DETECTION_THRESHOLD or (per_frame.size if 'per_frame' in locals() else 0) > 0 and float(np.sum(per_frame >= DETECTION_THRESHOLD)) >= FRAME_MIN_FRAMES_REQUIRED:
                conf = min(99, int(40 + (avg - DETECTION_THRESHOLD) * 35))
                return {"verdict":"WATERMARK DETECTED","authenticated":True,"confidence":conf,
                        "score":score_val,"risk":"LOW","risk_label":"Original Protected Audio",
                        "color":"green","duration_seconds":dur,"sample_rate":sr}
            else:
                conf = min(99, int(40 + (DETECTION_THRESHOLD - avg) * 35))
                return {"verdict":"NO WATERMARK / TAMPERED","authenticated":False,"confidence":conf,
                        "score":score_val,"risk":"HIGH","risk_label":"Possible Deepfake or Tampered Audio",
                        "color":"red","duration_seconds":dur,"sample_rate":sr}
        else:
            fft = np.fft.fft(audio)
            mag = np.abs(fft)
            scores = []
            bins = build_spaced_keys() if USE_SPACED_KEYS else SECRET_KEY
            for b in bins:
                if b < len(mag):
                    t = mag[b]
                    lo, hi = max(0, b-15), min(len(mag), b+15)
                    nb = np.concatenate([mag[lo:b], mag[b+1:hi]])
                    scores.append(t / (np.mean(nb) + 1e-10))
            avg = float(np.mean(scores))
            if avg >= DETECTION_THRESHOLD:
                conf = min(99, int(40+(avg-DETECTION_THRESHOLD)*35))
                return {"verdict":"WATERMARK DETECTED","authenticated":True,"confidence":conf,
                        "score":round(avg,3),"risk":"LOW","risk_label":"Original Protected Audio",
                        "color":"green","duration_seconds":dur,"sample_rate":sr}
            else:
                conf = min(99, int(40+(DETECTION_THRESHOLD-avg)*35))
                return {"verdict":"NO WATERMARK / TAMPERED","authenticated":False,"confidence":conf,
                        "score":round(avg,3),"risk":"HIGH","risk_label":"Possible Deepfake or Tampered Audio",
                        "color":"red","duration_seconds":dur,"sample_rate":sr}
    except Exception as e:
        return {"verdict":"ANALYSIS FAILED","authenticated":False,"confidence":0,"score":0,
                "risk":"UNKNOWN","risk_label":f"Error: {str(e)}","color":"yellow","error":str(e)}
    finally:
        cleanup(tp)


def extract_voice_fingerprint(audio_path):
    tp = None
    try:
        audio, sr, tp = safe_load(audio_path, sr_target=16000)
        trimmed, _ = librosa.effects.trim(audio, top_db=20)
        if len(trimmed) < sr * 0.5: trimmed = audio
        mfccs = librosa.feature.mfcc(y=trimmed, sr=16000, n_mfcc=N_MFCC)
        fp = np.concatenate([np.mean(mfccs, axis=1), np.std(mfccs, axis=1)])
        return fp.astype(np.float64)
    finally:
        cleanup(tp)


def cosine_similarity(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0: return 0.0
    return float(np.dot(a, b) / (na * nb))


def compare_voices(stored_fp, login_path):
    try:
        login_fp = extract_voice_fingerprint(login_path)
        if len(stored_fp) != len(login_fp):
            mn = min(len(stored_fp), len(login_fp))
            stored_fp, login_fp = stored_fp[:mn], login_fp[:mn]
        sim = cosine_similarity(stored_fp, login_fp)
        matched = sim >= VOICE_MATCH_THRESH
        conf = int(max(0, min(100, (sim - 0.5) / 0.5 * 100)))
        return {"matched":matched,"similarity":round(float(sim),4),"confidence":conf,
                "verdict":"VOICE VERIFIED ✓" if matched else "VOICE NOT RECOGNISED ✗",
                "color":"green" if matched else "red"}
    except Exception as e:
        return {"matched":False,"similarity":0.0,"confidence":0,
                "verdict":"ANALYSIS FAILED","color":"yellow","error":str(e)}
