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

Détail et chiffres de contrôle : `docs/audit_donnees.md` (audit du 2026-11-14).

### Limites des données
1. **Biais de survie.** L'univers a été choisi en 2026 parmi des titres importants aujourd'hui : un rejeu depuis 2021 paraît
   meilleur que ce qu'aurait donné une sélection faite en 2021.
2. **Mesures en dollars canadiens (CAD).** Tous les montants, rendements et volatilités incluent l'effet de change USD/CAD
   (taux quotidien de la Banque du Canada). En 2022, la hausse du dollar américain a réduit d'environ 5 à 6 points les pertes
   des actifs américains (SPY : −18,2 % en USD, −12,6 % en CAD). Les traces, l'explication et l'interface le précisent.
3. **Rendement total brut.** `adj_close` réinvestit 100 % des dividendes : ni retenue à la source américaine (15 % pour un
   résident canadien hors REER), ni frais de gestion des FNB, ni frais de transaction, ni impôt.
4. **Données Yahoo Finance non certifiées.** Les valeurs ajustées changent si l'on retélécharge. Artefact connu : faux
   « split » 1,021 de CNQ.TO le 2022-08-22 (≈ 1 point de rendement sur ce jour), non corrigé.
5. **Calendriers.** Union TSX + NYSE, report de la dernière valeur sur 2 jours de bourse au plus (fériés). La crypto est
   ramenée aux jours de bourse ; son prix est la clôture du jour UTC, celui des actions la clôture de 16 h HE (décalage de
   quelques heures). Les mesures de risque sont hebdomadaires (vendredi), ce qui neutralise les fériés.
6. **Historique court.** Cinq ans (261 semaines) dominés par un seul cycle de hausse des taux (2022) : corrélations et
   volatilités estimées instables ; la pire baisse dépend de cet échantillon.
7. **Macro.** Seul le taux directeur de la Banque du Canada (V39079) est utilisé. L'IPC et le chômage sont exclus à cause de
   leur délai de publication. Les taux à 2 et 10 ans (Canada, É.-U.) et le taux des fonds fédéraux sont préparés mais pas
   encore exploités (amélioration possible : expliquer la baisse simultanée des obligations en 2022). Les séries FRED sont
   dans leur dernière version (révisées).
8. **Méthodologie ESG.** Ce n'est pas une note ESG : présence dans un FNB ESG (ESGV pour les É.-U., XESG pour le Canada,
   méthodes différentes : ESGV exclut l'énergie, XESG pondère sans exclure) + règle sectorielle de l'équipe (énergie =
   controverse). JNJ est « non évalué » : son exclusion d'ESGV n'a pas pu être vérifiée dans la liste complète du fonds. Pas de revue des
   controverses sociales ou de gouvernance. Instantané 2026 appliqué à toute la période (biais d'anticipation). FNB et
   crypto : statuts `conforme` (ESGV), `non applicable` (obligations, or, neutre) ou `non évalué` (traité comme
   information manquante, jamais comme conformité). La règle couvre tous les actifs détenus, FNB compris : pour Mateo,
   XIU.TO (portefeuille supposé, contient de l'énergie) apparaît toujours en information manquante.
9. **Portefeuilles supposés.** Les compositions par persona sont des hypothèses de l'équipe, pas des données de clients.
10. **Données fictives de démonstration.** Si `data/processed/` est absent, l'application utilise une série simulée
    (`chargeur._demo`), réservée au développement : un bandeau rouge l'annonce dans l'interface, l'explication le répète
    et `tests/test_donnees.py` échoue en mode `DONNEES=local`.

### Améliorations possibles
- Exploiter les taux à 10 ans (BD.CDN.10YR.DQ.YLD, DGS10) dans le contexte 2022.
- Vérifier JNJ dans la liste complète des titres d'ESGV ; évaluer TSLA avec une source ESG officielle datée.
- Évaluer les FNB (composition) pour la règle ESG plutôt que « non évalué ».
