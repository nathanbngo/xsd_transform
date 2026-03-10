# XML → XSLT Transform

A small web UI to paste or drop **source XML** and an **XSLT** stylesheet, run the transformation in the browser, and **preview** or **download** the result.

## How to run

1. **Static server (recommended)**  
   Browsers may block `XSLTProcessor` or file reads when opening `index.html` as `file://`. Use any static server, for example:

   ```bash
   npx serve .
   ```

   Then open the URL shown (e.g. `http://localhost:3000`).

2. **VS Code**  
   Use “Live Server” or similar to open the folder.

## Usage

- **Source XML**: paste your instance document or load it via Browse / drag-and-drop (e.g. `BenefitsExtract.xml`).
- **XSLT**: paste your stylesheet or load it the same way.
- Click **Run transformation**. Output appears in the panel below.
- **Copy** or **Download** the result (`.xml`, `.html`, or `.txt` depending on output type).

## Notes

- The app uses the browser’s **XSLT 1.0** engine. XSLT 2.0/3.0 stylesheets need something like **Saxon** on a server.
- **UTF-8 BOM** is stripped when loading files so XML parsing doesn’t fail.
- **Very large output** (>500k chars) is truncated in the preview only; **Download** always contains the full result.
- If **Run** does nothing or stylesheets “fail silently”, open DevTools: Chromium’s `importStylesheet` can return `false` for invalid/unsupported XSLT—the app surfaces that as an error.

## Troubleshooting

| Issue | What to do |
|-------|------------|
| `XSLTProcessor is not available` | Serve over `http://localhost`, not `file://`. |
| Stylesheet rejected | Use XSLT 1.0 only; avoid 2.0/3.0 features. |
| Empty output | XSLT must produce a single root element for `transformToDocument`; text-only output needs a different pipeline (e.g. server Saxon). |
| Drag highlight flickers | Fixed via drag-depth counting on dropzones. |

If the transform outputs HTML (root element `html` in XHTML namespace), the download will use a `.html` extension.

## Files

| File        | Purpose                          |
|------------|-----------------------------------|
| `index.html` | Layout and structure             |
| `styles.css` | UI styling                       |
| `app.js`   | Parse XML, run XSLT, copy/download |
