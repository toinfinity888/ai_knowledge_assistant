# Interface Support Technicien - Documentation

## Vue d'ensemble

Nouvelle interface professionnelle en 3 colonnes pour le support en temps réel des techniciens de terrain.

## Accès

**URL:** `http://localhost:8000/demo/technician`

## Structure de l'Interface

### 📱 Colonne 1 : Informations Technicien & Chantier

#### Section Haut : Technicien
- **Avatar** avec initiales
- **Nom complet** du technicien
- **Badge d'expérience** (ex: "Expert • 5 ans")
- **Détails:**
  - 📍 Localisation actuelle
  - 🏢 Chantier assigné
  - ⏰ Heure d'arrivée prévue

#### Section Bas : Chantier (Plus grande)
- **Informations client:**
  - Avatar de l'entreprise/résidence
  - Nom du site
  - Client depuis combien de temps
  - Qui a fait l'installation initiale

- **Abonnement:**
  - Type d'abonnement (Premium, Standard, etc.)
  - Nombre de caméras incluses

- **Équipement installé:**
  - Liste détaillée avec icônes
  - Quantités pour chaque type d'équipement
  - Exemples:
    - 🎥 Caméra extérieure HD × 6
    - 🎥 Caméra intérieure 360° × 4
    - 📡 Enregistreur NVR × 1
    - 🔌 Alimentation PoE × 2

- **Notes importantes:**
  - Historique des incidents
  - Dernière intervention
  - Alertes spéciales

### 🎙️ Colonne 2 : Contrôles d'Appel & Chatbot

#### Section Haut : Contrôles d'Appel
- **Durée de l'appel** (00:00 format)
- **Statut** (● En ligne / ● En sourdine / ● Terminé)
- **Boutons de contrôle:**
  - 🎤 Mute/Unmute (bouton toggle)
  - 📞 Raccrocher (bouton rouge)
- **Visualisation audio:** Forme d'onde animée (8 barres)

#### Section Bas : Chatbot IA (Plus grande)
- **En-tête:**
  - 🤖 Assistant IA
  - Indicateur d'écoute active (point pulsant vert)

- **Zone de messages:**
  - Messages bot (gauche, fond blanc, avatar 🤖)
  - Messages utilisateur (droite, fond violet, avatar 👤)
  - Défilement automatique
  - Barres de défilement stylisées

- **Zone de saisie:**
  - Input arrondi avec bordure
  - Bouton d'envoi circulaire (➤)
  - Support de la touche Entrée

### ✅ Colonne 3 : Diagnostic et Solutions

- **En-tête:**
  - Titre: "✅ Diagnostic et Solutions"
  - Sous-titre: "Basé sur l'analyse en temps réel de la conversation"

- **Contenu:**
  - **État vide:** Icône de recherche + message d'attente
  - **Cartes de solution:**
    - Fond vert clair avec bordure verte
    - Titre en vert foncé
    - Contenu détaillé
    - Badge de confiance (en pourcentage)

  - **Étapes de solution:**
    - Numéros d'étapes circulaires (gradient violet)
    - Description de chaque étape
    - Design clair et actionnable

## Fonctionnalités JavaScript

### Gestion de Session
```javascript
// Démarre automatiquement au chargement
startCall() - Crée une session avec le backend
updateCallDuration() - Met à jour le compteur toutes les secondes
```

### Contrôles d'Appel
```javascript
toggleMute() - Bascule mute/unmute
  - Change l'icône: 🎤 → 🔇
  - Change le statut: "En ligne" → "En sourdine"

endCall() - Termine l'appel
  - Demande confirmation
  - Arrête le timer
  - Envoie la fin de session au backend
```

### Chat & IA
```javascript
sendChatMessage() - Envoie un message
  - Ajoute le message à l'interface
  - Envoie au backend via /demo/send-demo-transcription
  - Reçoit les suggestions
  - Affiche les réponses du bot

displaySolutions() - Affiche les solutions
  - Filtre les suggestions de type 'knowledge_base'
  - Crée des cartes de solution
  - Ajoute au début de la liste
```

### Intégration Backend
```javascript
// Endpoints utilisés:
POST /demo/start-demo-call
POST /demo/send-demo-transcription
POST /demo/end-demo-call

// Format de données:
{
  session_id: string,
  speaker: 'customer',
  text: string,
  language: 'fr',
  confidence: 1.0
}
```

