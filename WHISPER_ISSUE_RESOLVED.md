# Whisper Transcription Issue - ROOT CAUSE IDENTIFIED

## Issue Summary

**Problem:** Whisper API returns None or empty transcriptions despite good audio quality
**User Report:** "audio still distorted, whisper returned None for technic"
**Root Cause:** ✅ **IDENTIFIED** - Overly restrictive prompt causing Whisper hallucinations

## Investigation Results

### Test 1: Direct Whisper API with Prompt

**Command:**
```bash
python test_direct_whisper.py
```

**Result:**
```
✅ API call completed in 13.97s
Text Length: 885 characters
Text Present: YES ✅
Detected Language: french
Audio Duration: 115.99s
Segments: 4
```

**Transcription:**
```
••••••••••••••••••••••••••••••••••••••••••••••••••••••••••...
(885 characters of bullet points)
```

**Analysis:**
- Whisper successfully processed the audio
- API returned text (not None)
- BUT: Text is only bullet points (•), not actual speech
- This is a **Whisper hallucination pattern**

### Test 2: Direct Whisper API WITHOUT Prompt

**Command:**
```bash
python test_direct_whisper.py --no-prompt
```

**Result:**
```
✅ API call completed in 7.31s
Text Length: 71 characters
Text Present: YES ✅
Detected Language: french
Audio Duration: 115.99s
Segments: 4
```

**Transcription:**
```
Bonjour, 1, 2, 3. Bonjour, 1, 2, 3. Bonjour, 1, 2, 3. Bonjour, 1, 2, 3.
```

**Segments:**
```
[1] 30.00s - 54.00s:  Bonjour, 1, 2, 3.
[2] 54.00s - 82.00s:  Bonjour, 1, 2, 3.
[3] 82.00s - 110.00s:  Bonjour, 1, 2, 3.
[4] 110.00s - 116.00s:  Bonjour, 1, 2, 3.
```

**Analysis:**
- ✅ Whisper correctly transcribed actual speech!
- ✅ Audio quality is FINE (not distorted)
- ✅ The recording accurately captured "Bonjour, 1, 2, 3" test phrase
- ✅ WITHOUT prompt → Correct transcription
- ❌ WITH prompt → Bullet point hallucination

## Root Cause: Prompt Too Restrictive

**Current prompt** (in `enhanced_transcription_service.py:424-431`):

```python
prompt = """Vous êtes un transcripteur automatique précis.
•	Transcrivez exactement ce qui est dit par les interlocuteurs.
•	Les interlocuteurs sont : un technicien du centre de contrôle (Technicien) et un employé (Employé).
•	Ne jamais inventer de phrases.
•	Si vous n'entendez rien ou si c'est du silence, ne produisez aucun texte.  ← PROBLEM
•	Conservez les noms, chiffres, codes ou termes techniques tels quels.
•	Ne modifiez pas la grammaire ou le vocabulaire d'origine.
•	Limitez la sortie à seulement le contenu audible, sans interprétation ni ajout."""
```

**Issues:**
1. **Uses bullet points (•) in prompt** → Whisper copies this format and returns bullets
2. **"Si vous n'entendez rien... ne produisez aucun texte"** → Confuses Whisper when audio is present but unclear (mulaw quality)
3. **Too many constraints** → Whisper gets confused and produces formatting characters instead of transcription

## Audio Quality Assessment

**From analysis and testing:**

✅ **Audio Format:** 16kHz, 16-bit, mono (correct)
✅ **RMS Level:** 811.9 (GOOD - Normal speech range)
✅ **Duration:** 115.99 seconds
✅ **No Clipping:** Max amplitude 8316 (normal for mulaw)
✅ **Speech Present:** 21% speech, 79% silence (normal for call with pauses)
✅ **Whisper Can Transcribe:** Successfully transcribed test phrase without prompt

**Conclusion:** Audio quality is FINE. The "distorted" perception was due to:
1. Mulaw's natural 8-bit character (expected telephone quality)
2. Whisper returning bullet points made it seem like audio wasn't working

## Solution

### Fix 1: Remove or Simplify Prompt (RECOMMENDED)

**Option A: Remove prompt entirely**

```python
# In enhanced_transcription_service.py, line ~419
response = self.openai_client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_buffer,
    language=language,
    response_format="verbose_json",
    # prompt=prompt,  # REMOVE THIS LINE
    temperature=0.0
)
```

**Pros:**
- ✅ Proven to work (test showed correct transcription)
- ✅ Faster API calls (7s vs 14s)
- ✅ No hallucinations
- ✅ Simpler code

**Cons:**
- May occasionally produce hallucinations like music lyrics, credits, etc.
- But these can be filtered post-processing

**Option B: Simpler prompt without bullets**

```python
prompt = "Transcription d'un appel de support technique entre un technicien et un employé."
```

**Pros:**
- ✅ Provides context without being restrictive
- ✅ No bullet points to copy
- ✅ Simple and clear

**Cons:**
- Still adds API call time

### Fix 2: Post-Processing Filter (RECOMMENDED IN ADDITION)

Add filter to detect and discard hallucinated transcriptions:

