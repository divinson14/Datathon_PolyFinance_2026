# Documentation technique — AlphaForge AI

## 1. Problème choisi
## 2. Architecture agentique
(Insérer docs/architecture.svg ; rôle de chaque agent et pourquoi il existe.)
## 3. Données
Sources, actifs retenus, traitements (voir data/reports/rapport_qualite.md), hypothèses, licences.
## 4. Méthodes et technologies
Modèles Bedrock choisis et pourquoi ; calculs (volatilité annualisée, rejeu 2022, etc.).
## 5. Mécanisme d'explicabilité
Exemple complet : une phrase de la réponse → son ID de trace → l'appel d'outil → les données sources.
## 6. Validation
Tableau produit par `python app/tests/lancer_scenarios.py` ; tests unitaires.
## 7. Limites et améliorations