## Design et Style

### Palette de Couleurs
- **Violet principal:** `#667eea` → `#764ba2`
- **Rose:** `#f093fb` → `#f5576c`
- **Vert (solutions):** `#4caf50`, `#2e7d32`
- **Fond:** `#f5f7fa`
- **Texte principal:** `#2c3e50`
- **Texte secondaire:** `#7f8c8d`

### Gradients
- **Boutons primaires:** Violet → Violet foncé
- **Solutions:** Vert clair → Blanc
- **Abonnement:** Orange → Bleu foncé
- **Avatar technicien:** Violet dégradé
- **Avatar chantier:** Rose dégradé

### Animations
- **Forme d'onde:** Animation wave 1s avec délais progressifs
- **Indicateur d'écoute:** Pulse 2s
- **Hover des boutons:** Transform scale(1.05)
- **Scrollbar:** Stylisée avec couleurs personnalisées

### Responsive Design
```css
.main-container {
  display: grid;
  grid-template-columns: 320px 450px 1fr;
  gap: 20px;
  height: 100vh;
  padding: 20px;
}
```

## Structure des Données

### Informations Technicien (Exemple)
```javascript
{
  name: "Jean Dupont",
  initials: "JD",
  level: "Expert",
  experience: "5 ans",
  location: "Paris 15ème",
  assignedWorksite: "Résidence Étoile",
  arrivalTime: "14:30"
}
```

### Informations Chantier (Exemple)
```javascript
{
  name: "Résidence Étoile",
  customerSince: "3 ans",
  installer: "M. Bernard",
  subscriptionType: "Premium - 10 Caméras",
  equipment: [
    { name: "Caméra extérieure HD", icon: "🎥", qty: 6 },
    { name: "Caméra intérieure 360°", icon: "🎥", qty: 4 },
    { name: "Enregistreur NVR", icon: "📡", qty: 1 },
    { name: "Alimentation PoE", icon: "🔌", qty: 2 }
  ],
  lastIncident: "Problème d'enregistrement résolu le 15/10/2025"
}
```

### Format des Solutions
```javascript
{
  type: "knowledge_base",
  title: "Camera Recordings Not Visible",
  content: "Si votre caméra...",
  confidence: 0.85
}
```

## Cas d'Usage

### Scénario 1 : Appel de Support Standard
1. Technicien appelle depuis le terrain
2. Interface démarre automatiquement
3. Technicien pose une question dans le chat
4. IA analyse et propose des solutions dans la colonne 3
5. Si informations manquantes, bot pose des questions
6. Solutions s'affichent au fur et à mesure

### Scénario 2 : Consultation d'Historique
1. Agent de support voit les infos du chantier
2. Consulte l'équipement installé
3. Voit le dernier incident résolu
4. Adapte son approche en conséquence

### Scénario 3 : Résolution Guidée
1. Problème détecté: "Caméra ne s'enregistre pas"
2. IA affiche la solution de la base de connaissances
3. Solution formatée en étapes
4. Technicien suit les étapes
5. Confirme la résolution dans le chat

## Intégration avec le Système Existant

### Compatibilité
✅ Utilise les mêmes endpoints que l'interface demo/index.html
✅ Compatible avec le système multi-langue existant
✅ Fonctionne avec la base de connaissances Qdrant
✅ Intégré au système d'agents (Context Analyzer, RAG, etc.)

### Différences avec l'Interface Précédente
| Ancienne Interface | Nouvelle Interface |
|-------------------|-------------------|
| 2 colonnes | 3 colonnes |
| Focus: micro + suggestions | Focus: contexte + chat + solutions |
| Pas d'infos contextuelles | Infos technicien + chantier complètes |
| Liste de suggestions mixtes | Solutions séparées du chat |
| Audio via reconnaissance vocale | Audio + chat textuel |

## Prochaines Améliorations Possibles

### Court Terme
- [ ] Intégration avec CRM réel (au lieu de données mockées)
- [ ] WebSocket pour notifications temps réel
- [ ] Historique des appels précédents
- [ ] Export PDF des solutions proposées

### Moyen Terme
- [ ] Reconnaissance vocale intégrée (comme demo/index.html)
- [ ] Annotations sur les solutions
- [ ] Système de feedback (solution utile/non utile)
- [ ] Statistiques de résolution

