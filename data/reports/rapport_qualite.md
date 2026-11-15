# Rapport de qualité des données

- Période : 2021-11-12 → 2026-11-12
- Jours de bourse : 1282
- Actifs : 31

## Contrôles automatiques

- ✔ Tous les prix sont strictement positifs
- ✔ Aucune date en double
- ✔ Dates dans l'ordre chronologique
- ✔ Aucune valeur manquante après nettoyage
- ✔ Taux USD/CAD entre 1.245 et 1.460 (plausible : 1.15 à 1.55)
- ✔ Aucune variation quotidienne de plus de 35% (erreur de données probable)

## Valeurs manquantes

| Symbole | Première date | Manquants avant nettoyage | Manquants après |
|---|---|---|---|
| AAPL | 2021-11-12 | 27 | 0 |
| AGG | 2021-11-12 | 27 | 0 |
| AMZN | 2021-11-12 | 27 | 0 |
| ATD.TO | 2021-11-12 | 27 | 0 |
| BTC-USD | 2021-11-12 | 0 | 0 |
| CNQ.TO | 2021-11-12 | 27 | 0 |
| CNR.TO | 2021-11-12 | 27 | 0 |
| CSU.TO | 2021-11-12 | 27 | 0 |
| ENB.TO | 2021-11-12 | 27 | 0 |
| ESGV | 2021-11-12 | 27 | 0 |
| ETH-USD | 2021-11-12 | 0 | 0 |
| FTS.TO | 2021-11-12 | 27 | 0 |
| GLD | 2021-11-12 | 27 | 0 |
| GOOGL | 2021-11-12 | 27 | 0 |
| JNJ | 2021-11-12 | 27 | 0 |
| JPM | 2021-11-12 | 27 | 0 |
| MFC.TO | 2021-11-12 | 27 | 0 |
| MSFT | 2021-11-12 | 27 | 0 |
| NVDA | 2021-11-12 | 27 | 0 |
| PG | 2021-11-12 | 27 | 0 |
| QQQ | 2021-11-12 | 27 | 0 |
| RY.TO | 2021-11-12 | 27 | 0 |
| SHOP.TO | 2021-11-12 | 27 | 0 |
| SPY | 2021-11-12 | 27 | 0 |
| TD.TO | 2021-11-12 | 27 | 0 |
| TLT | 2021-11-12 | 27 | 0 |
| TSLA | 2021-11-12 | 27 | 0 |
| XBB.TO | 2021-11-12 | 27 | 0 |
| XIU.TO | 2021-11-12 | 27 | 0 |
| XOM | 2021-11-12 | 27 | 0 |
| ZST.TO | 2021-11-12 | 27 | 0 |

## Variations quotidiennes de plus de 15%

40 variations repérées, dont 4 encore à expliquer. Chacune est soit un événement réel (conservé tel quel), soit une erreur (à corriger). Les explications viennent de `raw/added/explications_variations.csv` ; « hypothèse à confirmer » = événement connu de l'équipe, source à ajouter. Crypto : la variation du lundi cumule celles de la fin de semaine (prix ramenés au calendrier boursier).

