# 🔐 VoiceGuard — AI Voice Clone Detection & Watermarking System

> **Hackathon Project | Overclock 24**  
> A resilient, secure audio authentication framework capable of protecting digital voice integrity in an AI-driven world.

---

## 📌 Problem Statement

AI-based voice synthesis has made it possible to generate highly realistic cloned audio. Deepfake audio is being used to:
- Manipulate public opinion
- Commit financial fraud
- Impersonate individuals in sensitive contexts

There is currently **no widely adopted system** that can embed secure watermarks into audio AND detect tampering or synthetic generation reliably.

---

## ✅ Our Solution

**VoiceGuard** is a two-in-one audio authentication system that:

1. **Embeds** inaudible, secure watermarks into original audio using **FFT (Fast Fourier Transform)** frequency-domain techniques
2. **Detects** whether any audio file has been tampered with, cloned, or lacks a valid watermark
3. **Generates** a downloadable forensic report for legal and evidentiary use

---

## 🎯 Key Features

| Feature | Description |
|--------|-------------|
| 🔐 FFT Watermarking | Embeds secret signatures in inaudible frequency bins |
| 🔍 Tamper Detection | Detects missing or altered watermarks with confidence score |
| 📄 Forensic Report | Downloadable report with verdict, confidence %, and timestamp |
| 📊 Live Dashboard | Real-time stats — files scanned, threats detected, files protected |
| 🌐 REST API | Simple Flask API for easy integration into any platform |
| 🎨 Clean UI | Dark-themed, responsive frontend with drag & drop upload |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Signal Processing | NumPy, SciPy (FFT) |
| Audio Handling | Librosa, SoundFile |
| Backend | Python, Flask, Flask-CORS |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Deployment | Railway.app / Render.com |

---

## 📁 Project Structure

```
voiceguard/
├── backend/
│   ├── app.py              # Flask API server
│   ├── watermark.py        # Core FFT watermark logic
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── index.html          # Main UI
│   ├── style.css           # Styling
│   └── script.js           # Frontend logic
├── test_audio/             # Sample audio files for demo
└── README.md
```

---

## ⚙️ How It Works

### Embedding a Watermark
```
Original Audio
      ↓
Apply FFT → Convert to Frequency Domain
      ↓
Inject secret signature at specific frequency bins
      ↓
Apply Inverse FFT → Convert back to Audio
      ↓
Watermarked Audio (sounds identical to original)
```

### Detecting a Watermark
```
Any Audio File
      ↓
Apply FFT → Convert to Frequency Domain
      ↓
Check if secret frequency bins contain our signature
      ↓
Calculate confidence score
      ↓
AUTHENTIC ✅  or  TAMPERED / CLONED ❌
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/voiceguard.git
cd voiceguard

# Install dependencies
pip install numpy scipy librosa soundfile flask flask-cors
```

### Run the Backend

```bash
cd backend
python app.py
# Server starts at http://localhost:5000
```

### Run the Frontend

```bash
cd frontend
# Simply open index.html in your browser
```

---


## 👥 Team

| Member | Role |
|--------|------|
| Krish | Backend & Signal Processing |
| Shivam | Frontend & UI/UX |
| Ashiwan Singh | Integration, Testing & Presentation |

---

## 🏆 Built At

**Overclock 24** — 24-Hour Hackathon

---

## 📄 License

MIT License — Free to use and modify.

---

> *"In a world where anyone can clone a voice in 30 seconds, VoiceGuard ensures authenticity can always be proven."*
