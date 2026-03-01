# VoiceGuard — AI Voice Clone Detection & Watermarking System

> **Hackathon Project | Overclock 24**  
> A resilient, secure audio authentication framework capable of protecting digital voice integrity in an AI-driven world.

---

## 1. Problem Statement

### Problem Title
AI Voice Clone Detection & Authentication

### Problem Description
AI-based voice synthesis has made it possible to generate highly realistic cloned audio. Deepfake audio is being used to manipulate public opinion, commit financial fraud, and impersonate individuals in sensitive contexts.

### Target Users
- Organizations and individuals needing to verify audio authenticity
- Legal and forensic investigators
- Media platforms combating deepfake audio
- Security-sensitive industries (finance, law enforcement, broadcasting)

### Existing Gaps
There is currently no widely adopted system that can embed secure watermarks into audio AND detect tampering or synthetic generation reliably.

---

## 2. Problem Understanding & Approach

### Root Cause Analysis
The rapid advancement of AI voice synthesis tools has outpaced the development of detection and verification mechanisms. Without a standardized way to authenticate audio, anyone can generate convincing fake audio that is nearly indistinguishable from the original.

### Solution Strategy
Implement a dual-purpose system that proactively embeds invisible watermarks into authentic audio at creation time, and reactively detects whether any given audio file is authentic or tampered — providing a full chain of custody for audio content.

---

## 3. Proposed Solution

### Solution Overview
VoiceGuard is a two-in-one audio authentication system that embeds inaudible, secure watermarks into original audio and detects whether any audio file has been tampered with, cloned, or lacks a valid watermark.

### Core Idea
Using FFT (Fast Fourier Transform) frequency-domain techniques, secret signatures are injected into inaudible frequency bins of an audio file. These signatures are imperceptible to listeners but detectable by the system, enabling reliable authentication.

### Key Features

| Feature | Description |
|--------|-------------|
| 🔐 FFT Watermarking | Embeds secret signatures in inaudible frequency bins |
| 🔍 Tamper Detection | Detects missing or altered watermarks with confidence score |
| 📄 Forensic Report | Downloadable report with verdict, confidence %, and timestamp |
| 📊 Live Dashboard | Real-time stats — files scanned, threats detected, files protected |
| 🌐 REST API | Simple Flask API for easy integration into any platform |
| 🎨 Clean UI | Dark-themed, responsive frontend with drag & drop upload |

---

## 4. System Architecture

### High-Level Flow
User → Frontend (HTML/CSS/JS) → Flask REST API → FFT Watermark Engine → Audio Output / Detection Report

### Architecture Description
The user uploads an audio file via the frontend drag-and-drop interface. The file is sent to the Flask backend, which routes it to either the watermark embedding module or the detection module. The core FFT engine processes the audio in the frequency domain, then returns the result (watermarked audio or detection verdict) back to the frontend along with a forensic report.

### Architecture Diagram
(Add system architecture diagram image here)

---

## 5. Database Design

### ER Diagram
(Add ER diagram image here)

### ER Diagram Description
VoiceGuard is primarily a stateless processing system. Future iterations may include a database for storing scan history, watermark keys, and user session data.

---

## 6. Dataset Selected

### Dataset Name
Custom test audio samples

### Source
Internally recorded and publicly available audio samples

### Data Type
WAV / MP3 audio files

### Selection Reason
Required diverse, real-world audio samples to validate watermark embedding and detection across different voice types, qualities, and lengths.

### Preprocessing Steps
- Convert audio files to a standard sample rate
- Normalize amplitude levels
- Trim silence from start/end of clips

---

## 7. Model Selected

### Model Name
FFT-Based Frequency Domain Watermarking (Signal Processing Algorithm)

### Selection Reasoning
FFT allows precise manipulation of specific inaudible frequency bins without affecting perceptible audio quality. It is computationally efficient and requires no training data, making it ideal for a hackathon setting.

### Alternatives Considered
- Deep learning-based audio classification (more complex, requires training data)
- LSB (Least Significant Bit) watermarking in time domain (less robust to compression)

### Evaluation Metrics
- Watermark detectability rate (confidence score %)
- Perceptual audio quality (watermarked audio sounds identical to original)
- Tamper detection accuracy (detection of cloned/modified audio)

