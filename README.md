# XML Transform — Desktop app

Native **Python** GUI (no browser, no JavaScript). Loads **source XML** and an **XSLT 1.0** stylesheet, runs the transform with **lxml** (libxslt), shows **pretty-printed** output, and lets you **save** the full result to disk.

## Requirements

- **Python 3.10+**
- Dependencies: `lxml`, `customtkinter`

## Install & run

```bash
cd desktop_app
pip install -r requirements.txt
python xml_xslt_gui.py
```

### One-click on Windows

Double‑click **`Run XML Transform.bat`** in this folder (or use the same file in the repo root — it jumps into `desktop_app/`).  
The batch file uses `python` or the `py` launcher and, if present, `.venv\Scripts\python.exe`.

## Features

| Feature | Description |
|--------|-------------|
| **Browse** | Open XML / XSLT from files (UTF-8 BOM stripped). |
| **Run transformation** | XSLT 1.0 only (same class of engine as the old browser app). |
| **Formatted preview** | XML is pretty-printed in the output panel. |
| **Truncation** | Very large output (>500k chars) is truncated in the preview only; **Save** writes the full file. |
| **Save / Download** | Choose path and extension (`.xml` / `.html` / `.txt` depending on result). |
| **Copy** | Copy full output to clipboard. |
| **Load sample** | Minimal XML + identity-style XSLT for a quick test. |

## XSLT 2.0 / 3.0

Not supported in-app. Use **Saxon** or another engine for 2.0+ stylesheets.

## Optional: single-folder executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name XMLTransform xml_xslt_gui.py
```

Run the built `.exe` from `dist/`.