### Long Terme
- [ ] Vision par caméra (upload d'images du site)
- [ ] Intégration calendrier/planning
- [ ] Base de connaissances personnalisée par client
- [ ] Analytics et métriques de performance

## Tests

### Lancer l'Application
```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
python app.py
```

### Accéder à l'Interface
```
http://localhost:8000/demo/technician
```

### Tester le Chat
1. Taper dans l'input: "Ma caméra ne s'enregistre pas"
2. Appuyer sur Entrée ou cliquer sur ➤
3. Vérifier que le message apparaît
4. Vérifier que la solution apparaît dans la colonne 3

### Tester les Contrôles
1. Cliquer sur le bouton Mute (🎤)
2. Vérifier que l'icône change en 🔇
3. Vérifier que le statut change en "En sourdine"
4. Re-cliquer pour désactiver

### Tester la Fin d'Appel
1. Cliquer sur le bouton rouge (📞)
2. Confirmer dans la popup
3. Vérifier que le statut passe à "Terminé"
4. Vérifier que le timer s'arrête

## Personnalisation

### Modifier les Données du Technicien
Éditer les valeurs dans le HTML (lignes 496-509):
```html
<h2 id="customerName">Jean Dupont</h2>
<span id="customerLocation">Paris 15ème</span>
...
```

### Modifier les Données du Chantier
Éditer les valeurs dans le HTML (lignes 519-559):
```html
<h3 id="worksiteName">Résidence Étoile</h3>
...
```

### Changer les Couleurs
Modifier les variables CSS dans la section `<style>`:
```css
/* Exemple: Changer la couleur principale */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
/* Remplacer par votre gradient */
```

## Support et Documentation

### Fichiers Liés
- `/app/frontend/templates/demo/technician_support.html` - Interface complète
- `/app/demo/web_demo_routes.py` - Routes Flask (ligne 35-38)
- `/app/services/realtime_transcription_service.py` - Service backend
- `/app/agents/agent_orchestrator.py` - Orchestration des agents

### Documentation Connexe
- `MULTILANGUAGE_FEATURE_COMPLETE.md` - Support multi-langue
- `UI_SPLIT_IMPLEMENTATION.md` - Séparation solutions/questions
- `TRANSCRIPTION_DEBUG_GUIDE.md` - Debug des problèmes

## Architecture Technique

```
┌─────────────────────────────────────────────────────────────┐
│                    Navigateur (Frontend)                     │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────────────┐  │
│  │ Colonne 1│  │ Colonne 2│  │      Colonne 3          │  │
│  │Technicien│  │   Chat   │  │      Solutions          │  │
│  │ Chantier │  │ Contrôles│  │                         │  │
│  └──────────┘  └──────────┘  └─────────────────────────┘  │
│                        │                                     │
│                        │ AJAX / Fetch                        │
└────────────────────────┼─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask Backend                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /demo/technician (Route)                            │  │
│  │  /demo/start-demo-call                               │  │
│  │  /demo/send-demo-transcription                       │  │
│  │  /demo/end-demo-call                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Realtime Transcription Service                      │  │
│  │  - process_transcription_segment()                   │  │
│  │  - get_session_suggestions()                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                     │
│                        ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Agent Orchestrator                                  │  │
│  │  ┌────────────┐  ┌──────────┐  ┌─────────────────┐ │  │
│  │  │  Context   │  │   RAG    │  │ Clarification   │ │  │
│  │  │  Analyzer  │  │  Engine  │  │     Agent       │ │  │
│  │  └────────────┘  └──────────┘  └─────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                     │
└────────────────────────┼─────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  PostgreSQL Database │
              │  - call_sessions     │
              │  - suggestions       │
              │  - agent_actions     │
              └──────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Qdrant Vector DB    │
              │  - Knowledge Base    │
              │  - 4 Camera Articles │
              └──────────────────────┘
```

## Conclusion

Cette nouvelle interface offre une expérience complète et professionnelle pour le support technique en temps réel, avec:
- ✅ Contexte complet du technicien et du chantier
- ✅ Interaction fluide via chatbot IA
- ✅ Solutions claires et actionnables
- ✅ Design moderne et responsive
- ✅ Intégration complète avec le backend existant

L'interface est prête à l'emploi et peut être personnalisée selon les besoins spécifiques de votre organisation.
