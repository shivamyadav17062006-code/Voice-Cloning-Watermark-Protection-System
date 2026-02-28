from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from watermark import embed_watermark, detect_watermark, extract_voice_fingerprint, compare_voices
import sqlite3, numpy as np, os, time, secrets, traceback, subprocess

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER  = "uploads"
OUTPUT_FOLDER  = "outputs"
PROFILE_FOLDER = "profiles"
DB_PATH        = "voiceguard.db"

for f in [UPLOAD_FOLDER, OUTPUT_FOLDER, PROFILE_FOLDER]:
    os.makedirs(f, exist_ok=True)

ALLOWED = {"wav","mp3","ogg","flac","m4a","webm","opus"}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        display_name TEXT,
        voice_profile BLOB,
        profile_audio TEXT,
        fp_version INTEGER DEFAULT 2,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        username TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS scans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        stored_filename TEXT,
        verdict TEXT,
        confidence REAL,
        is_authenticated INTEGER,
        risk TEXT,
        score REAL,
        duration REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS protected_files(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        original_filename TEXT,
        watermarked_filename TEXT,
        embedded_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit(); conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user(token):
    if not token: return None
    conn = get_db()
    row = conn.execute("SELECT user_id,username FROM sessions WHERE token=?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None

def save_audio(file, prefix="audio"):
    raw = file.filename or "audio.webm"
    ext = raw.rsplit(".",1)[-1].lower() if "." in raw else "webm"
    if ext not in ALLOWED: ext = "webm"
    name = f"{prefix}_{int(time.time())}_{secrets.token_hex(4)}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, name)
    file.save(path)
    return path, name

@app.route("/health")
def health():
    try:
        subprocess.run(["ffmpeg","-version"], capture_output=True, timeout=3)
        ffmpeg = "available ✅"
    except:
        ffmpeg = "NOT INSTALLED ❌ — run: brew install ffmpeg"
    return jsonify({"status":"VoiceGuard is running","version":"2.0.0","ffmpeg":ffmpeg})

@app.route("/register", methods=["POST"])
def register():
    print("📥 /register called")
    if "audio" not in request.files:
        return jsonify({"error":"No audio file provided"}), 400
    username = request.form.get("username","").strip().lower()
    display  = request.form.get("display_name","").strip() or username
    if not username or len(username) < 2:
        return jsonify({"error":"Username must be at least 2 characters"}), 400
    file = request.files["audio"]
    path, safe = save_audio(file, f"profile_{username}")
    print(f"🎵 Saved {path} ({os.path.getsize(path)} bytes)")
    try:
        fp = extract_voice_fingerprint(path)
        fp_bytes = fp.astype(np.float64).tobytes()
        print(f"✅ Fingerprint: {fp.shape}")
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":f"Could not process voice: {str(e)}. Try recording in a quieter spot."}), 500
    conn = get_db()
    try:
        conn.execute("INSERT INTO users(username,display_name,voice_profile,profile_audio,fp_version) VALUES(?,?,?,?,?)",
                     (username,display,fp_bytes,safe,2))
        conn.commit()
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        token = secrets.token_hex(32)
        conn.execute("INSERT INTO sessions(token,user_id,username) VALUES(?,?,?)",(token,uid,username))
        conn.commit(); conn.close()
        print(f"✅ Registered: {username}")
        return jsonify({"success":True,"message":f"Welcome, {display}! Your voice is your password.",
                        "token":token,"username":username,"display_name":display})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error":"Username already taken."}), 409
    except Exception as e:
        conn.close(); traceback.print_exc()
        return jsonify({"error":str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    print("📥 /login called")
    if "audio" not in request.files:
        return jsonify({"error":"No audio file provided"}), 400
    username = request.form.get("username","").strip().lower()
    if not username: return jsonify({"error":"Username required"}), 400
    file = request.files["audio"]
    path, _ = save_audio(file, f"login_{username}")
    print(f"🎵 Login audio: {path} ({os.path.getsize(path)} bytes)")
    conn = get_db()
    user = conn.execute("SELECT id,username,display_name,voice_profile FROM users WHERE username=?",(username,)).fetchone()
    conn.close()
    if not user:
        try: os.remove(path)
        except: pass
        return jsonify({"error":"User not found. Please register first."}), 404
    stored_fp = np.frombuffer(user["voice_profile"], dtype=np.float64)
    try:
        result = compare_voices(stored_fp, path)
        print(f"🔍 Similarity: {result['similarity']}, matched: {result['matched']}")
    except Exception as e:
        traceback.print_exc()
        try: os.remove(path)
        except: pass
        return jsonify({"error":f"Voice comparison failed: {str(e)}"}), 500
    try: os.remove(path)
    except: pass
    if result["matched"]:
        token = secrets.token_hex(32)
        conn = get_db()
        conn.execute("INSERT INTO sessions(token,user_id,username) VALUES(?,?,?)",(token,user["id"],username))
        conn.commit(); conn.close()
        return jsonify({**result,"token":token,"username":username,"display_name":user["display_name"]})
    return jsonify({**result,"error":f"Voice mismatch (score: {result['similarity']:.2f}, need ≥0.78). Try again clearly."}), 401

@app.route("/logout", methods=["POST"])
def logout():
    t = request.headers.get("X-Token")
    if t:
        conn = get_db(); conn.execute("DELETE FROM sessions WHERE token=?",(t,)); conn.commit(); conn.close()
    return jsonify({"success":True})

@app.route("/me")
def me():
    user = get_user(request.headers.get("X-Token"))
    if not user: return jsonify({"error":"Not authenticated"}), 401
    conn = get_db()
    u = conn.execute("SELECT display_name,created_at FROM users WHERE id=?",(user["user_id"],)).fetchone()
    conn.close()
    return jsonify({"username":user["username"],"display_name":u["display_name"] if u else user["username"],"created_at":u["created_at"] if u else None})

@app.route("/stats")
def stats():
    user = get_user(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None
    conn = get_db()
    if uid:
        t = conn.execute("SELECT COUNT(*) FROM scans WHERE user_id=?",(uid,)).fetchone()[0]
        f = conn.execute("SELECT COUNT(*) FROM scans WHERE user_id=? AND is_authenticated=0",(uid,)).fetchone()[0]
        a = conn.execute("SELECT COUNT(*) FROM scans WHERE user_id=? AND is_authenticated=1",(uid,)).fetchone()[0]
        p = conn.execute("SELECT COUNT(*) FROM protected_files WHERE user_id=?",(uid,)).fetchone()[0]
    else:
        t = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        f = conn.execute("SELECT COUNT(*) FROM scans WHERE is_authenticated=0").fetchone()[0]
        a = conn.execute("SELECT COUNT(*) FROM scans WHERE is_authenticated=1").fetchone()[0]
        p = conn.execute("SELECT COUNT(*) FROM protected_files").fetchone()[0]
    conn.close()
    return jsonify({"total_scans":t,"flagged":f,"authenticated":a,"protected":p})

@app.route("/detect", methods=["POST"])
def detect():
    if "audio" not in request.files: return jsonify({"error":"No audio"}), 400
    user = get_user(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None
    file = request.files["audio"]
    path, safe = save_audio(file, "detect")
    result = detect_watermark(path)
    result["filename"] = file.filename or "recorded_audio"
    conn = get_db()
    conn.execute("INSERT INTO scans(user_id,filename,stored_filename,verdict,confidence,is_authenticated,risk,score,duration) VALUES(?,?,?,?,?,?,?,?,?)",
                 (uid,result["filename"],safe,result["verdict"],result["confidence"],
                  1 if result["authenticated"] else 0,result["risk"],result["score"],result.get("duration_seconds")))
    conn.commit()
    sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    result["scan_id"] = sid
    return jsonify(result)

@app.route("/embed", methods=["POST"])
def embed():
    if "audio" not in request.files: return jsonify({"error":"No audio"}), 400
    user = get_user(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None
    file = request.files["audio"]
    fname = file.filename or "audio.wav"
    path, _ = save_audio(file, "embed")
    oname = "watermarked_" + fname.rsplit(".",1)[0] + ".wav"
    opath = os.path.join(OUTPUT_FOLDER, oname)
    result = embed_watermark(path, opath)
    if not result["success"]: return jsonify({"error":result.get("error","Embedding failed")}), 500
    conn = get_db()
    conn.execute("INSERT INTO protected_files(user_id,original_filename,watermarked_filename) VALUES(?,?,?)",(uid,fname,oname))
    conn.commit(); conn.close()
    try: os.remove(path)
    except: pass
    return send_file(opath, as_attachment=True, download_name=oname, mimetype="audio/wav")

@app.route("/audio/<int:sid>")
def serve_audio(sid):
    conn = get_db()
    row = conn.execute("SELECT stored_filename FROM scans WHERE id=?",(sid,)).fetchone()
    conn.close()
    if not row or not row["stored_filename"]: return jsonify({"error":"Not found"}), 404
    p = os.path.join(UPLOAD_FOLDER, row["stored_filename"])
    if not os.path.exists(p): return jsonify({"error":"File missing"}), 404
    ext = row["stored_filename"].rsplit(".",1)[-1].lower()
    mime = {"wav":"audio/wav","mp3":"audio/mpeg","ogg":"audio/ogg","webm":"audio/webm","opus":"audio/ogg"}.get(ext,"audio/wav")
    return send_file(p, mimetype=mime)

@app.route("/history")
def history():
    user = get_user(request.headers.get("X-Token"))
    uid  = user["user_id"] if user else None
    conn = get_db()
    if uid:
        rows = conn.execute("SELECT id,filename,stored_filename,verdict,confidence,risk,duration,timestamp FROM scans WHERE user_id=? ORDER BY timestamp DESC LIMIT 20",(uid,)).fetchall()
    else:
        rows = conn.execute("SELECT id,filename,stored_filename,verdict,confidence,risk,duration,timestamp FROM scans ORDER BY timestamp DESC LIMIT 20").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    init_db()
    print("🔐 VoiceGuard v2.0 → http://localhost:8080")
    print("━"*45)
    app.run(debug=True, port=8080)
