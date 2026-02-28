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
        fft = np.fft.fft(audio)
        for b in SECRET_KEY:
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
        fft = np.fft.fft(audio)
        mag = np.abs(fft)
        scores = []
        for b in SECRET_KEY:
            if b < len(mag):
                t = mag[b]
                lo, hi = max(0, b-15), min(len(mag), b+15)
                nb = np.concatenate([mag[lo:b], mag[b+1:hi]])
                scores.append(t / (np.mean(nb) + 1e-10))
        avg = float(np.mean(scores))
        dur = round(len(audio)/sr, 2)
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
