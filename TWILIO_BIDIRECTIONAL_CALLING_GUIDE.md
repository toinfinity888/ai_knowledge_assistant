# Guide Complet: Système d'Appel Bidirectionnel avec Twilio

## Vue d'Ensemble

Système d'appel téléphonique en temps réel avec:
- ✅ **Appels bidirectionnels** via Twilio
- ✅ **Speaker diarization** (identification des locuteurs)
- ✅ **Priorisation du technicien** - Le système écoute principalement le technicien
- ✅ **Transcription en temps réel** avec Whisper
- ✅ **Analyse IA contextuelle** - Solutions automatiques ou questions de clarification
- ✅ **Streaming audio** bidirectionnel (technicien ↔ système IA)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Téléphone du Technicien                       │
│                         (n'importe où)                           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Appel téléphonique
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Twilio Cloud                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Réception  │  │   Streaming  │  │  Audio bidirectionnel  │ │
│  │   d'appel   │─→│   WebSocket  │─→│   (mulaw ↔ PCM)       │ │
│  └─────────────┘  └──────────────┘  └────────────────────────┘ │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ WebSocket (audio streaming)
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               Notre Serveur (Flask + WebSocket)                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  TwilioAudioService                                       │ │
│  │  - Conversion audio (mulaw → PCM 16kHz)                   │ │
│  │  - Buffering (1 seconde)                                  │ │
│  │  - Envoi vers transcription                               │ │
│  └─────────────┬─────────────────────────────────────────────┘ │
│                │                                                 │
│                ▼                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  SpeakerDiarizationService                                │ │
│  │  - Détection d'activité vocale (VAD)                      │ │
│  │  - Identification locuteur (technicien vs agent)          │ │
│  │  - Priorisation (technicien en premier)                   │ │
│  └─────────────┬─────────────────────────────────────────────┘ │
│                │                                                 │
│                ▼                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  EnhancedTranscriptionService                             │ │
│  │  - Buffering audio (3 secondes)                           │ │
│  │  - Transcription Whisper (OpenAI API)                     │ │
│  │  - Filtrage par speaker_role                              │ │
│  └─────────────┬─────────────────────────────────────────────┘ │
│                │                                                 │
│                ▼                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Agent Orchestrator (système existant)                    │ │
│  │  - Context Analyzer                                       │ │
│  │  - RAG Engine (recherche base de connaissances)           │ │
│  │  - Clarification Agent                                    │ │
│  │  - Génération de solutions                                │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  Base Qdrant    │
        │  (Solutions)    │
        └─────────────────┘
```

## Composants Principaux

### 1. TwilioAudioService
**Fichier:** `app/services/twilio_audio_service.py`

**Responsabilités:**
- Initier des appels sortants vers les techniciens
- Gérer le streaming audio bidirectionnel via WebSocket
- Convertir audio entre formats Twilio (mulaw 8kHz) et Whisper (PCM 16kHz)
- Envoyer audio IA vers le technicien

**Méthodes clés:**
```python
initiate_call(to_number, session_id, websocket_url)
  → Démarre un appel vers le technicien

handle_media_stream(websocket, session_id)
  → Gère le flux audio WebSocket de Twilio

send_audio_to_stream(session_id, audio_data)
  → Envoie audio généré par IA au technicien

end_call(call_sid)
  → Termine l'appel
```

**Conversion audio:**
- **Entrant:** Mulaw 8kHz (Twilio) → PCM 16kHz (Whisper)
- **Sortant:** PCM 16kHz (IA) → Mulaw 8kHz (Twilio)

### 2. SpeakerDiarizationService
**Fichier:** `app/services/speaker_diarization_service.py`

**Responsabilités:**
- Identifier qui parle (technicien vs agent support)
- Détecter l'activité vocale (VAD)
- Prioriser la parole du technicien
- Filtrer les segments audio non pertinents

**Méthodes clés:**
```python
register_speaker(session_id, speaker_id, speaker_name, speaker_role)
  → Enregistre un locuteur pour la session

identify_speaker(session_id, audio_data, timestamp)
  → Identifie qui parle dans un segment audio

should_process_segment(session_id, speaker_role, segment_duration)
  → Décide si un segment doit être traité par l'IA

prioritize_technician_speech(session_id, segments)
  → Trie les segments avec le technicien en premier
```

**Logique de priorisation:**
- **Technicien:** Traiter si ≥ 0.5 secondes
- **Agent support:** Traiter si ≥ 1.0 secondes
- **Inconnu:** Ne pas traiter

**VAD (Voice Activity Detection):**
- Calcul RMS energy de l'audio
- Seuil: 0.01 (normalized)
- Si en dessous → silence, ignorer

### 3. EnhancedTranscriptionService
**Fichier:** `app/services/enhanced_transcription_service.py`

**Responsabilités:**
- Bufferiser l'audio entrant (3 secondes par défaut)
- Créer fichiers WAV pour Whisper
- Transcription via OpenAI Whisper API
- Combiner transcription + info speaker
- Envoyer au pipeline d'agents

**Méthodes clés:**
```python
process_audio_stream(session_id, audio_chunk, timestamp)
  → Traite un chunk audio du stream Twilio

initialize_session(session_id, technician_id, technician_name, ...)
  → Initialise une session avec profils speakers

end_session(session_id)
  → Termine session et retourne statistiques
```

**Buffering:**
- **Durée min:** 3 secondes (buffer_duration)
- **Durée max:** 10 secondes (max_buffer_duration)
- Force transcription si max atteint

**Workflow:**
1. Audio chunk arrive → ajouté au buffer
2. Si buffer ≥ 3s → transcription
3. Speaker diarization → identifier locuteur
4. Si technicien → envoyer aux agents
5. Si agent → ignorer (parole système)

### 4. Routes Twilio
**Fichier:** `app/api/twilio_routes.py`

**Endpoints:**

#### POST `/twilio/initiate-call`
Initier un appel vers un technicien

**Request:**
```json
{
  "phone_number": "+33612345678",
  "technician_id": "TECH001",
  "technician_name": "Jean Dupont",
  "session_id": "session_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "call_sid": "CAxxxxxxxxxxxx",
  "session_id": "session_abc123",
  "status": "initiated"
}
```

#### POST `/twilio/end-call`
Terminer un appel actif

**Request:**
```json
{
  "call_sid": "CAxxxxxxxxxxxx",
  "session_id": "session_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "call_sid": "CAxxxxxxxxxxxx",
  "status": "completed",
  "duration": 120,
  "session_stats": {
    "total_segments": 15,
    "speakers": {
      "TECH001": {
        "segment_count": 12,
        "speaker_role": "technician"
      }
    }
  }
}
```

#### WebSocket `/twilio/media-stream`
Stream audio bidirectionnel avec Twilio

**Messages Twilio → Serveur:**
```json
// Démarrage
{
  "event": "start",
  "start": {
    "streamSid": "MZxxxx",
    "customParameters": {
      "session_id": "session_abc123"
    }
  }
}

// Audio data
{
  "event": "media",
  "media": {
    "payload": "base64_mulaw_audio..."
  }
}

// Arrêt
{
  "event": "stop"
}
```

**Messages Serveur → Twilio:**
```json
// Envoyer audio au technicien
{
  "event": "media",
  "streamSid": "MZxxxx",
  "media": {
    "payload": "base64_mulaw_audio..."
  }
}
```

#### POST `/twilio/status`
Callback pour mises à jour de statut d'appel

Reçoit: CallSid, CallStatus, Direction, etc.

#### GET `/twilio/call-status/<call_sid>`
Obtenir le statut actuel d'un appel

## Configuration

### Variables d'Environnement

Ajouter au fichier `.env`:

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+15551234567

# Optional: Pour WebSocket public URL
TWILIO_WEBSOCKET_URL=https://votredomaine.com

# Optional: API Keys
TWILIO_API_KEY_SID=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY_SECRET=your_api_key_secret
```

### Installation des Dépendances

```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
pip install -r requirements.txt
```

Nouvelles dépendances ajoutées:
- `twilio` - SDK Twilio
- `pyannote.audio` - Speaker diarization (optionnel pour version avancée)

## Utilisation

### 1. Interface Web

**URL:** `http://localhost:8000/demo/twilio-technician`

**Étapes:**
1. Entrer le nom du technicien
2. Entrer l'ID technicien
3. Entrer le numéro de téléphone (format international: +33...)
4. Cliquer sur le bouton vert 📞 pour initier l'appel
5. Le technicien reçoit l'appel sur son téléphone
6. Parler du problème → transcription apparaît en temps réel
7. Cliquer sur le bouton rouge ✖️ pour terminer

### 2. API Programmatique

```python
import requests

# Initier un appel
response = requests.post('http://localhost:8000/twilio/initiate-call', json={
    'phone_number': '+33612345678',
    'technician_id': 'TECH001',
    'technician_name': 'Jean Dupont',
    'session_id': 'session_123'
})

call_data = response.json()
call_sid = call_data['call_sid']

# Plus tard: Terminer l'appel
requests.post('http://localhost:8000/twilio/end-call', json={
    'call_sid': call_sid,
    'session_id': 'session_123'
})
```

### 3. Obtenir Suggestions en Temps Réel

```python
# Polling pour nouvelles suggestions
response = requests.get(
    'http://localhost:8000/demo/get-session-suggestions',
    params={'session_id': 'session_123', 'limit': 10}
)

suggestions = response.json()['suggestions']

for suggestion in suggestions:
    if suggestion['type'] == 'knowledge_base':
        print(f"Solution: {suggestion['content']}")
    elif suggestion['type'] == 'clarification_question':
        print(f"Question: {suggestion['content']}")
```

## Flux de Traitement

### Scénario: Technicien Appelle pour un Problème

```
1. INITIATION
   - Frontend appelle /twilio/initiate-call
   - TwilioAudioService démarre l'appel
   - Twilio appelle le numéro du technicien
   - TwiML dit: "Bonjour, veuillez décrire le problème"

2. CONNEXION
   - Technicien répond
   - Twilio établit WebSocket vers /twilio/media-stream
   - Stream démarre (event: "start")

3. ÉCOUTE DU TECHNICIEN
   - Technicien parle: "Ma caméra ne s'enregistre pas depuis hier"
   - Audio → Twilio → WebSocket → TwilioAudioService
   - Conversion mulaw 8kHz → PCM 16kHz
   - Buffering dans TwilioAudioService (accumule 1 seconde)

4. TRANSCRIPTION
   - Buffer envoyé à EnhancedTranscriptionService
   - Buffer accumule 3 secondes
   - SpeakerDiarizationService identifie: "technician"
   - VAD confirme: activité vocale détectée
   - should_process_segment() → True (technicien, 3s)
   - Création fichier WAV
   - Whisper API transcrit: "Ma caméra ne s'enregistre pas depuis hier"

5. ANALYSE IA
   - Transcription envoyée à Agent Orchestrator
   - Context Analyzer analyse le contexte
   - Conversation = 7 mots → pas assez de contexte
   - Décision: needs_clarification = True

6. GÉNÉRATION DE QUESTION
   - Clarification Agent génère:
     "Pouvez-vous vérifier si la caméra est bien connectée au réseau?"
   - Suggestion stockée en DB
   - Frontend poll et affiche la question

7. TECHNICIEN RÉPOND
   - "Oui, elle est connectée au réseau"
   - Même flux: Audio → Transcription → Analyse
   - Contexte maintenant: 15 mots + entité détectée (réseau)
   - Context Analyzer: has_sufficient_context = True

8. RECHERCHE DE SOLUTION
   - Query Formulator crée: "Camera not recording but connected to network"
   - RAG Engine cherche dans Qdrant
   - Trouve: "Camera Recordings Not Visible - Subscription Active"
   - Score: 62.6%
   - LLM génère réponse en français
   - Solution affichée sur interface

9. FIN D'APPEL
   - Frontend appelle /twilio/end-call
   - TwilioAudioService termine l'appel
   - EnhancedTranscriptionService.end_session()
   - Statistiques retournées:
     {
       "total_segments": 8,
       "speakers": {
         "TECH001": {"segment_count": 6, "role": "technician"}
       }
     }
```

## Priorisation du Technicien

### Pourquoi?
L'objectif est de comprendre le problème décrit par le technicien, pas d'écouter les réponses du système IA.

### Comment?

#### 1. Identification de Speaker
```python
# Chaque segment audio est identifié
speaker_info = {
    'speaker_id': 'TECH001',
    'speaker_role': 'technician',  # ← Crucial
    'speaker_name': 'Jean Dupont'
}
```

#### 2. Filtrage par Rôle
```python
# Dans enhanced_transcription_service.py
if speaker_role != 'technician':
    logger.debug(f"Skipping agent processing for {speaker_role}")
    return  # Ne pas envoyer aux agents IA
```

#### 3. Seuils de Durée Différents
```python
# Dans speaker_diarization_service.py
def should_process_segment(session_id, speaker_role, segment_duration):
    if speaker_role == 'technician':
        return segment_duration >= 0.5  # Traiter segments courts

    if speaker_role == 'support_agent':
        return segment_duration >= 1.0  # Seuil plus élevé

    return False  # Ignorer inconnus
```

#### 4. Priorisation dans File
```python
# Si plusieurs segments en attente
def prioritize_technician_speech(session_id, segments):
    technician_segments = [s for s in segments if s['speaker_role'] == 'technician']
    other_segments = [s for s in segments if s['speaker_role'] != 'technician']

    return technician_segments + other_segments  # Technicien en premier
```

## Analyse de Contexte

### Détermination: Assez de Contexte?

Le système utilise `Context Analyzer Agent` pour décider:

**Critères pour "contexte suffisant":**

```python
conversation_word_count = len(conversation.split())
has_entities = len(detected_entities) > 0
has_issue = detected_issue != ""

# Règles:
if conversation_word_count > 30:
    has_sufficient_context = True  # Conversation longue → chercher solution

elif conversation_word_count > 15 and (has_entities or has_issue):
    has_sufficient_context = True  # Conversation moyenne + entités

elif conversation_word_count > 10 and has_issue:
    has_sufficient_context = True  # Problème identifié

else:
    needs_clarification = True  # Pas assez d'info → poser question
```

**Si contexte suffisant:**
→ RAG Engine cherche dans base de connaissances
→ Affiche solution

**Si contexte insuffisant:**
→ Clarification Agent génère question
→ Affiche question au technicien

## Formats Audio

### Twilio
- **Format:** G.711 μ-law (mulaw)
- **Sample rate:** 8000 Hz
- **Channels:** Mono (1)
- **Encoding:** 8-bit
- **Transport:** Base64 dans JSON via WebSocket

### Whisper (OpenAI)
- **Format:** WAV PCM
- **Sample rate:** 16000 Hz
- **Channels:** Mono (1)
- **Sample width:** 16-bit
- **Transport:** Fichier WAV via HTTP POST

### Conversion
```python
# Twilio → Whisper
mulaw_8k → PCM_8k (audioop.ulaw2lin)
         → PCM_16k (audioop.ratecv)
         → WAV file

# Whisper/IA → Twilio
PCM_16k → PCM_8k (audioop.ratecv)
        → mulaw_8k (audioop.lin2ulaw)
        → Base64
```

## Tests et Débogage

### Test Local (sans téléphone réel)

1. **Utiliser ngrok pour webhook public:**
```bash
ngrok http 8000
# URL: https://abc123.ngrok.io
```

2. **Configurer TWILIO_WEBSOCKET_URL:**
```bash
export TWILIO_WEBSOCKET_URL=https://abc123.ngrok.io
```

3. **Démarrer serveur:**
```bash
python app.py
```

4. **Tester avec numéro Twilio de test:**
- Numéros de test ne facturent pas
- Configurables dans console Twilio

### Logs de Débogage

```python
# Activer logs détaillés
import logging
logging.basicConfig(level=logging.DEBUG)

# Vérifier:
# - Audio chunks reçus
# - Conversions audio
# - Transcriptions
# - Identifications speaker
# - Décisions agent
```

### Vérifier Twilio Console

https://console.twilio.com/

- **Calls:** Voir tous les appels
- **Logs:** Debug webhook errors
- **TwiML Bins:** Tester TwiML

### Common Issues

#### WebSocket ne se connecte pas
```
Problème: Twilio ne peut pas atteindre /twilio/media-stream
Solution: Vérifier TWILIO_WEBSOCKET_URL est public (ngrok)
```

#### Audio déformé/haché
```
Problème: Conversion audio incorrecte
Solution: Vérifier sample rates (8kHz ↔ 16kHz)
```

#### Pas de transcription
```
Problème: Buffer trop court ou VAD trop strict
Solution: Réduire buffer_duration ou vad_threshold
```

#### Toujours des questions, pas de solutions
```
Problème: Context Analyzer trop conservateur
Solution: Vérifier seuils dans context_analyzer_agent.py
```

## Prochaines Améliorations

### Court Terme
- [ ] Text-to-Speech pour réponses vocales automatiques
- [ ] Support multi-langue (auto-détection)
- [ ] Webhooks pour événements (appel démarré, terminé, etc.)
- [ ] Dashboard temps réel pour superviseurs

### Moyen Terme
- [ ] Speaker diarization avancé avec pyannote.audio
- [ ] Enregistrement des appels complets
- [ ] Analytics: durée moyenne, taux de résolution, etc.
- [ ] Intégration CRM (lier appels aux tickets)

### Long Terme
- [ ] IA vocale conversationnelle (dialogue complet)
- [ ] Reconnaissance d'émotions (frustration, urgence)
- [ ] Routage intelligent vers humain si nécessaire
- [ ] Base de connaissances auto-apprenante

## Support et Documentation

### Fichiers Créés

1. **Services:**
   - `app/services/twilio_audio_service.py` - Gestion audio Twilio
   - `app/services/speaker_diarization_service.py` - Identification speakers
   - `app/services/enhanced_transcription_service.py` - Transcription améliorée

2. **Config:**
   - `app/config/twilio_config.py` - Configuration Twilio

3. **Routes:**
   - `app/api/twilio_routes.py` - Endpoints Twilio

4. **Frontend:**
   - `app/frontend/templates/demo/twilio_technician.html` - Interface d'appel

5. **Documentation:**
   - `requirements.txt` - Dépendances mises à jour
   - Ce fichier - Guide complet

### Ressources Externes

- **Twilio Docs:** https://www.twilio.com/docs/voice
- **Twilio Media Streams:** https://www.twilio.com/docs/voice/twiml/stream
- **Whisper API:** https://platform.openai.com/docs/guides/speech-to-text
- **Flask-Sock:** https://flask-sock.readthedocs.io/

## Conclusion

Le système d'appel bidirectionnel offre:
- ✅ Communication téléphonique naturelle
- ✅ Compréhension intelligente du contexte
- ✅ Priorisation automatique du technicien
- ✅ Solutions instantanées ou questions pertinentes
- ✅ Scalable et extensible

Le technicien peut appeler depuis n'importe où, décrire son problème, et recevoir de l'aide immédiate basée sur la base de connaissances, le tout sans interface complexe - juste un appel téléphonique.
