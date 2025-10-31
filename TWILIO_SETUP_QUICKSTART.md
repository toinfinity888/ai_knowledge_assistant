# Démarrage Rapide: Appels Bidirectionnels Twilio

## Configuration en 5 Minutes

### Étape 1: Installer les Dépendances

```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
pip install -r requirements.txt
```

### Étape 2: Configurer Twilio

1. **Créer un compte Twilio:**
   - Aller sur https://www.twilio.com/try-twilio
   - S'inscrire (essai gratuit disponible)

2. **Obtenir les credentials:**
   - Dashboard → Account → Settings
   - Copier: **Account SID** et **Auth Token**

3. **Acheter/Obtenir un numéro de téléphone:**
   - Dashboard → Phone Numbers → Buy a number
   - Choisir un numéro avec capacité **Voice**
   - Pour test: Numéros gratuits disponibles en trial

### Étape 3: Configurer Variables d'Environnement

Ajouter au fichier `.env`:

```bash
# Twilio Credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+15551234567

# Pour développement local: exposer via ngrok
TWILIO_WEBSOCKET_URL=http://localhost:8000
```

### Étape 4: Exposer Webhook (Développement Local)

Twilio a besoin d'une URL publique pour les webhooks:

```bash
# Installer ngrok
brew install ngrok  # macOS
# ou télécharger depuis https://ngrok.com/download

# Démarrer ngrok
ngrok http 8000

# Copier l'URL HTTPS (ex: https://abc123.ngrok.io)
# Mettre à jour .env:
TWILIO_WEBSOCKET_URL=https://abc123.ngrok.io
```

### Étape 5: Démarrer le Serveur

```bash
python app.py
```

### Étape 6: Tester l'Interface

1. **Ouvrir dans navigateur:**
   ```
   http://localhost:8000/demo/twilio-technician
   ```

2. **Remplir le formulaire:**
   - Nom: Jean Dupont
   - ID: TECH001
   - Téléphone: +33612345678 (VOTRE numéro)

3. **Cliquer sur le bouton vert 📞**

4. **Répondre à l'appel sur votre téléphone**

5. **Parler:** "Ma caméra ne s'enregistre pas"

6. **Observer:** Transcription apparaît en temps réel

7. **Fin:** Cliquer sur bouton rouge ✖️

## Vérification Rapide

### Test 1: Credentials Twilio

```python
from twilio.rest import Client

account_sid = "ACxxxx"
auth_token = "your_token"
client = Client(account_sid, auth_token)

# Test: lister vos numéros
numbers = client.incoming_phone_numbers.list()
print(f"Numéros disponibles: {len(numbers)}")
```

### Test 2: Webhook Accessible

```bash
# Vérifier que ngrok fonctionne
curl https://abc123.ngrok.io/twilio/test-twiml

# Devrait retourner du XML TwiML
```

### Test 3: OpenAI Whisper

```python
from openai import OpenAI
client = OpenAI()

# Votre clé OpenAI doit être configurée
# OPENAI_API_KEY dans .env
```

## Configuration Production

### Hébergement avec URL Publique

Si vous déployez sur un serveur avec domaine public:

```bash
# Mettre à jour .env
TWILIO_WEBSOCKET_URL=https://votredomaine.com

# Pas besoin de ngrok
```

### Configurer Webhooks dans Twilio Console

1. Aller sur https://console.twilio.com/
2. Phone Numbers → Manage → Active numbers
3. Cliquer sur votre numéro
4. Configurer:
   - **Voice & Fax → Configure with:** Webhooks/TwiML
   - **A call comes in:** `https://votredomaine.com/twilio/incoming` (optionnel)
   - **Call status changes:** `https://votredomaine.com/twilio/status`

### WebSocket avec SSL

Pour production, assurez-vous d'avoir SSL/TLS:

```bash
# Avec nginx + Let's Encrypt
server {
    listen 443 ssl;
    server_name votredomaine.com;

    location /twilio/media-stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Troubleshooting Rapide

### Erreur: "Account SID not found"
```
Solution: Vérifier TWILIO_ACCOUNT_SID dans .env
```

### Erreur: "Phone number not found"
```
Solution: Vérifier que le numéro commence par + (format international)
```

### Erreur: "WebSocket connection failed"
```
Solution:
1. Vérifier que ngrok est actif
2. Vérifier TWILIO_WEBSOCKET_URL pointe vers ngrok URL
3. Vérifier pas de firewall bloquant
```

### Erreur: "No transcription"
```
Solution:
1. Vérifier OPENAI_API_KEY configuré
2. Parler plus fort/plus longtemps (min 1 seconde)
3. Vérifier logs: python app.py
```

### Pas de solution, seulement questions
```
Solution:
1. Parler plus longuement (15+ mots)
2. Mentionner le problème clairement: "caméra ne s'enregistre pas"
3. Vérifier base Qdrant a des articles: python verify_and_load.py
```

## Commandes Utiles

```bash
# Vérifier status Twilio
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID.json" \
  -u "$TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN"

# Lister appels récents
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID/Calls.json?PageSize=10" \
  -u "$TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN"

# Tester endpoint localement
curl -X POST http://localhost:8000/twilio/initiate-call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+33612345678",
    "technician_id": "TEST",
    "technician_name": "Test",
    "session_id": "test-123"
  }'
```

## Prochaines Étapes

Après avoir testé avec succès:

1. **Personnaliser les données technicien** dans l'interface
2. **Ajouter plus d'articles** à la base de connaissances
3. **Tester différents scénarios** de problèmes
4. **Configurer TTS** pour réponses vocales automatiques
5. **Intégrer avec votre CRM** existant

## Support

- **Documentation complète:** [TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md](TWILIO_BIDIRECTIONAL_CALLING_GUIDE.md)
- **Twilio Support:** https://www.twilio.com/help
- **Logs système:** Vérifier sortie de `python app.py`

## Coûts Twilio (Référence)

**Mode Trial:**
- Gratuit pour tests
- Numéros limités

**Mode Production:**
- Numéro de téléphone: ~1€/mois
- Appels entrants: ~0.01€/minute
- Appels sortants: ~0.05€/minute
- WebSocket/Media Streams: inclus

Prix approximatifs pour France, vérifier tarifs actuels sur Twilio.

Avec 100 appels/mois de 5 minutes chacun:
- Coût estimé: ~30€/mois
