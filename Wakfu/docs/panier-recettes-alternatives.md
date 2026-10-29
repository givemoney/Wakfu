# Recettes alternatives du panier

Chaque composant à fabriquer qui possède plusieurs recettes a son propre encadré rouge, placé avant les ingrédients de base. Le calcul sélectionne initialement la première recette, par identifiant croissant. Il produit donc un plan complet sans attendre une validation manuelle.

L’encadré présente les quantités d’ingrédients de chaque possibilité pour le besoin restant après le stock, avec les arrondis de fabrication et les surplus éventuels. Choisir une autre recette recalcule le panier. Valider replie uniquement cet encadré ; son résumé indique les ingrédients retenus. Le résumé reste cliquable pour rouvrir et modifier le choix. Les contrôles sont temporairement désactivés pendant le recalcul afin de ne pas valider une ancienne réponse.

Les choix et leur validation sont enregistrés avec le panier dans le navigateur (`choices`, `confirmedChoices`). Les paniers existants sans validation restent compatibles : leurs choix sont conservés et leurs encadrés sont ouverts à la première consultation. Les choix de composants temporairement absents sont conservés, notamment lorsque le stock couvre tout le besoin. « Revoir les choix de recettes » déploie tous les encadrés présents sans changer la sélection. Vider le panier supprime aussi ses choix et validations.

Un composant entièrement en stock n’a ni fabrication ni encadré à valider. Les étapes des autres composants et le stock partagé continuent de fonctionner comme auparavant. Les ingrédients alternatifs ne sont pas choisis automatiquement selon un prix ou une disponibilité supposée.

## Vérifications

Les tests `web/test_cart_choices.py` couvrent la première recette stable, le choix explicite, les stocks partiels et complets, les besoins partagés, les composants ambigus indépendants, les dépendances du plan et les cycles. Le cas de la Canne Iboul et du Coutelas des Âges Farouches, avec trois outils intermédiaires de chaque en stock, a aussi été recalculé sur la base de référence. La navigation, le changement d’option, la validation, le repli, la réouverture et le rechargement ont été vérifiés dans une origine de test distincte pour préserver le panier personnel.