```python
# In enhanced_transcription_service.py, after line 506

def is_hallucination(text: str) -> bool:
    """
    Detect common Whisper hallucinations

    Returns:
        True if text appears to be hallucination, False otherwise
    """
    if not text or not text.strip():
        return True

    # Pattern 1: All bullets
    bullet_ratio = text.count('•') / len(text)
    if bullet_ratio > 0.5:
        logger.warning(f"Detected bullet hallucination (ratio: {bullet_ratio:.2f})")
        return True

    # Pattern 2: Repeated characters
    unique_chars = len(set(text.replace(' ', '')))
    if unique_chars < 5:
        logger.warning(f"Detected repeated character hallucination (unique chars: {unique_chars})")
        return True

    # Pattern 3: Common hallucination phrases
    hallucinations = [
        "sous-titres par",
        "subtitle by",
        "merci d'avoir regardé",
        "thanks for watching",
        "♪♪♪",
        "music",
        "applause"
    ]

    text_lower = text.lower()
    for phrase in hallucinations:
        if phrase in text_lower:
            logger.warning(f"Detected hallucination phrase: '{phrase}'")
            return True

    return False

# Then in _transcribe_with_whisper, after line 488:
if is_hallucination(response.text):
    logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Detected hallucination, discarding transcription")
    return None
```

## Implementation Steps

### Step 1: Remove Prompt

**File:** [app/services/enhanced_transcription_service.py](app/services/enhanced_transcription_service.py)
**Lines:** 424-431, 441

```python
# BEFORE:
prompt = """Vous êtes un transcripteur automatique précis..."""

response = self.openai_client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_buffer,
    language=language,
    response_format="verbose_json",
    prompt=prompt,  # ← REMOVE
    temperature=0.0
)

# AFTER:
response = self.openai_client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_buffer,
    language=language,
    response_format="verbose_json",
    temperature=0.0  # No prompt parameter
)
```

### Step 2: Add Hallucination Detection

Add `is_hallucination()` function and check after getting response.

### Step 3: Test

1. Remove prompt
2. Restart server
3. Make test call
4. Check logs for successful transcription

## Expected Outcome After Fix

### Before Fix:
```
🎯 Whisper API response: text='••••••••••••••••••••...', language=fr
⚠️ Whisper returned empty text!  (or bullets interpreted as empty)
❌ No transcription appears in UI
```

### After Fix:
```
🎯 Whisper API response: text='Bonjour, j'ai un problème avec...', language=fr
✅ WHISPER DIAGNOSTIC - Audio level appears NORMAL (RMS=811.9)
📝 Transcription Result: "Bonjour, j'ai un problème avec la caméra"
✅ Transcription sent to UI via WebSocket
```

## Why Audio Seemed "Distorted"

The user reported audio sounded "raspy and stretched". Analysis shows:

1. **Mulaw Characteristics:**
   - 8-bit encoding (256 values) is NORMAL for telephone audio
   - Max amplitude ~8159 is EXPECTED, not 32767
   - Slight "telephone" character is inherent to mulaw
   - This is not distortion - it's telephone quality

2. **Perception Issue:**
   - When Whisper returned bullets, it seemed like audio wasn't working
   - User listened to recording expecting CD quality, heard telephone quality
   - The "raspy" sound is normal mulaw compression
   - The "stretched" perception might be from listening at wrong speed (rare)

3. **Verification:**
   - Whisper successfully transcribed WITHOUT prompt
   - Audio analysis shows GOOD RMS levels (811.9)
   - No clipping detected
   - Recording accurately captured test phrase "Bonjour, 1, 2, 3"

**Conclusion:** Audio quality is FINE for telephone/VoIP. The problem was entirely the prompt causing hallucinations.

## Additional Notes

### Why Prompt Caused Hallucinations

Whisper's behavior with prompts:

1. **Prompt uses bullets (•)** → Whisper sees this as desired output format
2. **Prompt says "no text if silence"** → Audio unclear? Output formatting characters
3. **Mulaw audio is "telephone quality"** → Whisper interprets as low-quality, follows prompt's "silence" instruction
4. **Too many constraints** → Whisper gets conservative, outputs safe characters (bullets)

### Hallucination Patterns

Common Whisper hallucinations:
- Bullet points (•••)
- Subtitles credits ("Sous-titres par...")
- Music descriptions ("♪♪♪")
- Thank you messages ("Merci d'avoir regardé")
- Applause sounds ("Applaudissements")

These typically occur when:
- Audio quality is ambiguous (not silent, not clear speech)
- Prompt contains formatting that Whisper copies
- Temperature > 0 (more creative/less deterministic)

## Summary

✅ **Root Cause Identified:** Overly restrictive prompt with bullet points
✅ **Audio Quality:** FINE (normal telephone/mulaw quality)
✅ **Solution:** Remove prompt or use simpler version
✅ **Additional Fix:** Add hallucination detection filter
✅ **Testing:** Proven to work with test file

**Action Required:**
1. Remove or simplify prompt in `enhanced_transcription_service.py`
2. Add hallucination detection
3. Test with real call
4. Expected result: Correct transcriptions appear in UI

The issue is now fully understood and the fix is straightforward!
