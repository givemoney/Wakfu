# Base locale WAKFU actuelle

**Première utilisation : [guide de démarrage et d’initialisation](DEMARRAGE.md).**

Python 3.10+ et SQLite (bibliothèque standard, aucune dépendance Python supplémentaire).

## Installation depuis GitHub

1. Télécharger le ZIP du dépôt (Code → Download ZIP), puis **extraire tout le dossier** dans un emplacement où vous avez le droit d'écrire. Ne pas lancer depuis l'intérieur du ZIP.
2. Installer Python 3.10 ou plus s'il est absent. Sous Windows, activer le lanceur Python ou l'option PATH de l'installation. Aucun compte Ankama ni installation du jeu n'est requis.
3. Sous Windows, double-cliquer **Ouvrir-Wakfu.cmd**. Sous macOS/Linux, ouvrir un terminal dans le dossier extrait et exécuter **python3 launch.py**. Le navigateur s'ouvre sur l'adresse annoncée par le lanceur.
4. Cliquer **Initialiser la base**. Le serveur télécharge les sources publiques officielles, reconstruit et vérifie le catalogue identique à la référence, ainsi que les relations des zones de récolte. Garder le serveur et l'ordinateur ouverts pendant l'opération.
5. Cliquer **Explorer WAKFU Atlas**. Objets, monstres, recettes et les cinq catégories de récolte par zone sont disponibles ; les favoris et apprentissages commencent vides.

Le téléchargement du dépôt ne contient aucune base SQLite. Prévoir Internet et de l'espace libre pour une base d'environ 125 Mo et les fichiers temporaires de reconstruction. Le dossier peut contenir des espaces ou des accents. Le lancement utilise l'interpréteur installé sur votre ordinateur, sans chemin propre à un utilisateur ni adresse réseau fixe. Si le port 8765 est occupé, le lanceur choisit un port libre et ouvre la bonne adresse ; il ne ferme aucun autre programme. Les données de navigateur comme le panier sont liées à l'adresse locale utilisée.

L'installation nécessite que les sources officielles de la version de référence soient encore accessibles. Une indisponibilité réseau ou une source différente provoque une erreur explicite et permet de réessayer. Cette distribution est une application locale, pas un site hébergé sur GitHub Pages : Python doit fonctionner sur l'ordinateur qui l'utilise.

## Première installation sans base partagée

Lancer **Ouvrir-Wakfu.cmd**. Si `wakfu.sqlite` est absente, l'accueil ouvre automatiquement la page **/initialisation** à l'adresse indiquée par le lanceur. Cliquer **Initialiser la base**, garder le serveur ouvert et attendre la fin, puis cliquer **Explorer WAKFU Atlas**. Internet et suffisamment d'espace pour les archives temporaires et la base sont nécessaires. La page reste consultable et retrouve l'état de l'installation après un rechargement tant que le serveur tourne.

Cette initialisation reproduit le catalogue de référence **1.93.1.62**, build client **6.0_1.93.1.5275.330**. Ce numéro désigne la version de la base utilisée comme référence, pas une promesse qu'il s'agit toujours de la dernière version du jeu. `updater/reference.json` contient les versions, empreintes des sources publiques et empreintes du contenu des 44 tables de jeu ; il ne contient aucune préférence utilisateur ni la base SQLite. Les fichiers sont téléchargés depuis les CDN officiels Ankama, leurs empreintes contrôlées, puis le même importateur reconstruit la base. Le contenu des tables est comparé à la référence avant publication. L'identité porte sur les données de jeu et leur schéma, pas sur les octets du fichier SQLite ou les dates de reconstruction.

Si une source de référence manque ou a changé, l'installation échoue explicitement, sans basculer vers une autre version. La base candidate et les téléchargements temporaires sont supprimés lors d'un échec normal. Une installation simultanée est bloquée ; une base existante n'est jamais remplacée par cette page. Après une interruption brutale, le verrou `.update.lock` peut subsister : vérifier qu'aucune reconstruction ne tourne avant de le retirer. Relancer ensuite le serveur et réessayer.

Les favoris, notes et statuts d'apprentissage se trouvent exclusivement dans **personal.sqlite** ; le panier, le stock et les réglages du navigateur restent dans le stockage local de ce navigateur. Un nouvel utilisateur ne reçoit aucune de ces données. La page ne supprime pas les préférences déjà présentes sur une installation existante. Il s'agit d'une application locale, sans comptes ni isolation de plusieurs utilisateurs partageant la même installation serveur. L'installation est accessible seulement depuis l'ordinateur du serveur via `127.0.0.1` ; l'accès réseau reste en lecture seule.

Commande équivalente : `python updater/update.py --initialize-reference updater/reference.json`. La mise à jour habituelle `python updater/update.py` conserve son fonctionnement : elle importe la version actuellement publiée et préserve `personal.sqlite`.

## Interface web locale — WAKFU Atlas

### Récoltes par zone

L'onglet **Récoltes par zone** (`/#locations`) liste uniquement les territoires possédant des récoltes référencées : poissons, minerais, bois, récoltes paysannes et récoltes d'herboriste. Les donjons et butins de monstres sont exclus. Le tri utilise le niveau minimum de métier requis dans chaque zone ; la plage affichée décrit les niveaux des récoltes, pas le niveau de combat du territoire. La recherche porte sur la zone ou le produit récolté.

