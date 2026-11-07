# ZoomRecorder Pro 🎥🔍

A modern, high-performance Windows PC Screen Recorder built with **Python 3.11+**, **PyQt5**, **mss**, **OpenCV**, and **pynput**. Featuring smooth, cinematic **Mouse Click Zoom animations**, cursor highlights, expanding ripple effects, audio capture, and an OBS Studio-inspired dark modern user interface.

---

## 🌟 Key Features

### 1. 🎬 OBS-Style Dark Modern UI
- **Top Bar**: Stylish "ZoomRecorder Pro" branding, live status pills (`IDLE`, `REC`, `PAUSED`), digital recording timer (`00:00:00`), live file size counter (`MB`), and shortcut indicator.
- **Center Live Preview**: Real-time responsive preview display of the captured screen with smooth scaling and aspect-ratio preservation.
- **Bottom Control Deck**:
  - **Start Recording** (Vibrant Crimson Red) / **Stop** / **Pause & Resume**.
  - **Record Area Selector**: Full Screen, Custom Selected Area, or Specific Window.
  - **Video Quality**: 1080p (Full HD), 720p (HD), or Original native resolution.
  - **Frame Rate (FPS)**: 30 FPS or 60 FPS.
  - **Zoom Level**: 1.5x, 2.0x, or 3.0x magnification.
  - **Zoom Duration Slider**: Configurable from 1.0s to 3.0s (default 1.5s).
  - **Mouse Highlight Toggle**: Yellow cursor ring with glowing anti-aliased border.
  - **Click Sound Toggle**: Mechanical mouse-click sound generated and played asynchronously.
  - **Audio Recording Toggle**: Record microphone or system audio synced with video.
  - **Save Folder Selector**: Easily choose destination folder (defaults to `Desktop/ZoomRecorder`).
  - **Minimize to Tray**: Keep screen completely clear while recording.

---

### 2. 🔍 Mouse Click Zoom Effect (Core Feature)
- **Automatic Left-Click Detection**: Uses `pynput` mouse listener to intercept click positions without lag.
- **Smooth Easing Animation**:
  - **Zoom-In (0.3s)**: Smoothstep interpolation ($3p^2 - 2p^3$) transition from 1.0x to the selected Zoom Level.
  - **Zoom Hold (1.0s – 3.0s)**: Locks viewport centered at the click coordinates with edge clamping.
  - **Zoom-Out (0.3s)**: Smooth return back to full frame.
- **Visual Overlays**:
  - **Expanding Ripples**: Animated concentric circles with fading alpha originating from the click coordinate.
  - **Cursor Highlight**: Anti-aliased yellow aura and pointer arrow rendered seamlessly on output frames.

---

### 3. 📐 Area & Window Selection
- **Select Area**: Fullscreen transparent dark overlay allowing drag-and-drop bounding box selection with live pixel dimensions (`W × H`).
- **Specific Window**: Automatically detects open visible windows (via `win32gui`) and records only the chosen window's bounding rect.
- **Full Screen**: Automatically captures the primary monitor or virtual desktop.

---

### 4. ⌨️ Global Shortcuts & System Tray
- **F9**: Global Start / Stop Recording (works from any game, browser, or app).
- **F10**: Global Pause / Resume Recording.
- **System Tray Icon**: Context menu to Start, Stop, Pause, Open Recordings Folder, or Restore Window.

---

## 📁 Project Architecture

```
Screen Rec/
├── main.py             # OBS-style PyQt5 GUI, preview loop, tray & event handling
├── recorder.py         # mss/QScreen capture engine, zoom interpolation, ripples, OpenCV writer
├── mouse_tracker.py    # Zero-latency pynput mouse click listener & global hotkeys (F9/F10)
├── utils.py            # Click sound generator, audio recorder, FFmpeg muxer, area selector
├── requirements.txt    # Python package dependencies
├── build.bat           # 1-click PyInstaller Windows build script
└── README.md           # Documentation and user guide
```

---

## 🚀 Getting Started

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Python 3.11+ installed and added to `PATH`
- (Optional but recommended) FFmpeg in `PATH` for automatic audio/video muxing

### Installation

1. **Clone or navigate to the directory**:
   ```bash
   cd "Screen Rec"
   ```

2. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

There are three ways to run ZoomRecorder Pro without any black terminal/command prompt window:

1. **Direct Standalone EXE (Recommended)**:
   Double-click `dist/ZoomRecorder.exe`. It opens instantly as a native Windows application with its custom app icon and **no terminal window**.

2. **Silent VBS Launcher**:
   Double-click `Launch_ZoomRecorder.vbs`.

3. **Python Windowed Mode**:
   Double-click `main.pyw` or run:
   ```bash
   pythonw main.pyw
   ```
   *(Running with `pythonw` instead of `python` runs the app in the background without opening a terminal window).*

---

## 🛠️ Building Standalone Executable (.exe)

To bundle ZoomRecorder Pro into a single standalone `.exe` that runs without Python installed:

Simply double-click `build.bat` or run:

```bash
build.bat
```

Or manually with PyInstaller:
```bash
pyinstaller --onefile --windowed --name ZoomRecorder --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --hidden-import=win32gui --hidden-import=win32con --hidden-import=sounddevice main.py
```

The compiled binary will be located in the `dist/` directory:
```
dist/ZoomRecorder.exe
```

---

## 💡 How It Works (Zoom Math)

When a left-click occurs at screen coordinates $(C_x, C_y)$:
1. **Normalized Progress $p(t)$**:
   $$p(t) = \frac{t - t_0}{\Delta t}$$
2. **Smoothstep Easing**:
   $$S(p) = 3p^2 - 2p^3$$
3. **Dynamic Zoom Level**:
   $$Z(t) = 1.0 + (Z_{\text{target}} - 1.0) \cdot S(p)$$
4. **ROI Bounding Box**:
   $$W_{\text{crop}} = \frac{W}{Z(t)}, \quad H_{\text{crop}} = \frac{H}{Z(t)}$$
   The cropped box is clamped to $[0, W - W_{\text{crop}}]$ and $[0, H - H_{\text{crop}}]$ and scaled back to output resolution using high-quality bilinear interpolation (`cv2.INTER_LINEAR`).

---

## 📄 License
MIT License. Free for personal and commercial screen recording and tutorial creation.