| Date | Symbole | Variation | Explication | Statut |
|---|---|---|---|---|
| 2026-07-31 | AMZN | +15.4% | — | à expliquer |
| 2022-05-09 | BTC-USD | -15.4% | Effondrement du stablecoin TerraUSD (UST) et du jeton LUNA | hypothèse à confirmer |
| 2022-06-13 | BTC-USD | -22.2% | Gel des retraits chez le prêteur crypto Celsius (fin de semaine du 11-12 juin) | hypothèse à confirmer |
| 2023-03-13 | BTC-USD | +19.2% | Garantie des dépôts de Silicon Valley Bank par les autorités américaines (12 mars) et retour de l'USDC à 1 $ | hypothèse à confirmer |
| 2024-11-11 | BTC-USD | +15.9% | Hausse des cryptoactifs après l'élection présidentielle américaine | hypothèse à confirmer |
| 2022-05-09 | ETH-USD | -16.2% | Effondrement du stablecoin TerraUSD (UST) et du jeton LUNA | hypothèse à confirmer |
| 2022-05-30 | ETH-USD | +15.1% | Rebond après les pertes de mai (variation cumulée sur la fin de semaine) | hypothèse à confirmer |
| 2022-06-13 | ETH-USD | -27.2% | Gel des retraits chez le prêteur crypto Celsius (fin de semaine du 11-12 juin) | hypothèse à confirmer |
| 2022-07-18 | ETH-USD | +27.1% | Date provisoire annoncée pour « The Merge » (passage d'Ethereum à la preuve d'enjeu) | hypothèse à confirmer |
| 2022-11-08 | ETH-USD | -15.4% | Crise de liquidité de la plateforme FTX | hypothèse à confirmer |
| 2022-11-09 | ETH-USD | -17.2% | Crise de liquidité de la plateforme FTX (rachat par Binance abandonné) | hypothèse à confirmer |
| 2022-11-10 | ETH-USD | +17.2% | Rebond général après une inflation américaine (IPC d'octobre) plus faible que prévu | hypothèse à confirmer |
| 2023-03-13 | ETH-USD | +16.9% | Garantie des dépôts de Silicon Valley Bank par les autorités américaines (12 mars) et retour de l'USDC à 1 $ | hypothèse à confirmer |
| 2024-05-20 | ETH-USD | +18.4% | Signaux d'une approbation prochaine des FNB Ether au comptant par la SEC | hypothèse à confirmer |
| 2024-08-05 | ETH-USD | -19.0% | Repli mondial des marchés (dénouement des positions financées en yen) | hypothèse à confirmer |
| 2025-05-08 | ETH-USD | +22.8% | Mise à jour « Pectra » du réseau Ethereum (7 mai) | hypothèse à confirmer |
| 2026-08-19 | ETH-USD | +16.9% | — | à expliquer |
| 2023-05-25 | NVDA | +24.8% | Résultats trimestriels et prévisions de ventes fortement relevées (puces pour l'IA) | hypothèse à confirmer |
| 2024-02-22 | NVDA | +16.2% | Résultats du 4e trimestre (exercice 2024) meilleurs qu'attendu | hypothèse à confirmer |
| 2025-01-27 | NVDA | -16.7% | Annonce du modèle d'IA DeepSeek (crainte d'une baisse de la demande de puces) | hypothèse à confirmer |
| 2025-04-09 | NVDA | +18.3% | Suspension de 90 jours des droits de douane américains | hypothèse à confirmer |
| 2022-02-16 | SHOP.TO | -17.1% | Résultats du 4e trimestre 2021 et prévisions de croissance revues à la baisse | hypothèse à confirmer |
| 2022-10-27 | SHOP.TO | +17.1% | Résultats du 3e trimestre 2022 meilleurs qu'attendu | hypothèse à confirmer |
| 2022-11-10 | SHOP.TO | +16.5% | Rebond général après une inflation américaine (IPC d'octobre) plus faible que prévu | hypothèse à confirmer |
| 2023-02-16 | SHOP.TO | -15.5% | Résultats du 4e trimestre 2022 et prévisions prudentes | hypothèse à confirmer |
| 2023-05-04 | SHOP.TO | +23.2% | Résultats du 1er trimestre 2023 et vente de l'activité logistique à Flexport | hypothèse à confirmer |
| 2023-11-02 | SHOP.TO | +21.3% | Résultats du 3e trimestre 2023 meilleurs qu'attendu | hypothèse à confirmer |
| 2024-05-08 | SHOP.TO | -18.5% | Résultats du 1er trimestre 2024 et prévisions décevantes | hypothèse à confirmer |
| 2024-08-07 | SHOP.TO | +17.9% | Résultats du 2e trimestre 2024 meilleurs qu'attendu | hypothèse à confirmer |
| 2024-11-12 | SHOP.TO | +21.4% | Résultats du 3e trimestre 2024 meilleurs qu'attendu | hypothèse à confirmer |
| 2025-04-03 | SHOP.TO | -19.6% | Annonce de droits de douane américains généralisés (2 avril) | hypothèse à confirmer |
| 2025-04-09 | SHOP.TO | +17.5% | Suspension de 90 jours des droits de douane américains | hypothèse à confirmer |
| 2025-08-06 | SHOP.TO | +21.5% | Résultats du 2e trimestre 2025 (probable) | hypothèse à confirmer |
| 2026-05-05 | SHOP.TO | -15.6% | — | à expliquer |
| 2026-08-05 | SHOP.TO | +16.5% | — | à expliquer |
| 2024-04-29 | TSLA | +15.2% | Avancée vers l'autorisation de la conduite assistée (FSD) en Chine | hypothèse à confirmer |
| 2024-10-24 | TSLA | +21.9% | Résultats du 3e trimestre 2024 (marge meilleure qu'attendu) | hypothèse à confirmer |
| 2024-11-06 | TSLA | +15.4% | Résultat de l'élection présidentielle américaine | hypothèse à confirmer |
| 2025-03-10 | TSLA | -15.1% | Fort repli des valeurs technologiques américaines | hypothèse à confirmer |
| 2025-04-09 | TSLA | +22.3% | Suspension de 90 jours des droits de douane américains | hypothèse à confirmer |

## Traitements
- Clôture ajustée (dividendes et fractionnements).
- Crypto alignée sur le calendrier boursier.
- Trous ≤ 3 jours de bourse : report de la dernière valeur.
- Conversion USD → CAD au taux de la Banque du Canada du jour.

## Limites
- Biais de survie : l'univers ne contient que des actifs existants aujourd'hui.
- Données quotidiennes seulement ; aucune donnée intrajournalière.
