"""
VoiceGuard v2.0 — Flask Backend
Run: python3 backend/app.py
Open: http://localhost:8080
"""

import os
import time
import secrets
import traceback
import subprocess
import sqlite3

import numpy as np
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

from watermark import (
    embed_watermark,
    detect_watermark,
    extract_voice_fingerprint,
    compare_voices,
)

# ── App Setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR   = os.path.join(BASE_DIR, "..", "frontend")
UPLOAD_FOLDER  = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER  = os.path.join(BASE_DIR, "outputs")
PROFILE_FOLDER = os.path.join(BASE_DIR, "profiles")
DB_PATH        = os.path.join(BASE_DIR, "voiceguard.db")

ALLOWED_EXTENSIONS = {"wav", "mp3", "ogg", "flac", "m4a", "webm", "opus"}

for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, PROFILE_FOLDER]:
    os.makedirs(folder, exist_ok=True)


# ── Database ───────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            display_name TEXT,
            voice_profile BLOB,
            profile_audio TEXT,
            fp_version   INTEGER DEFAULT 2,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            token      TEXT UNIQUE NOT NULL,
            user_id    INTEGER,
            username   TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER,
            filename         TEXT,
            stored_filename  TEXT,
            verdict          TEXT,
            confidence       REAL,
            is_authenticated INTEGER,
            risk             TEXT,
            score            REAL,
            duration         REAL,
            timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS protected_files (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER,
            original_filename   TEXT,
            watermarked_filename TEXT,
            embedded_at         DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_from_token(token: str):
    """Return {user_id, username} dict or None."""
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT user_id, username FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_uploaded_audio(file, prefix: str = "audio") -> tuple[str, str]:
    """Save an uploaded audio file and return (absolute_path, safe_filename)."""
    raw_name = file.filename or "audio.webm"
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else "webm"
    if ext not in ALLOWED_EXTENSIONS:
        ext = "webm"
    safe_name = f"{prefix}_{int(time.time())}_{secrets.token_hex(4)}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(path)
    return path, safe_name


# ── Static File Serving ────────────────────────────────────────────────────────

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/login.html")
def serve_login_page():
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ── Health Check ───────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        ffmpeg_status = "available"
    except Exception:
        ffmpeg_status = "NOT INSTALLED — run: sudo apt install ffmpeg"
    return jsonify({
        "status":  "VoiceGuard is running",
        "version": "2.0.0",
        "ffmpeg":  ffmpeg_status
    })


# ── Auth: Register ─────────────────────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    username     = request.form.get("username", "").strip().lower()
    display_name = request.form.get("display_name", "").strip() or username

    if not username or len(username) < 2:
        return jsonify({"error": "Username must be at least 2 characters"}), 400

    path, safe_name = save_uploaded_audio(request.files["audio"], f"profile_{username}")

    try:
        fp = extract_voice_fingerprint(path)
        fp_bytes = fp.astype(np.float64).tobytes()
    except Exception as exc:
        traceback.print_exc()
        return jsonify({
            "error": f"Could not process voice: {str(exc)}. Try recording in a quieter environment."
        }), 500

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, display_name, voice_profile, profile_audio, fp_version) VALUES (?, ?, ?, ?, ?)",
            (username, display_name, fp_bytes, safe_name, 2)
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id, username) VALUES (?, ?, ?)",
            (token, user_id, username)
        )
        conn.commit()
        conn.close()
        return jsonify({
            "success":      True,
            "message":      f"Welcome, {display_name}! Your voice is your password.",
            "token":        token,
            "username":     username,
            "display_name": display_name
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Username already taken. Please choose another."}), 409
    except Exception as exc:
        conn.close()
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


# ── Auth: Login ────────────────────────────────────────────────────────────────

@app.route("/login", methods=["POST"])
def login():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    username = request.form.get("username", "").strip().lower()
    if not username:
        return jsonify({"error": "Username is required"}), 400

    path, _ = save_uploaded_audio(request.files["audio"], f"login_{username}")

    conn = get_db()
    user = conn.execute(
        "SELECT id, username, display_name, voice_profile FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()

    if not user:
        try: os.remove(path)
        except: pass
        return jsonify({"error": "User not found. Please register first."}), 404

    stored_fp = np.frombuffer(user["voice_profile"], dtype=np.float64)

    try:
        result = compare_voices(stored_fp, path)
    except Exception as exc:
        traceback.print_exc()
        try: os.remove(path)
        except: pass
        return jsonify({"error": f"Voice comparison failed: {str(exc)}"}), 500

    try: os.remove(path)
    except: pass

    if result["matched"]:
        token = secrets.token_hex(32)
        conn = get_db()
        conn.execute(
            "INSERT INTO sessions (token, user_id, username) VALUES (?, ?, ?)",
            (token, user["id"], username)
        )
        conn.commit()
        conn.close()
        return jsonify({
            **result,
            "token":        token,
            "username":     username,
            "display_name": user["display_name"]
        })

    return jsonify({
        **result,
        "error": (
            f"Voice mismatch (similarity: {result['similarity']:.2f}, "
            f"required ≥ 0.78). Please try again clearly."
        )
    }), 401


# ── Auth: Logout ───────────────────────────────────────────────────────────────

@app.route("/logout", methods=["POST"])
def logout():
    token = request.headers.get("X-Token")
    if token:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return jsonify({"success": True})


# ── Profile ────────────────────────────────────────────────────────────────────

@app.route("/me")
def me():
    user = get_user_from_token(request.headers.get("X-Token"))
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    conn = get_db()
    row = conn.execute(
        "SELECT display_name, created_at FROM users WHERE id = ?", (user["user_id"],)
    ).fetchone()
    conn.close()
    return jsonify({
        "username":     user["username"],
        "display_name": row["display_name"] if row else user["username"],
        "created_at":   row["created_at"] if row else None
    })


# ── Stats ──────────────────────────────────────────────────────────────────────

@app.route("/stats")
def stats():
    user = get_user_from_token(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None
    conn = get_db()
    if uid:
        total     = conn.execute("SELECT COUNT(*) FROM scans WHERE user_id = ?", (uid,)).fetchone()[0]
        flagged   = conn.execute("SELECT COUNT(*) FROM scans WHERE user_id = ? AND is_authenticated = 0", (uid,)).fetchone()[0]
        auth      = conn.execute("SELECT COUNT(*) FROM scans WHERE user_id = ? AND is_authenticated = 1", (uid,)).fetchone()[0]
        protected = conn.execute("SELECT COUNT(*) FROM protected_files WHERE user_id = ?", (uid,)).fetchone()[0]
    else:
        total     = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        flagged   = conn.execute("SELECT COUNT(*) FROM scans WHERE is_authenticated = 0").fetchone()[0]
        auth      = conn.execute("SELECT COUNT(*) FROM scans WHERE is_authenticated = 1").fetchone()[0]
        protected = conn.execute("SELECT COUNT(*) FROM protected_files").fetchone()[0]
    conn.close()
    return jsonify({
        "total_scans":   total,
        "flagged":       flagged,
        "authenticated": auth,
        "protected":     protected
    })


# ── Detect Watermark ───────────────────────────────────────────────────────────

@app.route("/detect", methods=["POST"])
def detect():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400

    user = get_user_from_token(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None

    file = request.files["audio"]
    path, safe_name = save_uploaded_audio(file, "detect")

    result   = detect_watermark(path)
    filename = file.filename or "recorded_audio"
    result["filename"] = filename

    conn = get_db()
    conn.execute(
        """INSERT INTO scans
           (user_id, filename, stored_filename, verdict, confidence,
            is_authenticated, risk, score, duration)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (uid, filename, safe_name, result["verdict"], result["confidence"],
         1 if result["authenticated"] else 0, result["risk"],
         result["score"], result.get("duration_seconds"))
    )
    conn.commit()
    scan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    result["scan_id"] = scan_id
    return jsonify(result)


# ── Embed Watermark ────────────────────────────────────────────────────────────

@app.route("/embed", methods=["POST"])
def embed():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400

    user = get_user_from_token(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None

    file  = request.files["audio"]
    fname = file.filename or "audio.wav"
    path, _ = save_uploaded_audio(file, "embed")

    out_name = "watermarked_" + fname.rsplit(".", 1)[0] + ".wav"
    out_path = os.path.join(OUTPUT_FOLDER, out_name)

    result = embed_watermark(path, out_path)
    if not result["success"]:
        return jsonify({"error": result.get("error", "Embedding failed")}), 500

    conn = get_db()
    conn.execute(
        "INSERT INTO protected_files (user_id, original_filename, watermarked_filename) VALUES (?, ?, ?)",
        (uid, fname, out_name)
    )
    conn.commit()
    conn.close()

    try: os.remove(path)
    except: pass

    return send_file(
        out_path,
        as_attachment=True,
        download_name=out_name,
        mimetype="audio/wav"
    )


# ── Serve Scan Audio ───────────────────────────────────────────────────────────

@app.route("/audio/<int:scan_id>")
def serve_audio(scan_id):
    conn = get_db()
    row = conn.execute(
        "SELECT stored_filename FROM scans WHERE id = ?", (scan_id,)
    ).fetchone()
    conn.close()

    if not row or not row["stored_filename"]:
        return jsonify({"error": "Not found"}), 404

    file_path = os.path.join(UPLOAD_FOLDER, row["stored_filename"])
    if not os.path.exists(file_path):
        return jsonify({"error": "File no longer available"}), 404

    ext = row["stored_filename"].rsplit(".", 1)[-1].lower()
    mime_map = {
        "wav":  "audio/wav",
        "mp3":  "audio/mpeg",
        "ogg":  "audio/ogg",
        "webm": "audio/webm",
        "opus": "audio/ogg",
        "flac": "audio/flac",
        "m4a":  "audio/mp4"
    }
    return send_file(file_path, mimetype=mime_map.get(ext, "audio/wav"))


# ── History ────────────────────────────────────────────────────────────────────

@app.route("/history")
def history():
    user = get_user_from_token(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None
    conn = get_db()
    if uid:
        rows = conn.execute(
            """SELECT id, filename, stored_filename, verdict, confidence,
                      risk, duration, timestamp
               FROM scans WHERE user_id = ?
               ORDER BY timestamp DESC LIMIT 20""",
            (uid,)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, filename, stored_filename, verdict, confidence,
                      risk, duration, timestamp
               FROM scans ORDER BY timestamp DESC LIMIT 20"""
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print()
    print("🔐  VoiceGuard v2.0 — Starting up")
    print("━" * 42)
    print("👉  Dashboard : http://localhost:8080")
    print("👉  Login     : http://localhost:8080/login.html")
    print("━" * 42)
    print()
    app.run(debug=False, port=8080, host="0.0.0.0")
