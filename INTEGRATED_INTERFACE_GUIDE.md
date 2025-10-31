# Guide: Interface Intégrée Technicien avec Appels Twilio

## Vue d'Ensemble

L'interface `technician_support.html` est maintenant **complètement intégrée** avec la fonctionnalité d'appels bidirectionnels Twilio. C'est une interface professionnelle tout-en-un qui combine:

- ✅ **Informations contextuelles** (technicien + chantier)
- ✅ **Appels téléphoniques réels** via Twilio
- ✅ **Transcription en temps réel** avec speaker diarization
- ✅ **Chat interactif** avec l'IA
- ✅ **Solutions automatiques** basées sur RAG

## 🚀 Accès

**URL:** http://localhost:8000/demo/technician

## 📱 Architecture de l'Interface

### 3 Colonnes Professionnelles

```
┌──────────────┬───────────────────┬──────────────────────┐
│   Colonne 1  │     Colonne 2     │      Colonne 3       │
│              │                   │                      │
│  Technicien  │  Contrôles Call   │     Solutions        │
│  ┌─────────┐ │  ┌──────────────┐ │  ┌────────────────┐ │
│  │  Info   │ │  │   Timer      │ │  │  Diagnostic    │ │
│  │  Avatar │ │  │   Mute/End   │ │  │  & Solutions   │ │
│  │  Tel    │ │  │   Waveform   │ │  │                │ │
│  │ [Appeler]│ │  └──────────────┘ │  │  - Solution 1  │ │
│  └─────────┘ │                   │  │  - Solution 2  │ │
│              │  Chatbot IA       │  │  - ...         │ │
│  Chantier    │  ┌──────────────┐ │  └────────────────┘ │
│  ┌─────────┐ │  │  Messages    │ │                      │
│  │ Client  │ │  │  🤖  Bot     │ │                      │
│  │ Équipt  │ │  │  👤  User    │ │                      │
│  │ History │ │  │              │ │                      │
│  └─────────┘ │  │ [Input]  [➤] │ │                      │
│              │  └──────────────┘ │                      │
└──────────────┴───────────────────┴──────────────────────┘
```

## 🎯 Fonctionnalités Intégrées

### Colonne 1: Contexte Complet

#### Section Technicien (Haut)
- **Avatar** avec initiales
- **Nom** et badge d'expérience
- **Localisation** actuelle
- **Chantier assigné**
- **Heure d'arrivée prévue**
- **📞 Numéro de téléphone** (input)
- **Bouton "Appeler le Technicien"** (appel Twilio)
- **Statut de l'appel** (messages dynamiques)

#### Section Chantier (Bas)
- **Informations client:**
  - Avatar de l'entreprise/résidence
  - Nom du site
  - Client depuis X années
  - Installateur initial

- **Abonnement:**
  - Type (Premium, Standard, etc.)
  - Nombre de caméras

- **Équipement installé:**
  - Liste détaillée avec quantités
  - Icons pour chaque type

- **Historique:**
  - Dernier incident
  - Notes importantes

### Colonne 2: Communication

#### Section Contrôles (Haut)
- **Timer d'appel** en temps réel
- **Statut:** En ligne / En sourdine / Terminé
- **Boutons:**
  - 🎤 Mute/Unmute (désactivé jusqu'à l'appel)
  - 📞 Terminer (désactivé jusqu'à l'appel)
- **Forme d'onde audio** animée (8 barres)

#### Section Chatbot (Bas)
- **En-tête:**
  - "Assistant IA" avec icône
  - Indicateur d'écoute active (point pulsant)

- **Messages:**
  - Messages bot (gauche, fond blanc)
  - Messages utilisateur (droite, fond violet)
  - Scroll automatique
  - Tracking des IDs pour éviter doublons

- **Input:**
  - Champ de saisie texte
  - Bouton d'envoi
  - Support touche Entrée

### Colonne 3: Intelligence

- **En-tête:**
  - "Diagnostic et Solutions"
  - Sous-titre contextuel

- **État vide:**
  - Icône de recherche
  - Message d'attente
  - Instructions

