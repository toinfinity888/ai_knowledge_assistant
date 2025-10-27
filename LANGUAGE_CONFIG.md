# Language Configuration Guide

## Current Configuration: 🇫🇷 French

Both demo modes are now configured for French language transcription.

---

## Demo Options

### Option 1: Python Microphone Demo (Better Accuracy)
**File:** `app/demo/microphone_demo.py`
**Technology:** Faster Whisper (local AI)
**Current Language:** French (`language="fr"` on line 89)

**How to run:**
```bash
python -m app.demo.microphone_demo
```

**How to change language:**
Edit line 89 in [app/demo/microphone_demo.py](app/demo/microphone_demo.py):
```python
segments, info = self.whisper_model.transcribe(
    wav_path,
    beam_size=1,
    vad_filter=True,
    language="fr"  # Change to "en", "ru", "es", "de", etc.
)
```

**Supported languages:** 99+ languages including:
- `"fr"` - French
- `"en"` - English
- `"ru"` - Russian
- `"es"` - Spanish
- `"de"` - German
- `"it"` - Italian
- `"pt"` - Portuguese
- `"ar"` - Arabic
- etc.

---

### Option 2: Web Browser Demo (Easier to Use)
**File:** `app/frontend/templates/demo/index.html`
**Technology:** Browser Speech Recognition API
**Current Language:** French (`recognition.lang = 'fr-FR'` on line 414)

**How to run:**
```bash
./launch_demo.sh
# Then open: http://localhost:8080/demo
```

**How to change language:**
Edit line 414 in [app/frontend/templates/demo/index.html](app/frontend/templates/demo/index.html):
```javascript
recognition.lang = 'fr-FR';  // Change to other locale codes
```

**Supported languages:** Browser-dependent, common ones:
- `'fr-FR'` - French (France)
- `'fr-CA'` - French (Canada)
- `'en-US'` - English (US)
- `'en-GB'` - English (UK)
- `'ru-RU'` - Russian
- `'es-ES'` - Spanish (Spain)
- `'de-DE'` - German
- `'it-IT'` - Italian
- `'pt-BR'` - Portuguese (Brazil)
- etc.

**Note:** Web demo works best in Chrome/Edge. Safari has limited support.

---

## Quick Language Switch

### To English:
**Python demo:**
```python
language="en"
```

**Web demo:**
```javascript
recognition.lang = 'en-US';
```

### To Russian:
**Python demo:**
```python
language="ru"
```

**Web demo:**
```javascript
recognition.lang = 'ru-RU';
```

---

## Testing Your Configuration

### Test Python Demo:
```bash
python -m app.demo.microphone_demo
```
Speak in French and check if transcription appears correctly.

### Test Web Demo:
```bash
./launch_demo.sh
```
Open http://localhost:8080/demo, click microphone button, speak in French.

---

## Troubleshooting

### Problem: Transcription is in wrong language
**Solution:**
1. Check which demo you're using
2. Verify the language setting in the correct file
3. Restart the demo after making changes

### Problem: Web demo doesn't recognize French
**Possible causes:**
- Using Safari (use Chrome/Edge instead)
- Browser doesn't support fr-FR (try fr-CA)
- Microphone permission not granted

### Problem: Python demo has poor accuracy
**Solutions:**
- Use larger Whisper model: change `whisper_model="base"` to `"small"` or `"medium"`
- Speak more clearly
- Reduce background noise
- Increase segment_duration to 5.0 seconds

---

## Language Settings Summary

| Component | File | Line | Current Setting |
|-----------|------|------|-----------------|
| Python Demo | app/demo/microphone_demo.py | 89 | `language="fr"` |
| Web Demo | app/frontend/templates/demo/index.html | 414 | `recognition.lang = 'fr-FR'` |

**Status:** ✅ Both configured for French
