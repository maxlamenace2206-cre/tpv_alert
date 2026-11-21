# Alerte Topivo → notification sur ton téléphone

Toutes les 10 minutes, GitHub se connecte à ton compte staff.topivo.fr, regarde la liste des missions et t'envoie une notif **ntfy** si une nouvelle est apparue.

## 1. Sur ton téléphone (2 min)
1. Installe **ntfy** depuis le Play Store.
2. Appuie sur **+** et abonne-toi à un canal au nom difficile à deviner, par ex. `topivo-a9f3k2xq-alertes` (invente le tien, ne reprends pas cet exemple).
   (Les canaux ntfy sont publics : quelqu'un qui devine le nom pourrait lire tes notifs.)
3. Dans les réglages de l'appli, autorise les notifications et désactive l'optimisation de batterie pour ntfy.

## 2. Sur GitHub (5 min, depuis un ordinateur c'est plus simple)
1. Crée un compte sur github.com si tu n'en as pas, puis dans **github.com/settings/emails** coche **Keep my email addresses private** (sinon ton adresse mail apparaît publiquement dans l'historique).
2. **New repository** → nom `topivo-alert` → **Public** (voir la note plus bas) → Create.
3. **Add file → Upload files** : glisse tout le contenu du dossier (y compris le dossier `.github`).
4. **Settings → Secrets and variables → Actions → New repository secret**, crée ces 3 secrets :
   - `TOPIVO_EMAIL` : ton identifiant Topivo
   - `TOPIVO_PASSWORD` : ton mot de passe Topivo
   - `NTFY_TOPIC` : le nom du canal choisi à l'étape 1
5. **Settings → Actions → General → Workflow permissions** : coche **Read and write permissions** → Save.
6. Onglet **Actions** → active les workflows → **Vérifier Topivo** → **Run workflow** avec `debug` = `1`.

Tu dois recevoir « Topivo : surveillance activée » sur ton téléphone. Ensuite ça tourne tout seul.

## 3. Réglages
Aucun réglage nécessaire : le script est déjà calé sur Topivo. Il lit la page « Ouvert aux inscriptions »
(`/event?type=new`) et repère chaque carte d'événement par son lien unique `/event/hours/<numéro>`.
Si le site change un jour, tu peux le corriger sans toucher au code, dans **Settings → Secrets and variables → Actions → onglet Variables** :
- `MISSIONS_URL` : adresse de la page des missions
- `MISSION_SELECTOR` : sélecteur CSS d'une carte de mission (actuellement `.card-event`)

Le run en mode debug produit un fichier **debug** (supprimé automatiquement après 1 jour ; supprime-le toi-même dès que tu l'as regardé, car sur un dépôt public il est téléchargeable par tous) : capture d'écran + HTML + liste détectée, en bas de la page du run : c'est ce qu'il faut regarder pour ajuster.

## Pourquoi un dépôt public ?
- Dépôt public : minutes GitHub Actions illimitées et gratuites.
- Dépôt privé : 2 000 min/mois gratuites, pas assez pour une vérification toutes les 10 min. En privé, passe le `cron` à `*/30 * * * *`.

Tes identifiants restent dans les secrets, invisibles même en public. Le fichier `state.json` ne contient que des empreintes illisibles.

## Si ça casse
Tu reçois une seule notif « le script ne marche plus » (mot de passe changé, site modifié…). Relance alors en mode debug.
