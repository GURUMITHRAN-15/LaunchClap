# 🎙️ LaunchClap

### Control your Windows workspace with a double clap.

LaunchClap is a Windows desktop utility that listens for a double clap and launches your configured applications. It features a modern dark interface, neon-green styling, live audio visualization, and microphone-level monitoring.

> **Privacy-first design:** Audio is processed locally in memory. LaunchClap does not intentionally record audio to files or upload audio to a server.

---

## ✨ Features

- 👏 **Double-clap detection** — trigger your configured workspace with two claps.
- 🎨 **Modern dark GUI** — a dark interface with neon-green accents.
- 📊 **Live waveform** — visualize microphone input in real time.
- 🎚️ **Audio level meter** — monitor incoming microphone volume.
- 🎯 **Automatic calibration** — estimate background noise before listening.
- 🖥️ **Application launcher** — configure applications such as VS Code, Chrome, Windows Terminal, and Spotify.
- ⚙️ **Configurable settings** — save application paths and detection sensitivity.
- 🚀 **Windows startup option** — optionally launch the application when you sign in.
- 🔒 **Local processing** — no cloud audio processing or account required.

## 🖼️ Screenshots

*Screenshots coming soon.*

Add a screenshot of the LaunchClap interface here once you capture one:

```md
![LaunchClap interface](docs/screenshots/launchclap.png)
```

## 🛠️ Built With

- Python
- PySide6 — desktop GUI
- NumPy — audio signal calculations
- SoundDevice — microphone input
- Git and GitHub — version control and collaboration

## 💻 Requirements

- Windows 10 or Windows 11
- Python 3.14, if running from source
- A working microphone
- Git, if cloning the repository
- An internet connection for the initial dependency installation

## 📥 Installation

### Option 1: Run from source

**1. Clone the repository**

```bash
git clone https://github.com/GURUMITHRAN-15/LaunchClap.git
cd LaunchClap
```

**2. Install dependencies**

```bash
py -3.14 -m pip install -r requirements.txt
```

**3. Start LaunchClap**

```bash
py -3.14 main.py
```

If the `py -3.14` command is unavailable, install a compatible Python version and use its corresponding command.

## 🎮 How to Use

1. Open LaunchClap.
2. Configure the executable paths for the applications you want to launch.
3. Save your settings.
4. Click **Start Listening + Calibrate**.
5. Keep the room quiet while the microphone calibrates.
6. Clap twice within the supported detection interval.
7. LaunchClap attempts to open your configured applications.

**Tip:** Adjust the sensitivity if background noise triggers detection or your claps aren't recognized. Microphone permissions and input-device settings can also affect detection.

## ⚙️ Configuration

LaunchClap stores its settings in:

```text
%APPDATA%\ClapLaunch\config.json
```

Configuration includes application paths, detection threshold, and the Windows startup preference.

You can change application paths through the graphical interface instead of editing the configuration file manually.

## 🔐 Privacy and Security

LaunchClap is designed for local desktop use.

- Audio samples are analyzed in memory for clap detection and visualization.
- The application does not intentionally save microphone recordings or upload audio.
- Application launching uses configured executable paths.
- The optional Windows startup setting modifies the current user's Windows startup registry entry.

**Important:** Only configure executable paths you trust. Review the source code before running software you build or download, and check microphone permissions in Windows.

## 🧰 Troubleshooting

### Microphone is not detected

- Check Windows microphone permissions.
- Confirm that the intended microphone is enabled.
- Close other applications that may be interfering with microphone access.
- Run LaunchClap from a terminal to view error messages.

### Claps are not detected

- Complete calibration in a quiet environment.
- Adjust the detection sensitivity.
- Move closer to the microphone or check its input level.
- Reduce background noise and try again.

### Application does not launch

- Verify the configured executable path.
- Confirm that the application exists at that location.
- Use the **Test Launch** button to check the configured applications.

### Dependencies fail to install

Update pip and retry:

```bash
py -3.14 -m pip install --upgrade pip
py -3.14 -m pip install -r requirements.txt
```

## 🗺️ Roadmap

- [x] Double-clap detection
- [x] Configurable application paths
- [x] Automatic audio calibration
- [x] Dark GUI with neon-green styling
- [x] Live waveform and input meter
- [ ] Add screenshots and a demonstration video
- [ ] Improve automated tests
- [ ] Publish a tested Windows executable release
- [ ] Add more microphone and detection settings

## 🤝 Contributing

Contributions, bug reports, and feature suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make and test your changes.
4. Commit your work.
5. Open a pull request describing the changes.

Please include reproduction steps when reporting bugs.

## 📄 License

No license has been specified here yet. Until a license is added to the repository, do not assume that others have permission to redistribute or modify the project.

## 👨‍💻 Author

**Gurumithran**

GitHub: [@GURUMITHRAN-15](https://github.com/GURUMITHRAN-15)

---

⭐ If you find LaunchClap useful, consider starring the repository!
