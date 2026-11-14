# Décisions et hypothèses

Notez ici chaque choix au fil de l'eau : c'est la moitié de la documentation technique.

## Formats d'échange (figés à H0)
- **Mandat** : persona (`app/config/personas/*.json`) + gabarit (`app/config/gabarits_risque.yaml`) + demande extraite `{symbole, part}`.
- **Trace** : `{id, session, horodatage, titre, agent, outil, entrees, sortie, source, periode}`.
- **Verdict** : `{trace, regles: [{regle, limite, valeur, ok}], violees, consigne}`.
- **Réponse** : `{intro, lignes: [{tag: Fait|Hypothèse|Scénario fictif, texte, traces}], limites, style}`.

## Seuils des gabarits (hypothèses de l'équipe)
| Gabarit | Poids max/titre | Volatilité max | Perte max | Crypto max | Justification |
|---|---|---|---|---|---|
| Faible à modéré | 5 % | 10 % | -15 % | 0 % | À compléter |
| Modéré | 10 % | 15 % | -25 % | 0 % | À compléter |
| Élevé | 15 % | 25 % | -35 % | 10 % | À compléter |

## Portefeuilles supposés
Le persona ne donne pas son portefeuille actuel → hypothèse affichée à l'utilisateur.
⚠️ XIU et XBB sont des exemples : remplacez-les par des symboles présents dans `assets_universe.csv`.

## Services AWS
| Service | Pourquoi |
|---|---|
| Bedrock | LLM des agents ; petit modèle pour l'extraction, modèle plus capable pour la rédaction |
| Bedrock Guardrails | Bloque transactions réelles et conseil personnalisé |
| S3 | Données propres produites par data/ |
| Lambda | Outils de calcul isolés, rôle IAM en lecture seule |
| DynamoDB | Journal d'audit des traces |

## Journal des choix
- AAAA-MM-JJ — choix — raison — qui
