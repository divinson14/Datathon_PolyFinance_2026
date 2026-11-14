# Rapport de qualité des données

- Période : 2021-11-12 → 2026-11-12
- Jours de bourse : 1282
- Actifs : 31

| Symbole | Première date | Manquants avant nettoyage | Manquants après |
|---|---|---|---|
| AAPL | 2021-11-12 | 27 | 0 |
| AGG | 2021-11-12 | 27 | 0 |
| AMZN | 2021-11-12 | 27 | 0 |
| ATD.TO | 2021-11-12 | 27 | 3 |
| BTC-USD | 2021-11-12 | 0 | 0 |
| CNQ.TO | 2021-11-12 | 27 | 3 |
| CNR.TO | 2021-11-12 | 27 | 3 |
| CSU.TO | 2021-11-12 | 27 | 3 |
| ENB.TO | 2021-11-12 | 27 | 3 |
| ESGV | 2021-11-12 | 27 | 0 |
| ETH-USD | 2021-11-12 | 0 | 0 |
| FTS.TO | 2021-11-12 | 27 | 3 |
| GLD | 2021-11-12 | 27 | 0 |
| GOOGL | 2021-11-12 | 27 | 0 |
| JNJ | 2021-11-12 | 27 | 0 |
| JPM | 2021-11-12 | 27 | 0 |
| MFC.TO | 2021-11-12 | 27 | 3 |
| MSFT | 2021-11-12 | 27 | 0 |
| NVDA | 2021-11-12 | 27 | 0 |
| PG | 2021-11-12 | 27 | 0 |
| QQQ | 2021-11-12 | 27 | 0 |
| RY.TO | 2021-11-12 | 27 | 3 |
| SHOP.TO | 2021-11-12 | 27 | 3 |
| SPY | 2021-11-12 | 27 | 0 |
| TD.TO | 2021-11-12 | 27 | 3 |
| TLT | 2021-11-12 | 27 | 0 |
| TSLA | 2021-11-12 | 27 | 0 |
| XBB.TO | 2021-11-12 | 27 | 3 |
| XIU.TO | 2021-11-12 | 27 | 3 |
| XOM | 2021-11-12 | 27 | 0 |
| ZST.TO | 2021-11-12 | 27 | 3 |

## Traitements
- Clôture ajustée (dividendes et fractionnements).
- Crypto alignée sur le calendrier boursier.
- Trous ≤ 3 jours : report de la dernière valeur.
- Conversion USD → CAD au taux de la Banque du Canada du jour.

## Limites
- Biais de survie : l'univers ne contient que des actifs existants aujourd'hui.
- Données quotidiennes seulement ; aucune donnée intrajournalière.