# Démarrage du Serveur - Guide Rapide

## ✅ Le serveur est maintenant en cours d'exécution!

### État Actuel

```
✓ Serveur Flask: http://localhost:8000
✓ Routes Twilio: Enregistrées
✓ Ngrok: Actif (exposant localhost:8000)
✓ Tous les composants IA: Initialisés
```

## 🌐 Interfaces Disponibles

### 1. Interface Twilio (Appels Bidirectionnels)
**URL:** http://localhost:8000/demo/twilio-technician

**Fonctionnalités:**
- Initiation d'appels téléphoniques vers techniciens
- Transcription en temps réel
- Speaker diarization (identification locuteurs)
- Solutions IA basées sur la conversation

### 2. Interface Technicien (3 Colonnes)
**URL:** http://localhost:8000/demo/technician

**Fonctionnalités:**
- Vue complète: technicien, chantier, solutions
- Chat avec IA
- Contrôles d'appel
- Design professionnel

### 3. Interface Demo Simple
**URL:** http://localhost:8000/demo/

**Fonctionnalités:**
- Reconnaissance vocale navigateur
- Test rapide sans Twilio
- Séparation solutions/questions

## 🚀 Démarrage

### Démarrage Automatique

```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
PORT=8000 python main.py
```

### Vérification

```bash
# Test serveur
curl http://localhost:8000/demo/

# Test Twilio routes
curl http://localhost:8000/twilio/test-twiml
```

### Configuration Ngrok

Si vous utilisez ngrok pour exposer votre serveur:

```bash
# Dans un autre terminal
ngrok http 8000

# Copier l'URL HTTPS (ex: https://abc123.ngrok.io)
# Mettre à jour .env:
TWILIO_WEBSOCKET_URL=https://abc123.ngrok.io
```

## 📋 Endpoints API

### Twilio
```
POST   /twilio/initiate-call       - Démarrer un appel
POST   /twilio/end-call             - Terminer un appel
GET    /twilio/call-status/<sid>    - Statut d'appel
POST   /twilio/status               - Webhook statut
WS     /twilio/media-stream         - Stream audio WebSocket
GET    /twilio/test-twiml           - Test TwiML
```

### Demo/Testing
```
GET    /demo/                       - Interface simple
GET    /demo/technician             - Interface 3 colonnes
GET    /demo/twilio-technician      - Interface Twilio
POST   /demo/start-demo-call        - Démarrer session
POST   /demo/send-demo-transcription - Envoyer transcription
POST   /demo/end-demo-call          - Terminer session
GET    /demo/get-session-suggestions - Obtenir suggestions
```

### API Temps Réel
```
POST   /api/realtime/call/start     - Démarrer session
POST   /api/realtime/call/end       - Terminer session
POST   /api/realtime/transcription  - Envoyer transcription
GET    /api/realtime/suggestions/<session_id> - Suggestions
WS     /api/realtime/ws/<session_id> - WebSocket temps réel
```

## 🔧 Logs et Débogage

### Voir les Logs en Temps Réel

Les logs s'affichent dans le terminal où vous avez lancé `python main.py`

**Informations affichées:**
- Initialisation des composants
- Requêtes HTTP entrantes
- Transcriptions reçues
- Décisions des agents IA
- Résultats de recherche RAG
- Erreurs et warnings

### Arrêter le Serveur

```bash
# Trouver le processus
ps aux | grep "python main.py"

# Tuer le processus
kill <PID>

# Ou si lancé au premier plan
CTRL+C
```

### Redémarrage Rapide

```bash
# Arrêter serveur existant
pkill -f "python main.py"

# Redémarrer
PORT=8000 python main.py
```

## 📊 Composants Initialisés

Quand le serveur démarre, vous verrez:

```
✓ Twilio routes registered
✓ Call Session Manager ready
✓ RAG Engine ready
✓ LLM ready (OpenAI GPT-4o)
✓ Agent Orchestrator ready
  - Context Analyzer Agent
  - Query Formulation Agent
  - Clarification Agent
✓ Transcription Service ready
✓ Database tables created/verified
```

## 🌍 Variables d'Environnement Requises

### Minimum (pour tests sans Twilio)
```bash
OPENAI_API_KEY=sk-proj-xxxxx
QDRANT_URL=https://xxxxx.cloud.qdrant.io:6333
QDRANT_API_KEY=xxxxx
DATABASE_URL=postgresql://user:pass@localhost:5432/db
```

### Complet (avec Twilio)
```bash
# OpenAI
OPENAI_API_KEY=sk-proj-xxxxx

# Qdrant
QDRANT_URL=https://xxxxx.cloud.qdrant.io:6333
QDRANT_API_KEY=xxxxx

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/db

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+15551234567
TWILIO_WEBSOCKET_URL=https://your-ngrok-url.ngrok.io  # ou votre domaine

# Optionnel
PORT=8000
```

## ⚠️ Problèmes Courants

### Port Déjà Utilisé
```bash
# Error: Address already in use
# Solution:
lsof -ti:8000 | xargs kill -9
```

### Module Twilio Non Trouvé
```bash
# Error: No module named 'twilio'
# Solution:
pip install twilio
```

### Base de Données Non Accessible
```bash
# Error: could not connect to server
# Solution: Vérifier DATABASE_URL dans .env
# Ou démarrer PostgreSQL:
brew services start postgresql  # macOS
```

### Qdrant Non Accessible
```bash
# Error: Failed to connect to Qdrant
# Solution: Vérifier QDRANT_URL et QDRANT_API_KEY
```

## 🧪 Tests Rapides

### Test 1: Serveur Fonctionne
```bash
curl http://localhost:8000/demo/
# Devrait retourner HTML
```

### Test 2: Twilio Routes
```bash
curl http://localhost:8000/twilio/test-twiml
# Devrait retourner XML TwiML
```

### Test 3: Base de Connaissances
```bash
python test_direct_query.py
# Devrait retourner des solutions
```

### Test 4: Interface Web
Ouvrir dans navigateur:
```
http://localhost:8000/demo/twilio-technician
```

## 📚 Documentation Complète

- **Guide Twilio:** [TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md](TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md)
- **Démarrage Rapide:** [TWILIO_SETUP_QUICKSTART.md](TWILIO_SETUP_QUICKSTART.md)
- **Résumé Fonctionnalités:** [SYSTEM_FEATURES_SUMMARY.md](SYSTEM_FEATURES_SUMMARY.md)
- **Interface 3 Colonnes:** [TECHNICIAN_INTERFACE_DOCUMENTATION.md](TECHNICIAN_INTERFACE_DOCUMENTATION.md)

## 🎯 Prochaines Étapes

1. ✅ Serveur démarré
2. ⏳ Configurer credentials Twilio dans .env
3. ⏳ Tester interface Twilio
4. ⏳ Faire un appel test
5. ⏳ Vérifier transcription et solutions

## 💡 Conseils

- **Développement:** Utilisez ngrok pour exposer localhost
- **Production:** Utilisez un domaine avec SSL/TLS
- **Logs:** Gardez un terminal ouvert pour voir les logs
- **Tests:** Commencez par l'interface demo simple
- **Debug:** Vérifiez les logs en cas de problème

---

**Serveur actuellement en cours d'exécution sur:** http://localhost:8000
**Dernière mise à jour:** 2025-10-30