Les liens territoire-ressource viennent des références d'écosystème de `worlds.lib` dans `contents/maps/data.jar` du client officiel Ankama. Le lecteur contrôle les limites de chaque collection, l'identité des territoires et la consommation complète du fichier. Les identifiants sont ensuite joints aux ressources et actions de récolte officielles, puis aux catégories d'objets des cinq métiers. Les bois sont limités aux actions de coupe ramenant l'arbre au stade vide, et à la catégorie officielle Forestier : fruits et boutures sont exclus de Bois. Les autres catégories incluent leurs produits de récolte et graines, ainsi que les produits rares référencés par les listes de récolte, lorsqu'ils appartiennent à la même catégorie d'objets. Un produit est affiché une seule fois par zone, même si plusieurs actions le fournissent.

`updater/harvest-locations.json` fournit les relations de la version de référence. Une reconstruction ou mise à jour génère `harvest-locations.json` à la racine, à partir de l'archive officielle téléchargée. Le serveur vérifie version, build et empreinte de l'archive par rapport à la base ; une référence incompatible n'est jamais utilisée. Ces données de zones n'ajoutent aucune préférence personnelle ni modification aux tables de jeu de la base de référence. Les données SQLite restent exclues du dépôt.

Une référence d'écosystème décrit une zone, pas les positions des gisements ou bancs de poissons ni leur disponibilité instantanée. La couverture n'est pas annoncée comme exhaustive ; les territoires sans récolte localisable sont omis. Les zones classées comme instances de donjons dans les données officielles sont exclues. Les données du serveur et les plantations peuvent évoluer.

Double-cliquer sur **Ouvrir-Wakfu.cmd** dans ce dossier. Le lanceur démarre le serveur local si nécessaire et ouvre son adresse locale dans le navigateur (port 8765 par défaut, un port libre sinon). Après un redémarrage de Windows, utiliser à nouveau le lanceur.

- Collections : objets, monstres, recettes, donjons, ressources.
- Recherche par nom ou identifiant, sans distinction de casse ou d'accents ; filtres de niveau, tri et pagination.
- Cliquer une carte pour voir sa fiche, puis une source, un ingrédient ou un monstre pour poursuivre l'exploration. Le bouton Retour revient à la fiche précédente.
- Les recettes permettent de calculer les ingrédients pour plusieurs fabrications.
- Les lieux distinguent les coordonnées d'entrée des indications concernant une famille.
- La page Sources & couverture explique les limites. Les modèles d'effets restent disponibles dans une section repliable, sans formule inventée.

La recherche et les fiches consultent la base locale. Les images sont affichées directement depuis https://static.ankama.com/wakfu/portal/game/item/64/{gfx_id}.png et monster/200/{gfx_id}.png à partir des identifiants graphiques officiels. Les recettes utilisent l'image de leur produit ; les ressources utilisent iconGfxId. Aucun fichier image n'est enregistré dans le projet ni importé dans SQLite. Le navigateur peut utiliser son cache habituel. Les images nécessitent Internet ; un symbole remplace une image absente ou inaccessible. Aucun accès au client du jeu n'est effectué. Le serveur écoute uniquement sur 127.0.0.1, consulte SQLite en lecture seule et ouvre une connexion par requête : la prochaine consultation utilise la base remplacée par l'updater. Il n'effectue aucune mise à jour automatique. Fermer le navigateur ne ferme pas le serveur ; il s'arrête au redémarrage de Windows. Pour un usage avec arrêt manuel, lancer Python avec `web/server.py` dans un terminal, puis Ctrl+C.

Fichiers : `web/server.py`, `web/index.html`, `web/style.css`, `web/app.js`, `start-web.ps1` et `Ouvrir-Wakfu.cmd`. Aucune dépendance supplémentaire à installer.
## Utilisation

Depuis ce dossier : `python updater/update.py`. Si Python n'est pas dans PATH, utiliser le chemin complet d'un interpréteur Python. `update.ps1` recherche Python 3.10+ installé, sans chemin propre à une machine.

La mise à jour télécharge le numéro courant, télécharge les fichiers de cette version, construit une nouvelle base, vérifie ses relations et son intégrité, revérifie le numéro courant, puis remplace `wakfu.sqlite` avec `os.replace`. Aucun historique ni sauvegarde de version n'est conservé. Une erreur avant le remplacement conserve l'ancienne base. Les téléchargements et la base candidate sont supprimés en fin d'exécution, même en cas d'exception Python. Une interruption brutale du processus peut laisser un dossier temporaire et `.update.lock` : vérifier qu'aucun import ne tourne avant de les supprimer manuellement. Une base ouverte par un autre programme peut bloquer son remplacement sur Windows ; fermer ce programme et relancer.

`report.json` est le rapport lisible courant. Les métadonnées intégrées à SQLite font autorité si l'écriture du rapport externe est interrompue après le remplacement de la base. Les données originales JSON sont conservées **dans la base** (`source_records`) pour ne perdre aucun champ ; les fichiers téléchargés sont supprimés. Il s'agit uniquement de la version actuelle, pas d'un historique.

