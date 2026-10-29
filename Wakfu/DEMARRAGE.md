# Démarrage et initialisation de WAKFU Atlas

1. Accepter l'invitation GitHub si le dépôt est privé. Sur la page du dépôt, choisir **Code → Download ZIP**, puis extraire tout le dossier dans un emplacement où vous pouvez écrire. Ne pas lancer depuis le ZIP.
2. Installer **Python 3.10 ou plus**. Sous Windows, activer le lanceur Python ou l'ajout au PATH. Aucun module Python supplémentaire, compte Ankama ni installation du jeu n'est nécessaire.
3. Sous **Windows**, double-cliquer sur `Ouvrir-Wakfu.cmd`. Sous **macOS/Linux**, ouvrir un terminal dans le dossier extrait et exécuter `python3 launch.py`.
4. Le navigateur ouvre le site local. L'adresse habituelle est http://127.0.0.1:8765/ ; si le port est occupé, le lanceur choisit un autre port. Utiliser l'adresse qu'il ouvre.
5. Au premier lancement, la page d'initialisation apparaît automatiquement. Cliquer **Initialiser la base** et garder l'ordinateur et le serveur ouverts jusqu'à la fin. Prévoir Internet et de l'espace libre pour la base d'environ 125 Mo et les téléchargements temporaires.
6. Cliquer **Explorer WAKFU Atlas**. Les sources officielles Ankama sont téléchargées, reconstruites et vérifiées pour reproduire les données de jeu de référence, dont les objets, monstres, recettes et récoltes par zone.

## Vos données

Aucune base SQL ni donnée personnelle du créateur n'est distribuée. Les favoris, notes et apprentissages commencent vides et appartiennent à votre installation. Le panier et le stock sont conservés dans votre navigateur.

## Les fois suivantes

Relancer le même lanceur : la base déjà initialisée est réutilisée. Après un redémarrage de l'ordinateur, relancer l'application. Fermer l'onglet ne ferme pas le serveur.

## En cas de problème

- Python introuvable : installer Python 3.10+ avec son lanceur ou son ajout au PATH, puis réessayer.
- Erreur d'initialisation : vérifier Internet, l'espace disque et les droits d'écriture du dossier. Réessayer depuis la page. Les sources officielles de la version de référence doivent encore être accessibles ; une erreur explicite est affichée sinon.
- Adresse inaccessible : relancer le lanceur et utiliser l'adresse ouverte, car le port peut changer.

`127.0.0.1` désigne votre propre ordinateur. Le projet nécessite Python en fonctionnement ; le dépôt GitHub ne constitue pas un hébergement public du site.

Consulter [le README](README.md) pour les détails de la version de référence et de la reconstruction.
