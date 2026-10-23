# ClapLaunch

A beginner-friendly Windows double-clap app launcher. Microphone audio is processed in memory on the local computer; the app does not record audio to disk or upload it.

## Requirements
- Windows 10/11
- Python 3.11 or 3.12 (64-bit recommended)
- A working microphone and permission for desktop apps to use it

## Install and run
1. Install Python from https://www.python.org/downloads/windows/ . During setup, enable **Add Python to PATH**.
2. Open Command Prompt in this folder.
3. Install dependencies:

   ```bat
   py -m pip install -r requirements.txt
   ```

4. Run:

   ```bat
   py main.py
   ```

## First setup
1. Use **Browse…** to select each app's `.exe` path. For Terminal, `wt.exe` may work as-is; if it doesn't, browse to Windows Terminal's executable or use `cmd.exe`.
2. Click **Save settings**.
3. Click **Test launch** to verify the chosen paths.
4. Click **Start listening + calibrate**. Keep the room quiet for three seconds.
5. After calibration, clap twice about 0.2–0.5 seconds apart.
6. Enable **Run automatically when I sign in to Windows** and save settings to register startup for your Windows user. This is a per-user startup entry; administrator privileges are not required.

## Common application paths
- VS Code: `%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe`
- Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe` or `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
- Edge: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- Terminal: `wt.exe`
- Spotify: `%APPDATA%\Spotify\Spotify.exe` (if installed as a classic desktop app)

Paths differ by installation. The Browse button is the most reliable option.

## Notes and safety
- This is a prototype, not a perfect clap classifier. Loud clicks, door slams, and other sharp sounds may sometimes trigger it.
- Calibration adapts the threshold to ambient volume; it does not train an AI model.
- The detector has a short cooldown to prevent repeated launches.
- It only launches configured app paths and does not use `shell=True`.
- Audio is not intentionally saved or transmitted. The microphone remains active only while listening is enabled.
- To stop the listener, click **Stop listening** or close the app.
- To remove automatic startup, uncheck the startup option and click **Save settings**.
- Settings are stored in `%APPDATA%\ClapLaunch\config.json`.
