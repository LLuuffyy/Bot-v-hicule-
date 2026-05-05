# Bot-v-hicule

Bot qui scrape automatiquement 10 sites français de petites annonces 2x/jour
pour trouver un **utilitaire d'occasion fiable** correspondant à des critères
stricts, et envoie par email les **10 meilleures annonces** classées par
écart par rapport au prix du marché.

Conçu pour un artisan en climatisation basé dans le Var (83210), budget
8 000 - 9 000 €, fourgon tôlé sans vitres arrière, diesel/essence.

## Sites couverts

| Site | Mode | Notes |
|---|---|---|
| LeBonCoin | Playwright stealth | Le plus gros volume en France |
| La Centrale | Playwright stealth | Spécialiste auto |
| Facebook Marketplace | Playwright + login persistant | Compte FB requis |
| ParuVendu | HTTP | Friendly |
| AutoScout24 | HTTP (JSON-LD) | Gros volume Europe |
| Ouest-France Auto | HTTP | Friendly |
| Caradisiac Occasions | HTTP | Friendly |
| Le Parking | HTTP (agrégateur) | Doublons dédupés automatiquement |
| AutoReflex | HTTP | Friendly |
| L'Argus Occasions | HTTP | Friendly |

## Setup Windows (pas-à-pas)

### 1. Installer Python 3.11+

Télécharge depuis <https://www.python.org/downloads/>. **Important** : coche
"Add Python to PATH" pendant l'installation.

Vérifie : ouvre PowerShell et tape `python --version`.

### 2. Cloner le repo

```powershell
cd C:\Users\<toi>\Documents
git clone https://github.com/lluuffyy/bot-v-hicule- Bot-v-hicule
cd Bot-v-hicule
```

### 3. Lancer l'installateur