Téléchargement seul : `python updater/download.py DOSSIER_TEMPORAIRE` (ce mode explicite conserve ses fichiers). Vérification : `python updater/verify.py`.

## Sources et traçabilité

- Version officielle : https://wakfu.cdn.ankama.com/gamedata/config.json
- Données : https://wakfu.cdn.ankama.com/gamedata/{version}/{dataset}.json
- Index officiel du launcher : https://cytrus.cdn.ankama.com/cytrus.json
- Manifeste officiel : https://cytrus.cdn.ankama.com/wakfu/releases/main/windows/{build}.manifest
- Archives officielles : blocs vérifiés dans https://cytrus.cdn.ankama.com/wakfu/bundles/{préfixe}/{hash}
- Publication officielle de l'export : https://www.wakfu.com/en/forum/332-development/236779-json-data (page protégée par vérification anti-robot lors de ce travail ; contenu non utilisé pour déduire des mécaniques).
- Licence de données Ankama : https://static.ankama.com/upload/backoffice/direct/2019-03-11/0142dee52de0de37d139f4728b9e9a4d.pdf

Les valeurs importées proviennent exclusivement des réponses des CDN Ankama. `report.json` et `metadata` recensent les URL, statuts HTTP, nombres de lignes, tailles, empreintes des JSON et du manifeste, ainsi que les SHA-1 des archives officielles téléchargées. Aucune donnée communautaire n'est intégrée. Les noms des premiers fichiers JSON ont été repérés à partir du projet WakData (https://gitlab.com/MathiusD/wakdata), puis vérifiés directement sur le CDN courant ; ses anciennes valeurs ne sont pas utilisées.