---

## 8. Technology Stack

### Frontend
HTML5, CSS3, Vanilla JavaScript — dark-themed responsive UI with drag-and-drop file upload

### Backend
Python, Flask, Flask-CORS

### ML/AI
NumPy, SciPy (FFT-based signal processing), Librosa, SoundFile

### Database
N/A (stateless processing; persistent storage is a future scope item)

### Deployment
Railway.app / Render.com

---

## 9. API Documentation & Testing

### API Endpoints List
- **POST /embed** — Upload an audio file to embed a watermark; returns watermarked audio
- **POST /detect** — Upload an audio file to check for a valid watermark; returns verdict and confidence score
- **GET /report** — Download the forensic report (PDF) with verdict, confidence %, and timestamp

### API Testing Screenshots
(Add Postman / Thunder Client screenshots here)

---

## 10. Module-wise Development & Deliverables

### Checkpoint 1: Research & Planning
- Deliverables: Problem scoping, tech stack selection, FFT watermarking approach validated

### Checkpoint 2: Backend Development
- Deliverables: Flask API server (`app.py`) with `/embed` and `/detect` endpoints functional

### Checkpoint 3: Frontend Development
- Deliverables: Responsive dark-themed UI with drag-and-drop upload and live dashboard stats

### Checkpoint 4: Model Training
- Deliverables: N/A — FFT algorithm requires no training; core watermark logic (`watermark.py`) implemented

### Checkpoint 5: Model Integration
- Deliverables: Frontend connected to backend API; end-to-end watermark embed and detect flow working

### Checkpoint 6: Deployment
- Deliverables: Backend deployed on Railway.app/Render.com; frontend accessible via browser

---

## 11. End-to-End Workflow

1. User opens the VoiceGuard web interface
2. User drags and drops an audio file onto the upload area
3. User selects either **Embed Watermark** or **Detect Watermark**
4. Frontend sends the file to the Flask REST API
5. Backend applies FFT and injects/checks the secret signature in inaudible frequency bins
6. Backend returns result — watermarked audio file OR detection verdict with confidence score
7. User downloads the watermarked audio or the forensic report

---

## 12. Demo & Video


- Demo Video Link: https://drive.google.com/file/d/1hiRxTFIV-RXiALqd-vTP-eii3bkLT5bN/view?usp=share_link
- GitHub Repository: (https://github.com/shivamyadav17062006-code/Voice-Cloning-Watermark-Protection-System/tree/main)

---

## 13. Hackathon Deliverables Summary

- Functional FFT watermark embedding and detection system
- Flask REST API with embed, detect, and report endpoints
- Responsive dark-themed frontend with drag-and-drop interface and live stats dashboard
- Downloadable forensic report for legal/evidentiary use

---

## 14. Team Roles & Responsibilities

| Member Name | Role | Responsibilities |
|-------------|------|-----------------|
| Krish | Backend & Signal Processing | Flask API development, FFT watermark logic implementation |
| Shivam | Frontend & UI/UX | HTML/CSS/JS UI design, drag-and-drop upload, live dashboard |
| Ashiwan Singh | Integration, Testing & Presentation | API-frontend integration, QA testing, demo presentation |

---

## 15. Future Scope & Scalability

### Short-Term
- Add user authentication to manage watermark keys per user
- Improve tamper detection robustness against audio compression artifacts
- Add support for more audio formats (AAC, FLAC, OGG)

### Long-Term
- Integrate ML-based deepfake detection as a second validation layer
- Build a browser extension for real-time audio verification on media platforms
- Provide an enterprise-grade API with rate limiting, audit logs, and key management
- Pursue standardization as an industry audio authentication protocol

---

## 16. Known Limitations

- Watermark may be degraded by heavy audio compression (e.g., low-bitrate MP3 conversion)
- No persistent database for watermark key management in the current version
- Detection confidence score may be reduced for very short audio clips

---

## 17. Impact

- Empowers individuals and organizations to prove the authenticity of audio recordings
- Provides a practical, open-source tool against deepfake audio used in fraud and disinformation
- Lays the groundwork for a standardized audio authentication ecosystem

---

> *"In a world where anyone can clone a voice in 30 seconds, VoiceGuard ensures authenticity can always be proven."*