Ouvre PowerShell **en mode administrateur** (clic droit → "Exécuter en tant
qu'administrateur") puis :

```powershell
cd C:\Users\<toi>\Documents\Bot-v-hicule
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
```

Ce script va :
- Créer un environnement virtuel Python dans `venv\`
- Installer les dépendances (httpx, Playwright, jinja2, etc.)
- Télécharger le navigateur Chromium pour Playwright
- Créer 2 tâches planifiées Windows (`BotVehicule-Matin` à 7h30, `BotVehicule-Soir` à 19h30)

### 4. Configurer les emails (`.env`)

Copie `.env.example` en `.env` :

```powershell
copy .env.example .env
notepad .env
```

Remplis les valeurs :

```ini
GMAIL_USER=ton.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
NOTIFY_EMAIL=ton.email@gmail.com
```

**Pour obtenir le mot de passe d'application Gmail :**
1. Va sur <https://myaccount.google.com/security>
2. Active la "Validation en deux étapes" si ce n'est pas déjà fait
3. Va sur <https://myaccount.google.com/apppasswords>
4. Crée un mot de passe pour "Application personnalisée" → "Bot Véhicule"
5. Copie les 16 caractères (avec ou sans espaces, peu importe) dans `.env`

### 5. Connexion Facebook (une seule fois)

Le scraper Facebook a besoin que tu te connectes manuellement la première fois.
Ses cookies sont sauvegardés et réutilisés pour les runs suivants.

```powershell
.\venv\Scripts\python.exe scripts\facebook_login.py
```

Une fenêtre Chromium s'ouvre. Connecte-toi à Facebook normalement, puis ferme
la fenêtre. La session est mémorisée dans `data\fb_session\`.

> ⚠ **Risque de blocage Facebook** : si FB détecte l'automatisation, ton compte
> peut être bloqué temporairement. Pour limiter le risque, le bot est limité à
> **1 visite Marketplace toutes les 12h**, mais le risque n'est pas nul. Si ça
> arrive, crée un compte FB secondaire et refais l'étape 5.

### 6. Test manuel

```powershell
.\scripts\run.ps1
```

Tu devrais recevoir un email avec les annonces trouvées dans les minutes qui suivent.

Tu peux aussi tester en mode "dry run" (sans envoyer d'email) :

```powershell
.\venv\Scripts\python.exe -m src.main --dry-run --verbose
```

### 7. C'est bon

Le bot tournera tout seul tous les jours à 7h30 et 19h30.

Vérifier les tâches planifiées :

```powershell
Get-ScheduledTask -TaskName BotVehicule-*
```

Voir les logs des runs précédents :

```powershell
Get-Content data\runs.log -Tail 100
```

## Critères de recherche

Définis dans [`src/config.py`](src/config.py) :

| Critère | Valeur |
|---|---|
| Code postal | 83210 (Belgentier) |
| Rayon | 100 km |
| Prix max | 9 000 € |
| Année min | 2012 |
| Km max | 200 000 |
| Carburants | diesel, essence |
| Type | fourgon tôlé (pas de vitres arrière) |

Modèles **whitelist** (bonus de score) : Renault Kangoo, Citroën Berlingo,
Peugeot Partner, Renault Trafic, Ford Transit Connect, Volkswagen Caddy.

Modèles **blacklist** (malus de score) : Fiat Doblo, Mercedes Citan, Dacia Dokker.

Pour ajuster, édite `src/config.py` ou utilise les variables d'environnement
listées dans `.env.example`.

## Comment c'est scoré (0-100)

Le scoring privilégie les **bonnes affaires par rapport au marché**.

| Critère | Bonus / Malus |
|---|---|
| Prix ≤ 75% du marché | +40 |
| Prix entre 75-90% du marché | +25 |
| Prix entre 90-100% du marché | +10 |
| Modèle whitelist | +15 |
| Modèle blacklist | -10 |
| Km < 100 000 | +12 |
| Km entre 100k-150k | +8 |
| Année ≥ 2017 | +8 |
| Année ≥ 2015 | +5 |
| Distance ≤ 30 km | +8 |
| Distance ≤ 50 km | +5 |
| Vendeur particulier | +5 |
| Description trop courte (<100 chars) | -10 |
| Baisse de prix détectée | +10 |

Le prix marché est calculé à partir de :
- Une **table de référence** (l'Argus 2026) : `src/market_price.py`
- Une **médiane dynamique** des annonces déjà collectées (rolling 90 jours)

## Architecture

```
Bot-v-hicule/
├── scripts/
│   ├── install.ps1            # Installation Windows + tâches planifiées
│   ├── run.ps1                # Lancement manuel ou planifié
│   └── facebook_login.py      # Setup unique du login FB
├── src/
│   ├── config.py              # Critères, modèles, mots-clés
│   ├── models.py              # Dataclass Listing
│   ├── storage.py             # SQLite + dédup + historique prix
│   ├── filters.py             # Filtrage hard + détection vitres
│   ├── scorer.py              # Score 0-100
│   ├── market_price.py        # Estimation prix marché
│   ├── geo.py                 # Distance code postal → 83210
│   ├── notifier.py            # Email Gmail SMTP
│   └── main.py                # Orchestrateur
├── scrapers/
│   ├── base.py                # Interface commune
│   ├── leboncoin.py           # ⭐ priorité
│   ├── lacentrale.py          # ⭐ priorité
│   ├── facebook.py            # ⭐ priorité (login requis)
│   └── ... (7 autres)
├── tests/
│   ├── test_filters.py        # 19 tests unitaires
│   └── test_scorer.py         #  9 tests unitaires
├── templates/
│   └── email.html.j2          # Template email
└── data/                      # Gitignored (DB, logs, FB session)
```

## Maintenance

- **Tests unitaires** : `.\venv\Scripts\python.exe -m pytest tests/ -v`
- **Lancer un seul scraper** : `python -m src.main --only leboncoin paruvendu --dry-run`
- **Voir les logs** : `data\runs.log`
- **Backup de la base** : copier `data\listings.db` ailleurs de temps en temps
- **Réinitialiser** : supprimer `data\listings.db` (la prochaine exécution recréera tout)

## Limites connues

- **Anti-bot** : LeBonCoin / La Centrale / Facebook changent régulièrement
  leurs protections. Si un scraper retourne 0 résultat, c'est probablement
  qu'ils ont mis à jour leur DOM ou leur détection. Le bot continue avec les
  autres sites en attendant un fix.
- **Détection des vitres arrière** : c'est le filtre le plus délicat (rarement
  un champ structuré). Le bot fait son maximum avec les mots-clés
  titre/description. En cas de doute, l'annonce passe avec le flag
  `⚠ vitres à vérifier` — vérifie sur la photo avant de te déplacer.
- **Légal** : ce bot est pour usage strictement personnel. Pas de revente, pas
  de spam, rate limiting respecté. C'est une zone grise tolérée.

## Conseil diesel vs essence

Pour ton usage (artisan clim, kilométrage probable > 15 000 km/an, charge utile,
tournées Var/Bouches-du-Rhône) → **diesel recommandé**.

- Meilleur couple pour charger l'utilitaire
- Plus économique sur kilométrage élevé
- Année ≥ 2012 = Crit'Air 2 = autorisé dans les ZFE Marseille / Aix / Nice
- Le diesel domine ce segment d'occasion (5x plus de choix)

L'essence reste OK si tu fais surtout du Toulon intra-muros, mais tu auras
moins d'annonces.