Les formats de départ ont été étudiés à partir de wakfu-bdata et wakfu-bdata-gen (https://github.com/jac3km4/wakfu-bdata, https://github.com/jac3km4/wakfu-bdata-gen). Leurs anciens schémas ne suffisaient pas : l'outil Python lit maintenant les types de champs dans la copie **courante téléchargée** de `wakfu-client.jar`, puis vérifie identifiant, taille de chaque enregistrement et consommation complète des archives. Le schéma FlatBuffers du manifeste a été vérifié dans https://github.com/AerafalDev/Cytrus/blob/main/src/Cytrus/FlatBuffers/Manifest.fbs. Ces projets servent de références de format, pas de sources de valeurs de jeu.

Les libellés français des monstres, familles, sorts, instances et donjons proviennent des entrées officielles `content.{type}.{id}` de `texts_fr.properties`, contenues dans l'archive officielle téléchargée `i18n_fr.jar`. Les numéros de version JSON et de build du launcher ont des formats distincts ; les deux sont consignés et la branche de version est contrôlée.

## Organisation et schéma

- `wakfu.sqlite` : base unique courante.
- `report.json` : comptages, audit et limites.
- `updater/download.py` : téléchargement, nouvelles tentatives réseau, contrôle de version.
- `updater/import_data.py` : import et validation.
- `updater/update.py` : verrou, reconstruction temporaire, remplacement.
- `updater/verify.py` : contrôles de réimport et de conservation de la base en cas d'échec.
- `updater/cytrus.py` : manifeste courant, téléchargement ciblé des blocs, vérification SHA-1.
- `updater/client_export.py` : export des archives officielles téléchargées.
- `updater/client_binary.py` et `java_schema.py` : lecture et validation des données binaires, sans exécuter le code du jeu.
- `updater/map_points.py` : lecture des repères et coordonnées officiels.

Tables : `items`, `job_items`, `equipment_types`, `resource_types`, `actions`, `effects`, `effect_parameters`, `item_effects`, `item_properties`, `item_properties_link`, `recipes`, `recipe_ingredients`, `recipe_results`, `recipe_categories`, `resources`, `harvest_actions`, `harvest_loots`, `states`, `translations`, `arrays`, `source_records`, `referenced_harvest_skills`, `acquisition_sources`, `metadata`.

Tables ajoutées : `client_monsters`, `monster_families`, `monster_drops`, `monster_spells`, `monster_spell_names`, `monster_collect_actions`, `client_dungeons`, `dungeon_monsters`, `dungeon_entrances`, `world_instances`, `map_points`, `map_interactive_points`, `client_protectors`, `family_ecosystem_references`, `client_loot_lists`, `loot_list_entries`, `client_world_loot_lists`.

`client_monsters` expose identifiant, famille, niveaux minimum/maximum, caractéristiques de base PV/PW/PA/PM et identifiant graphique. Les autres champs et évolutions de caractéristiques restent conservés sous leur numéro de champ binaire et dans les données originales. Aucune formule de niveau ou de Stasis n'est extrapolée.

Les butins conservent `rate_raw` et le vecteur de conditions original, ainsi que tous les paramètres anonymes. Ce taux brut n'est pas une promesse du taux effectif en jeu ; les critères, variations de serveur, modes et mécanismes de tirage ne sont pas simulés. Les récoltes sur les créatures et leurs listes de butin sont reliées séparément aux objets dont l'identifiant existe dans l'export JSON. Les références inconnues sont conservées et comptées.

Les champs scalaires des définitions sont des colonnes SQL conservant leur nom officiel (les objets imbriqués utilisent `_`). Traductions et listes sont séparées. Les effets sont reliés aux objets avec ordre et contexte ; leurs paramètres numériques sont séparés et leur définition complète conservée. Les modèles de description des effets ne sont pas évalués : aucune formule n'est improvisée.

Vues : `all_item_ids` déduplique les identifiants ; `all_items` offre des colonnes communes (priorité à `items` pour les doublons, les deux définitions restent conservées) ; `item_names_fr` expose les noms français. Ne pas additionner `items` et `job_items` pour compter les objets uniques.

`monster_dungeon_locations` expose l'appartenance explicite d'un monstre à un donjon, le monde associé et, lorsqu'un repère correspondant est disponible, les coordonnées **de l'entrée**. `monster_family_ecosystem_hints` expose les mondes où la famille figure dans les besoins d'écosystème d'un membre de clan : ce sont des indications au niveau de la famille, pas une preuve de présence de chaque variante ou boss.

Les relations vers les fichiers CDN incomplets sont auditées sans créer de faux objets pour satisfaire une clé étrangère. Les relations internes des effets sont contraintes par SQLite. Les ingrédients et résultats doivent référencer des recettes existantes ; les catégories doivent exister. Tous les enregistrements téléchargés sont comptés après import et `PRAGMA integrity_check` et `foreign_key_check` doivent réussir.

## Limites de couverture

Le CDN est un instantané publié : la présence d'un objet ne prouve pas son obtention possible aujourd'hui en jeu. Les pourcentages de complétude du monde réel sont inconnus faute de catalogue total officiel accessible.

Les sources d'obtention normalisées couvrent résultats de recettes, récoltes de ressources et de créatures, butins de récolte et drops intégrés aux définitions officielles des créatures. Les listes de butin mondial sont conservées sans inventer leur application à chaque monstre.

Les 14 catégories de recettes portent leurs noms officiels. Les 5 `skillId` de récolte sont conservés comme identifiants référencés ; aucun nom de métier n'est inventé. Les 32 types d'équipement et 7 types de ressources environnementales ne sont pas un catalogue exhaustif de tous les types d'objets.

`recipePattern.json` et les candidats JSON `monsters`, `monsterDrops`, `drops`, `zones`, `areas`, `jobs`, `itemSources`, `lootTables`, `npcs`, `achievements`, `quests` ont retourné HTTP 403 lors de la construction initiale. **403 signifie accès refusé, pas preuve d'absence.** Ces noms sont des sondes, pas une liste officielle exhaustive. Les monstres et données associées sont maintenant obtenus par les archives publiques du CDN du launcher, qui constituent une autre source officielle.

Les définitions de créatures incluent PNJ, invocations, variantes de quêtes, contenus obsolètes et de test. Leur nombre ne représente pas celui des ennemis actuellement combattables. Des noms peuvent manquer ; aucun libellé n'est inventé. Une association de donjon, une coordonnée d'entrée, un monde et un habitat de famille sont des informations différentes.

Les descriptions de repères peuvent contenir des critères d'accès non évalués. Les points d'une version future et ceux dont toutes les descriptions sont explicitement `False` sont exclus des relations de lieux proposées, mais conservés dans les données brutes. Aucun point de réapparition exact d'une espèce en plein air n'est déduit de la position d'un membre de clan.

Le rapport donne le nombre exact d'objets sans relation d'obtention connue, des références de drop inconnues, des créatures sans lieu associé et des donjons sans coordonnées d'entrée. Le catalogue total de toutes les sources d'obtention, emplacements de réapparition, quêtes, marchands et récompenses reste inconnu.

## Confidentialité et indépendance du jeu

L'outil final n'inspecte **ni l'installation locale de WAKFU, ni sa mémoire, ni son processus**. Il ne modifie aucun fichier du jeu et n'automatise aucune action en jeu. Il utilise Python et les fichiers téléchargés dans son propre dossier temporaire ; aucun Java ou outil de décompilation n'est requis pour les mises à jour.

Il ne demande pas de compte Ankama, mot de passe, cookie ou jeton de session et ne les transmet pas. La base reste locale. Les serveurs CDN voient les requêtes et l'adresse IP : ce fonctionnement ne promet ni anonymat complet ni indétectabilité. Aucun mécanisme de dissimulation ou de contournement d'anti-triche n'est ajouté. Pendant l'investigation initiale, des fichiers installés ont été lus en lecture seule ; l'outil livré a été modifié pour utiliser exclusivement les téléchargements publics.

## Exemple de recherche

```sql
SELECT DISTINCT n.id, n.name, a.source_kind, a.source_id
FROM item_names_fr n
LEFT JOIN acquisition_sources a ON a.item_id=n.id
WHERE n.name LIKE '%Algue%';
```

Exemple pour les monstres et leurs lieux :

```sql
SELECT t.text AS monstre, l.dungeon_name, l.associated_world_name,
       l.entrance_world_id, l.entrance_x, l.entrance_y
FROM client_monsters m
JOIN translations t ON t.entity='client_monsters' AND t.entity_id=m.id
  AND t.field='title' AND t.language='fr'
LEFT JOIN monster_dungeon_locations l ON l.monster_id=m.id
WHERE t.text LIKE '%Arakne%';
```



## Séparation des PNJ dans l’interface

La rubrique PNJ utilise les 105 définitions officielles de membres de clan (`client_protectors`) et les 118 définitions de créatures rattachées à la famille officielle « Membres de clan » ou ses descendants. Les 223 fiches ne constituent pas 223 personnages distincts : une personne peut être représentée dans les deux catalogues. La fiche de localisation et la définition de créature restent distinguées. Les identifiants de routage des premières sont négatifs pour éviter les collisions ; leur identifiant officiel positif est affiché. Aucun nouvel identifiant de jeu n’est créé dans la base.

Ces 118 définitions sont exclues des Monstres. La rubrique Monstres contient 1 085 autres définitions associées explicitement à un donjon ou à une liste de butin. Ce critère de sélection ne prouve pas leur disponibilité actuelle, ni une classification exhaustive. Les 1 671 autres définitions sont dans « À classer » : elles peuvent comprendre des PNJ non encore identifiés, invocations, variantes, contenus de test ou créatures sans relations connues. Aucun nom de créature n’est utilisé pour deviner son rôle. Les définitions originales restent intactes ; les listes se recalculent depuis la base à chaque consultation.
Les recettes proposent 14 cases à cocher par métier, issues des catégories officielles. Plusieurs sélections sont combinées (un métier ou un autre), puis croisées avec le nom et les niveaux. Sans case cochée, tous les métiers sont inclus. Réinitialiser efface aussi cette sélection.

## Modes d’affichage et rareté

Cartes, Liste et Tableau sont disponibles pour chaque collection. Le choix est mémorisé dans le navigateur, avec les mêmes résultats, filtres et pagination. Les objets et les produits de recettes portent un libellé de rareté ainsi qu’une couleur de nom et de bordure ; les autres entités restent neutres. La palette est adaptée au contraste du fond clair, plutôt qu’une reproduction des valeurs RGB du client. Les codes bruts viennent de all_items.rarity dans l’export officiel. La correspondance des libellés (0 commun, 1 inhabituel, 2 rare, 3 mythique, 4 légendaire, 5 relique, 6 souvenir, 7 épique) a été vérifiée dans la référence technique communautaire maintenue https://github.com/mikeshardmind/wakfu-utils/blob/main/wakautosolver/restructured_types.py . Les conventions vert pour rare et orange pour mythique sont corroborées par https://methodwakfu.com/divers/personnalisation/les-titres/ . Une rareté inconnue conserve un affichage neutre ; aucune rareté n’est inventée pour les PNJ, monstres ou ressources environnementales.

## Notes personnelles et favoris

Le tri initial est le niveau croissant ; le tri par nom reste disponible sur choix explicite. Les objets et les produits de recettes ont une étoile de favori et une note éditable dans leur fiche (5 000 caractères maximum). Le résumé de note est visible en cartes, liste et tableau. « Favoris uniquement » se combine aux autres filtres. Notes et favoris d’un même objet sont partagés entre sa fiche et les recettes qui le produisent.

Les données personnelles sont stockées localement dans personal.sqlite, séparément de wakfu.sqlite. Elles persistent après la fermeture du navigateur et le remplacement de la base de jeu par l’updater. Conserver personal.sqlite si le projet est déplacé ou sauvegardé. Elles ne sont envoyées à aucun service externe. Elles restent présentes si un objet disparaît de l’export, mais cet objet absent n’est plus affiché dans le catalogue courant. Aucune note de démonstration n’est livrée.

## Catégories de l’hôtel de vente
Le menu Objets utilise la hiérarchie officielle ITEM_TYPE (199 catégories, parent_id et ordre du client), avec les traductions françaises content.14. Source : archive contents/bdata/37.jar téléchargée sur le CDN Ankama par l’updater. Les groupes peuvent être dépliés ; sélectionner un parent inclut ses descendants. Plusieurs branches peuvent être combinées avec la recherche, les niveaux et les favoris. Les types supplémentaires restent accessibles sous Autres catégories. Aucun intitulé absent n’est inventé. La mise à jour valide la hiérarchie et la couverture de tous les types d’objets avant de remplacer la base. Les notes et favoris restent dans personal.sqlite.



## Consultation sur le réseau local (optionnelle)

Le lancement standard écoute uniquement sur `127.0.0.1` et ne change aucune règle de pare-feu. L'initialisation et les préférences restent réservées à l'ordinateur du serveur.

Pour un partage choisi sur votre réseau privé, lancer `python web/server.py --lan-host ADRESSE_IPV4_DU_PC --port 8765`. Utiliser ensuite cette adresse et ce port depuis l'autre appareil. Le réseau donne uniquement accès au catalogue et au calcul du panier, sans permettre d'initialiser la base ni de modifier les préférences personnelles du serveur.

Sous Windows, `enable-lan.ps1` est un outil optionnel à lancer en administrateur avec vos propres paramètres `-LanHost`, `-RemoteSubnet`, `-InterfaceAlias` et, si nécessaire, `-Port`. Il limite la règle au Python installé, à l'adresse et au sous-réseau choisis, sur un profil réseau privé. Il n'est jamais exécuté par le lanceur ou la page d'initialisation. Aucune adresse IP ou interface personnelle n'est prédéfinie.

## Panier de recettes

Depuis la liste ou la fiche des recettes, choisissez Ajouter au panier, puis Panier. Les quantités sont des nombres de fabrications (le rendement de chaque recette est indiqué). Le panier est propre au navigateur et enregistré dans son stockage local, y compris sur le réseau local. Aucun stock possédé ne se déduit automatiquement.

Le calcul lit uniquement wakfu.sqlite. Il décompose les composants, additionne les besoins communs avant arrondi des fabrications et indique les surplus. Lors de plusieurs recettes pour un composant, un choix est requis ; le total reste partiel avant ce choix. Les ingrédients sans recette connue constituent les feuilles du calcul, sans garantir que leur source est exhaustive. Les produits secondaires ne sont pas réutilisés. Les cycles et les recettes incomplètes sont signalés, jamais inventés. Les notes et favoris restent privés sur le poste principal.


### Panier : page et checklist

La petite icône de panier ajoute une recette une seule fois et devient colorée. Recliquer ne change pas la quantité. La page /panier permet seule de modifier les fabrications et retirer les recettes. Les ingrédients proposent cartes, liste ou tableau avec image, niveau, type, rareté et lieux des sources connus. Les filtres par branche de type, lieu, rareté et nom se combinent. Les indications de famille restent signalées comme approximatives ; les emplacements absents sont Lieu inconnu.

Cocher un ingrédient barre la ligne sans la masquer. Les cases sont enregistrées par navigateur. Toute augmentation du besoin total décoche la ligne ; un besoin identique ou réduit conserve la case. Ces cases sont une confirmation manuelle, pas une gestion automatique du stock.


### Arbre des recettes

Sous la checklist, chaque recette du panier présente son arbre de composants et les quantités de chaque branche. Les liens ouvrent les fiches dans un onglet. Les composants fabriqués sont décomposés récursivement. Les lots partagés sont réutilisés entre branches et explicitement signalés, afin de conserver les totaux du calculateur. Les choix non résolus restent signalés.


### Plan global et suivi de fabrication

Avant les arbres, le plan global regroupe les fabrications par recette et additionne les composants communs. Il minimise le nombre de passages chez les artisans en respectant les dépendances, y compris les retours nécessaires. Chaque passage termine toutes les recettes alors réalisables chez cet artisan. Une recherche exacte compare les ordres possibles ; une borne de 30 000 états ou 2 secondes maintient le panier réactif. Si cette limite empêche de prouver le minimum, le plan proposé est explicitement indiqué comme non prouvé. Les choix de recettes manquants donnent un plan partiel. Ce calcul suppose les ingrédients de base rassemblés et un stockage suffisant ; il minimise les passages, pas les distances géographiques. Le métier, le niveau, les produits et les ingrédients consommés sont indiqués, sans inventer de lieu d atelier. Des cases indépendantes suivent les étapes du plan et chaque ligne des arbres. Les lignes restent visibles et barrées ; une augmentation du besoin décoche la ligne correspondante. Le suivi est enregistré par navigateur et ne déduit pas automatiquement les stocks.

### Exclure des ingrédients dans la recherche de recettes

Le filtre propose une recherche d'objets avec images, plusieurs exclusions retirables et un bouton pour les effacer. Par défaut, toute recette contenant directement au moins un ingrédient exclu est masquée. L'option « Inclure les recettes intermédiaires » vérifie toute la chaîne connue : une alternative sans ingrédient exclu suffit à conserver la recette. Les composants sans recette connue sont des feuilles ; les chaînes cycliques ou incomplètes ne constituent pas une fabrication valide. Le résultat dépend de la couverture de la base, pas d'une garantie sur toutes les façons d'obtenir un objet en jeu. Le filtre se combine aux métiers, niveaux, raretés, favoris et à la pagination. Il ne modifie ni les recettes ni le panier.

### Mobilier apprenable et suivi manuel

Le filtre « Apprentissage du mobilier » est disponible dans Objets et Recettes : tous, apprenables, non appris, déjà appris, non apprenables. Les objets possédant l'action officielle LEARN_FURNITURE portent une case « Déjà appris » sur leurs listes et fiches. Elle est décochée par défaut et modifiable manuellement. Aucun journal ni état du compte de jeu n'est importé. Le statut est conservé dans personal.sqlite, avec les notes et favoris, indépendamment du remplacement de wakfu.sqlite. Il correspond au profil local Atlas, pas à une synchronisation automatique des comptes WAKFU. Les statuts et filtres personnels restent réservés au poste principal ; le réseau local ne reçoit que l'indicateur public apprenable.

La table item_learning provient des actions ITEM de contents/bdata/35.jar. L'import initial a lu le client Steam en lecture seule ; sa source et son empreinte sont enregistrées dans metadata.furniture_learning_source. Les prochaines mises à jour téléchargent cette archive avec les autres sources officielles et reconstruisent la classification. Le lecteur trouve l'identifiant LEARN_FURNITURE dans l'énumération du client, contrôle les identifiants et la taille de chaque enregistrement, et échoue si le format change. Une absence d'objet dans le client reste un statut inconnu, jamais un non apprenable déduit. Ce statut désigne l'apprentissage d'une apparence de mobilier, pas l'apprentissage d'un plan de recette.

### Tri et visibilité des ingrédients du panier

Le tri propose niveau croissant (par défaut), niveau décroissant, nom, catégorie ou lieu de récupération. Les catégories et lieux inconnus sont placés après les valeurs connues ; les objets à plusieurs sources restent affichés une seule fois. Les filtres existants restent combinables. Le bouton « Masquer les ingrédients cochés » cache seulement les ingrédients de base rassemblés ; un second clic les réaffiche cochés et barrés. Le compteur précise les lignes masquées. Le tri et le choix de visibilité sont conservés dans le navigateur, sans modifier le calcul des besoins ni les cases du plan et des arbres.

Le panier ne comporte plus de filtres d'ingrédients : uniquement les tris et le bouton de masquage des lignes cochées. Le tri par lieu compare séparément région associée, carte puis donjon, avec des en-têtes de groupes. Une indication de famille sans rattachement régional reste « Île / région non renseignée » ; une carte absente reste « Carte non précisée ». Les ingrédients sans lieu restent dans « Lieu inconnu ». Pour plusieurs sources, la première source dans cet ordre sert au regroupement, les autres restent affichées. Ce regroupement n'est pas un calcul d'itinéraire optimal et ne complète pas les coordonnées ou hiérarchies géographiques absentes.

Les fiches objets associent chaque monstre source à ses propres lieux (donjon référencé ou indication de famille explicitement approximative). Un monde associé à un donjon n’est plus assimilé à une île/région. En tri géographique du panier, un ingrédient apparaît dans chaque lieu référencé, avec état de collecte commun par ID et sans multiplication du total. Les monstres sources sans lieu restent visibles.

### Stock propre au panier
Les champs « Déjà en stock » des composants et le récapitulatif repliable sous les ingrédients sont enregistrés avec le panier dans le navigateur. Le stock est alloué une seule fois après agrégation des besoins, avant arrondi des fabrications et décomposition des composants restants. Un composant entièrement couvert reste visible comme disponible en stock ; ses sous-recettes inutiles sont retirées du plan et les passages artisans sont recalculés. Les cases de progression ne représentent pas le stock. Remettre le champ à zéro rétablit le besoin. Aucun inventaire du jeu n’est consulté. Le stock couvre les ingrédients, pas les fabrications finales explicitement demandées ; les produits secondaires ne sont pas réutilisés. Tests : web/test_cart_stock.py.


### Précision géographique — correction générale du 3 octobre 2026

Les archives officielles courantes `contents/maps/data.jar` (`worlds.lib`) et `contents/maps/paper/full.jar` sont désormais importées automatiquement. Le lecteur suit la sérialisation de `cdH`, `cdI`, `bMh`, `cdJ`, `cdK`, `Ne`, `Vt`, `Vs` et `UL`, vérifie les limites de chaque enregistrement et rejette les octets supplémentaires. La base contient 720 cartes, 274 territoires dont 248 avec traduction française officielle (`content.66`). Les noms techniques internes ne remplacent jamais un nom absent.

La cause principale des mauvaises entrées de donjon était une jointure incorrecte : `map_points.link_id` désigne une référence d’entrée, pas directement `client_dungeons.id`. Le client résout cette référence avec `bLa.d → eQN.QO → eQO`, depuis la liste `aKU.cnk` (champ binaire 8). L’import applique maintenant cette correspondance à tous les donjons : 109 entrées retenues, 106 donjons avec coordonnées. Exemple contrôlé : Hammamamoule, Bilbyza, entrée `(67, -42, 0)`, territoire Costa del Gelax. Les 33 candidats dont le rattachement ne concorde pas restent conservés dans les sources brutes et documentés dans `report.json`, sans publier leur coordonnée comme fiable. Ce contrôle prudent peut exclure une entrée distante légitime ; il ne prouve pas que ces candidats sont faux.

Les exigences d’écosystème des protecteurs sont reliées à leurs territoires explicites (`PROTECTOR.field_7`), comme dans `brg.dHy`. Cela produit 704 relations pour 692 créatures sur 93 territoires. Ces liens portent sur la **famille** de monstres : ils ne prouvent pas la présence de chaque variante, boss ou invocation. Ils restent identifiés comme indications de famille dans l’interface. Les coordonnées d’entrée sont rattachées aux cellules de territoire en suivant `bMh.dV → Vf/Ve → GS/UL`, y compris les coordonnées négatives ; une cellule ambiguë ne reçoit pas un territoire inventé.

Toutes les fiches d’objets, leurs monstres sources et les lignes du panier utilisent ces relations. Les regroupements affichent les noms connus dans l’ordre région/carte → territoire → donjon ; un ingrédient partagé entre lieux conserve sa quantité unique et ses cases synchronisées. Les emplacements des récoltes végétales et minérales et certaines créatures restent incomplets : aucune localisation n’est déduite d’une ressemblance de noms ou ajoutée à la main. Le calcul des ingrédients et le stock ne sont pas modifiés.

Validation : 25 tests, dont 6 contrôles géographiques (toutes les entrées reliées à la liste officielle, cohérence des régions, couverture globale, coordonnées négatives, ambiguïtés et lieux inconnus). Inspection visuelle des fiches et du tri du panier. Les prochaines mises à jour reconstruisent ces relations depuis les mêmes sources actuelles.

## Donjons et tableaux de butins

L’onglet Donjons présente chaque donjon référencé, trié par niveau par défaut, avec un tableau des objets provenant des monstres explicitement associés. Chaque objet apparaît une seule fois par donjon et liste ses monstres sources. Le filtre Types de butin permet d’afficher uniquement ou de masquer les catégories cochées, y compris leurs sous-catégories. Sans sélection, tous les objets apparaissent. Les donjons sans butin renseigné ou sans résultat après filtrage restent visibles. La recherche et la pagination permettent de parcourir tous les donjons de la base.

Ces tableaux décrivent les relations présentes dans la base de référence ; ils ne garantissent pas une liste exhaustive des récompenses, coffres ou conditions de butin actuels. Aucun taux pour un personnage ou mode de difficulté n’est déduit.

Les références de butin dont l’objet est absent du catalogue sont comptées dans une indication sous chaque tableau, sans lignes vides. Le filtre de rareté se combine avec les types de butin. Survoler un objet, ou lui donner le focus au clavier, affiche les effets d’équipement et d’utilisation présents dans la base. La bulle n’affiche pas le texte descriptif de l’objet et ne renvoie pas les effets vers la fiche. Les modèles conditionnels et paramètres dépendant du niveau sont évalués selon le client de référence ; les sections suivent les catégories de l’export, sans attribuer un marqueur critique absent.

Le lecteur `web/item_stats.py` est une implémentation indépendante des règles observées dans le client officiel de référence : formatage BN, paramètres eUj, calcul flottant et arrondi eVE/eVF. Il évalue les paires valeur + coefficient × niveau, conditions de présence/signe, comparaisons, pluriels imbriqués et libellés élémentaires sans exécuter les modèles comme du code. Les effets dépourvus de description sont conservés avec leur intitulé officiel et leurs valeurs, sans les masquer. Exemple vérifié : Baguette Ratée bourrue #12637, niveau 72, sept effets d’équipement dont 26 Maîtrise sur 1 élément, et deux dégâts Lumière d’utilisation de 28 et 35. L’export ne marque pas ces deux valeurs comme normale/critique ; elles restent dans la catégorie utilisation. Tests de formules : `web/test_item_stats.py`.

Les butins de tous les donjons sont triés par code de rareté décroissant (Épique, Souvenir, Relique, Légendaire, Mythique, Rare, Inhabituel, Commun), puis par taux brut de référence croissant à rareté égale. Pour un objet donné par plusieurs monstres du même donjon, le maximum des taux référencés sert au tri : sa source la plus accessible. Les taux absents viennent après les taux connus dans leur rareté ; les raretés inconnues viennent en dernier. Le nom puis l’identifiant stabilisent les égalités. Le tri est conservé avec les filtres et ne représente pas une probabilité cumulée ni un taux ajusté aux bonus du joueur.

Le filtre « Objets recherchés dans les donjons » permet de rechercher et d’ajouter jusqu’à 100 objets, d’en retirer un ou de vider la liste. La liste reste dans le navigateur. Il sélectionne les donjons ayant au moins une relation explicite de butin vers un objet demandé, avant le comptage et la pagination, indépendamment des filtres de types et raretés. Il ne restreint pas leurs tableaux aux seuls objets demandés : les lignes correspondantes sont encadrées et portent « Recherché ». Les filtres d’affichage existants continuent de masquer les butins concernés, sans exclure un donjon sélectionné par cette liste. Une liste vide inclut tous les donjons ; « Réinitialiser » vide aussi la liste.

### Recherches de donjons enregistrées

Le panneau « Mes recherches » permet de nommer et enregistrer autant de recherches que la capacité du navigateur le permet, sans plafond dans l’application. Il conserve le nom recherché, niveaux, tri, raretés, branches de catégories et sous-types, mode d’inclusion/exclusion des butins et liste des objets recherchés. « Charger » rappelle une sauvegarde ; « Enregistrer » crée une nouvelle sauvegarde ; « Mettre à jour » remplace volontairement les filtres et le nom de la sauvegarde sélectionnée ; « Supprimer » retire cette sauvegarde sans effacer les filtres affichés. « Nouvelle recherche » remet les critères des donjons à zéro sans toucher aux sauvegardes. Les mises à jour du catalogue ne les effacent pas. Les sauvegardes utilisent le stockage local du navigateur (`wakfu-dungeon-searches-v1`) : elles ne sont pas partagées entre appareils et sont effacées si les données du site sont supprimées. Un stockage plein affiche une erreur et conserve les sauvegardes précédentes.

### TIPS — Chasses
L’onglet principal TIPS propose une fiche Chasses : neuf emplacements et leurs statistiques doublées selon la couleur de la châsse. Les données reproduisent le tableau fourni par l’utilisateur ; chaque absence est explicitement indiquée par « Aucun ×2 ». Les trois couleurs ont aussi des libellés textuels. Le tableau défile horizontalement sur petit écran. Pour ajouter une fiche, compléter le registre `window.Tips.guides` de `web/tips.js` ; navigation interne et rendu sont générés depuis ce registre. Aucun appel à l’API de recherche n’est déclenché pour TIPS.