- **Cartes de solution:**
  - Fond vert clair, bordure verte
  - Titre en vert foncé
  - Contenu détaillé
  - Badge de confiance (%)
  - Insertion en haut de liste (plus récentes d'abord)

## 🔄 Workflow Utilisateur

### 1. Initialisation de Page

```javascript
// Au chargement:
1. Génère session ID unique
2. Initialise l'interface (sans appel)
3. Boutons contrôles désactivés
4. Prêt à recevoir numéro téléphone
```

### 2. Initiation d'Appel Twilio

**Actions utilisateur:**
1. Entre numéro de téléphone: `+33612345678`
2. Clique sur "📞 Appeler le Technicien"

**Système:**
```javascript
// Validation
if (!phoneNumber.startsWith('+')) {
    showCallStatus('Format international requis', 'error');
    return;
}

// POST /twilio/initiate-call
{
  phone_number: "+33612345678",
  technician_id: "TECH1234567890",
  technician_name: "Jean Dupont",
  session_id: "session-1234567890"
}

// Réponse
{
  success: true,
  call_sid: "CAxxxxxxxxxxxxx",
  session_id: "session-1234567890",
  status: "initiated"
}
```

**UI Updates:**
- Bouton devient "✓ Appel connecté" (désactivé)
- Bouton Mute activé
- Bouton Terminer activé
- Timer démarre (00:00, 00:01, 00:02...)
- Status: "Appel connecté - Transcription en cours" (vert)
- Polling démarre (toutes les 3 secondes)

### 3. Conversation en Cours

**Côté Twilio (automatique):**
```
Téléphone technicien
    ↓
Twilio reçoit audio
    ↓
WebSocket → /twilio/media-stream
    ↓
TwilioAudioService (conversion audio)
    ↓
SpeakerDiarizationService (identification)
    ↓
EnhancedTranscriptionService (Whisper)
    ↓
Agent Orchestrator (analyse)
    ↓
RAG Engine ou Clarification Agent
    ↓
Suggestions sauvegardées en DB
```

**Côté Interface (polling):**
```javascript
// Toutes les 3 secondes
GET /demo/get-session-suggestions?session_id=xxx&limit=20

// Réponse
{
  suggestions: [
    {
      id: 123,
      type: "knowledge_base",
      title: "Camera Recording Issues",
      content: "If your camera...",
      confidence: 0.85
    },
    {
      id: 124,
      type: "clarification_question",
      title: "Need More Info",
      content: "Can you confirm if...",
      confidence: 0.90
    }
  ]
}
```

**UI Updates:**
- **Solutions** (type: knowledge_base) → Colonne 3
- **Questions** (type: clarification_question) → Chat (bot message)
- Nouvelles questions uniquement (pas de doublons via data-suggestion-id)
- Animation d'apparition (délai 500ms entre messages)

### 4. Interaction Chat

**Utilisateur tape dans le chat:**
```
"Oui, la caméra est bien connectée"
```

**Système:**
```javascript
// POST /demo/send-demo-transcription
{
  session_id: "session-xxx",
  speaker: "customer",
  text: "Oui, la caméra est bien connectée",
  language: "fr",
  confidence: 1.0
}

// Traitement identique à transcription Twilio:
// → Agent Orchestrator
// → Context Analyzer
// → RAG ou Questions
```

**Résultat:**
- Message user affiché (chat, droite)
- Si contexte suffisant → Solution apparaît (colonne 3)
- Sinon → Nouvelle question bot (chat, gauche)

### 5. Fin d'Appel

**Utilisateur clique "📞 Terminer":**

```javascript
// Confirmation
if (!confirm('Terminer l\'appel?')) return;

// POST /twilio/end-call
{
  call_sid: "CAxxxxxxxxxxxxx",
  session_id: "session-xxx"
}

// Réponse
{
  success: true,
  call_sid: "CAxxxxx",
  status: "completed",
  duration: 120,
  session_stats: {
    total_segments: 15,
    speakers: {
      "TECH123": {
        segment_count: 12,
        speaker_role: "technician"
      }
    }
  }
}
```

**UI Updates:**
- Timer arrêté
- Polling arrêté
- Status: "● Terminé"
- Bouton Terminer désactivé
- Bouton Appeler réactivé
- Message: "Appel terminé" (vert)
- Statistiques dans console (pour analyse)

## 🎨 Design

### Couleurs

**Primaire:**
- Violet gradient: `#667eea` → `#764ba2`
- Vert (succès): `#4caf50`, `#2e7d32`
- Rouge (fin): `#e74c3c`, `#c0392b`

**Secondaire:**
- Fond page: `#f5f7fa`
- Cartes: `white`
- Chat bot: `white`
- Chat user: `#667eea`

**Status:**
- Succès: `#e8f5e9` / `#2e7d32`
- Erreur: `#ffebee` / `#c62828`
- Progress: `#fff3e0` / `#e65100`

### Animations

```css
@keyframes wave {
    0%, 100% { height: 20px; }
    50% { height: 50px; }
}

@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```

## 🔧 Configuration Requise

### Variables d'Environnement

```bash
# OpenAI (requis)
OPENAI_API_KEY=sk-proj-xxxxx

# Qdrant (requis)
QDRANT_URL=https://xxxxx.cloud.qdrant.io:6333
QDRANT_API_KEY=xxxxx

# PostgreSQL (requis)
DATABASE_URL=postgresql://user:pass@localhost:5432/db

# Twilio (pour appels)
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+15551234567
TWILIO_WEBSOCKET_URL=https://your-ngrok-url.ngrok.io
```

### Ngrok (Développement Local)

```bash
# Terminal 1: Démarrer serveur
PORT=8000 python main.py

# Terminal 2: Exposer avec ngrok
ngrok http 8000

# Copier URL HTTPS
# Mettre à jour .env:
TWILIO_WEBSOCKET_URL=https://abc123.ngrok.io

# Redémarrer serveur
```

## 🧪 Tests

### Test 1: Interface Sans Twilio

```bash
# Démarrer serveur
PORT=8000 python main.py

# Ouvrir navigateur
open http://localhost:8000/demo/technician

# Observer:
✓ Interface charge
✓ Session initialisée
✓ Bouton "Appeler" visible
✓ Contrôles désactivés
✓ Chat vide
✓ Solutions vides
```

### Test 2: Chat Manuel (Sans Appel)

```bash
# Dans le chat, taper:
"Ma caméra ne s'enregistre pas"

# Observer:
✓ Message apparaît (user, droite)
✓ Après 1-2s: question bot apparaît (gauche)
✓ Ou solution apparaît (colonne 3)
```

### Test 3: Appel Twilio Complet

```bash
# Prérequis: Twilio configuré, ngrok actif

# 1. Entrer VOTRE numéro: +33...
# 2. Cliquer "Appeler"
# 3. Répondre au téléphone
# 4. Parler: "Ma caméra ne marche pas"
# 5. Observer:
   ✓ Timer démarre
   ✓ Après ~5s: transcription apparaît (colonne 3)
   ✓ Question bot dans chat OU solution
# 6. Répondre par téléphone ou chat
# 7. Cliquer "Terminer"
# 8. Observer:
   ✓ Appel termine
   ✓ Statistiques en console
```

## 📊 État de l'Interface

### Variables JavaScript Globales

```javascript
sessionId        // "session-1234567890"
callSid          // "CAxxxxx" (Twilio call ID)
isMuted          // false / true
callStartTime    // Date.now() when call started
callTimer        // setInterval ID for timer
suggestionPollingTimer // setInterval ID for polling
currentLanguage  // "fr"
isCallActive     // false / true
```

### Timers Actifs

**callTimer:**
- Démarre: lors de l'appel
- Fréquence: 1 seconde
- Action: met à jour affichage timer
- Arrête: fin d'appel

**suggestionPollingTimer:**
- Démarre: lors de l'appel
- Fréquence: 3 secondes
- Action: récupère nouvelles suggestions
- Arrête: fin d'appel

## ⚡ Performance

### Latences

```
Appel Twilio → Transcription → Solution
     ~2s           ~3s            ~2s     = ~7s total

Breakdown:
- Twilio audio buffering: 1-2s
- Whisper transcription: 2-3s
- RAG recherche + LLM: 1-2s
- Polling délai: 0-3s (max)
```

### Optimisations

- **Polling:** 3 secondes (bon équilibre)
- **Buffering audio:** 3 secondes (qualité transcription)
- **Cache messages:** data-suggestion-id (pas de doublons)
- **Lazy loading:** solutions chargées à la demande

## 🐛 Troubleshooting

### Interface Ne Charge Pas

```bash
# Vérifier serveur
curl http://localhost:8000/demo/technician
# Devrait retourner HTML

# Vérifier console navigateur (F12)
# Rechercher erreurs JavaScript
```

### Bouton "Appeler" Ne Fonctionne Pas

```javascript
// Console navigateur:
Error: Failed to fetch

// Solution:
1. Vérifier serveur actif
2. Vérifier TWILIO_ACCOUNT_SID dans .env
3. Vérifier credentials Twilio valides
4. Tester endpoint:
   curl -X POST http://localhost:8000/twilio/initiate-call \
     -H "Content-Type: application/json" \
     -d '{"phone_number":"+33...", "session_id":"test"}'
```

### Pas de Transcription

```bash
# Vérifier ngrok actif
curl https://your-ngrok-url.ngrok.io/twilio/test-twiml

# Vérifier TWILIO_WEBSOCKET_URL
echo $TWILIO_WEBSOCKET_URL

# Vérifier logs serveur
# Rechercher: "Media stream started"
```

### Solutions N'Apparaissent Pas

```bash
# Vérifier base de connaissances
python verify_and_load.py

# Vérifier polling fonctionne
# Console navigateur → Network tab
# Voir requêtes GET /demo/get-session-suggestions

# Vérifier réponses contiennent suggestions
```

## 📚 Documentation Connexe

- **[TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md](TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md)** - Guide complet Twilio
- **[TWILIO_SETUP_QUICKSTART.md](TWILIO_SETUP_QUICKSTART.md)** - Setup Twilio rapide
- **[SYSTEM_FEATURES_SUMMARY.md](SYSTEM_FEATURES_SUMMARY.md)** - Toutes les fonctionnalités
- **[START_SERVER.md](START_SERVER.md)** - Démarrer le serveur

## 🎯 Prochaines Améliorations

### Court Terme
- [ ] Rendre champs technicien éditables (nom, localisation)
- [ ] Ajouter bouton "Recharger équipement"
- [ ] Historique des appels dans section chantier
- [ ] Export PDF des solutions proposées

### Moyen Terme
- [ ] Authentification utilisateur
- [ ] Intégration CRM (load données réelles)
- [ ] Webhooks pour notifications
- [ ] Dashboard superviseur (voir tous les appels)

### Long Terme
- [ ] Multi-tenant (plusieurs organisations)
- [ ] Analytics avancés (taux résolution, etc.)
- [ ] Recommandations proactives
- [ ] Base de connaissances personnalisée par client

---

**Version:** 2.0 Intégrée
**Dernière mise à jour:** 2025-10-30
**Status:** ✅ Production Ready (avec configuration Twilio)
