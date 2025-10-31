# 🤖 AI Support Assistant - Système d'Assistance en Temps Réel

Assistant IA intelligent pour support technique avec appels téléphoniques bidirectionnels, transcription en temps réel, et solutions automatiques basées sur une base de connaissances vectorielle.

## ✨ Fonctionnalités Principales

### 🎯 Nouveautés v2.0

- **📞 Appels Bidirectionnels Twilio** - Communication téléphonique naturelle
- **🎤 Speaker Diarization** - Identification automatique des locuteurs
- **🧠 Priorisation Intelligente** - Focus sur la parole du technicien
- **🌍 Support Multi-Langue** - 15 langues supportées
- **📊 Interfaces Multiples** - 3 interfaces web professionnelles

### 🔄 Workflow Complet

```
Appel Téléphone → Streaming Audio → Transcription → Analyse IA → Solutions
     Twilio           WebSocket        Whisper         GPT-4o        RAG
```

## 🚀 Démarrage Rapide

### 1. Installation

```bash
git clone [votre-repo]
cd ai_knowledge_assistant
pip install -r requirements.txt
```

### 2. Configuration

Créer un fichier `.env` avec vos credentials:

```bash
cp .env.example .env
nano .env
```

**Variables requises:**
```bash
OPENAI_API_KEY=sk-proj-xxxxx
QDRANT_URL=https://xxxxx.cloud.qdrant.io:6333
QDRANT_API_KEY=xxxxx
DATABASE_URL=postgresql://user:pass@localhost:5432/db
```

### 3. Démarrer le Serveur

```bash
PORT=8000 python main.py
```

Serveur disponible sur `http://localhost:8000`

### 4. Interfaces Disponibles

- **Twilio:** http://localhost:8000/demo/twilio-technician
- **3 Colonnes:** http://localhost:8000/demo/technician
- **Simple:** http://localhost:8000/demo/

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [START_SERVER.md](START_SERVER.md) | Guide démarrage serveur |
| [SYSTEM_FEATURES_SUMMARY.md](SYSTEM_FEATURES_SUMMARY.md) | Résumé fonctionnalités complètes |
| [TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md](TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md) | Guide Twilio complet |
| [TWILIO_SETUP_QUICKSTART.md](TWILIO_SETUP_QUICKSTART.md) | Setup Twilio en 5 minutes |

## 📊 Composants

- **Agents IA:** 4 (Context Analyzer, Query Formulator, Clarification, Orchestrator)
- **Services:** 6 (Twilio Audio, Speaker Diarization, Transcription, etc.)
- **Interfaces:** 3 (Twilio, 3 Colonnes, Simple)
- **Endpoints API:** 15+
- **Langues:** 15

## 🔧 Stack Technique

**Backend:** Python, Flask, Twilio SDK, OpenAI API, SQLAlchemy, Qdrant
**Frontend:** HTML5/CSS3/JavaScript, WebSocket, Web Speech API
**Infrastructure:** PostgreSQL, Qdrant Cloud, Twilio Cloud

---

**Version:** 2.0
**Status:** ✅ Production Ready
