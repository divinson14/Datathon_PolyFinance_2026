# Décisions et hypothèses

Notez ici chaque choix au fil de l'eau : c'est la moitié de la documentation technique.

## Formats d'échange (figés à H0)
- **Mandat** : persona (`app/config/personas/*.json`) + gabarit (`app/config/gabarits_risque.yaml`) + demande extraite `{symbole, part}`.
- **Trace** : `{id, session, horodatage, titre, agent, outil, entrees, sortie, source, periode}`.
- **Verdict** : `{trace, regles: [{regle, limite, valeur, ok}], violees, consigne}`.
- **Réponse** : `{intro, lignes: [{tag: Fait|Hypothèse|Scénario fictif, texte, traces}], limites, style}`.

## Méthode de calcul (app/config/calcul.yaml, app/src/outils/calculs.py)
- Prix : `adj_close` (dividendes et fractionnements déjà intégrés, ne rien réappliquer), convertis en CAD
  avec le taux Banque du Canada reporté sur les jours sans taux (fériés, fins de semaine crypto).
- Rendements **hebdomadaires** (clôture du vendredi), 261 semaines du 2021-11-19 au 2026-11-13 : neutralise
  les calendriers TSX / NYSE / crypto 7 j/7. Annualisation × 52.
- Portefeuille à **poids constants** (rééquilibré chaque semaine) pour volatilité, pire baisse et part du risque ;
  le rejeu 2022 est en achat-conservation (plus parlant en dollars). Les deux hypothèses sont affichées.
- **Part du risque** = contribution d'Euler à la variance : w_i·(Σw)_i / w'Σw (somme = 100 %).
- **Paris indépendants** = ratio de participation des valeurs propres de diag(w)·Σ·diag(w) : (Σλ)²/Σλ².
  N lignes indépendantes de même risque → N ; un seul facteur dominant → 1.
  ⚠️ Cette définition ne redonne pas le « 1,9 » de l'exploration (portefeuille Amira à parts égales : 2,6) : citer 2,6.
- **Point de bascule** : grille de 0 à 100 % par pas de 0,5 point ; part maximale de l'actif demandé (le reste
  du portefeuille est réduit proportionnellement) qui respecte toutes les règles, et première règle franchie.
- Macro : seules les séries **quotidiennes** sont copiées dans `processed/macro_quotidien.csv`. IPC et chômage
  (datés au mois de référence, publiés des semaines plus tard) sont exclus pour ne pas « voir le futur ».
- Correction des données : le report du taux de change se faisait sur la table longue (mélange possible entre symboles) ;
  il est maintenant fait sur le calendrier civil complet avant la fusion.
- CNQ.TO : faux « split » 1,021 le 2022-08-22 (probable distribution spéciale) déjà intégré par Yahoo dans `adj_close`. Effet ≈ 2 %, non corrigé, documenté.

## Seuils des gabarits (hypothèses de l'équipe, app/config/gabarits_risque.yaml)
« Titre » = action individuelle ou crypto. Les FNB diversifiés ne sont pas soumis aux limites par titre.

| Gabarit | Poids max/titre | Part du risque max/titre | Vol. max | Pire baisse max | Oblig. min | Crypto max | Paris min |
|---|---|---|---|---|---|---|---|
| Faible à modéré (Robert) | 10 % | 20 % | 8 % | -12 % | 40 % | 0 % | — |
| Modéré (Mateo) | 15 % | 25 % | 12 % | -20 % | 20 % | 0 % | — |
| Élevé (Amira) | 25 % | 30 % | 25 % | -45 % | 0 % | 10 % | 2,0 |

Justification à compléter (NT). Contrainte vérifiée par un test : chaque portefeuille supposé respecte son propre gabarit.

## Portefeuilles supposés (hypothèses affichées à l'utilisateur, mesures sur données réelles)
| Persona | Portefeuille | Vol. | Pire baisse | Paris indép. |
|---|---|---|---|---|
| Robert | XBB 30, ZST 30, XIU 15, SPY 15, FTS 5, GLD 5 | 5,2 % | -9,2 % | 2,5 |
| Mateo | ESGV 30, XIU 25, XBB 30, ZST 5, FTS 5, GLD 5 | 8,4 % | -14,3 % | 1,7 |
| Amira | XIU 15, SPY 20, QQQ 20, XBB 10, GLD 5, NVDA/SHOP/MSFT/JNJ 5 chacun, BTC 5, ETH 5 | 16,2 % | -30,2 % | 2,6 |

Points de bascule obtenus (TSLA) : Robert 3 %, Mateo 6 %, Amira 13 %. Règle limitante dans les trois cas : part du risque par titre.
Robert à 30 % TSLA : TSLA porte 89,5 % du risque. Crypto : bascule à 0 % pour Robert et Mateo (interdite) et pour Amira (déjà au plafond de 10 %).

## ESG (Mateo)
`data/raw/added/esg_controverses.csv` est encore vide : tous les titres sont « non évalué ». Le moteur ne les déclare
**pas** conformes : il les signale comme information manquante (UI ⚠️, ligne dans l'explication). À remplir (NT), puis lancer `02_construire_esg.py`.

## Agent Profil (app/src/agents/profil.py, config/profil.yaml, config/alias_actifs.yaml)
- **Mandat JSON** = profil + gabarit + contraintes + horizon en années + informations manquantes + tensions + hypothèses + demande.
  Le profil vient d'un persona de référence OU de 5 champs saisis (âge, tolérance, horizon, objectif, ESG ; capital facultatif).
- **La tolérance au risque n'est jamais déduite** : si elle manque, l'agent s'arrête et la demande.
- **Tensions** entre champs (ex. tolérance élevée + horizon < 7 ans, seuils dans config/profil.yaml) : signalées dans
  l'interface et l'explication, jamais corrigées à la place de l'utilisateur. L'âge n'est volontairement pas utilisé dans une règle.
- Profil saisi : capital fictif par défaut et portefeuille supposé selon la tolérance, affichés comme hypothèses.
- **Extraction de la demande** : le LLM choisit l'actif et recopie l'extrait (« 30 % », « 50 000 $ ») ; le code vérifie que
  l'extrait est dans le message (contrôle d'ancrage) puis calcule la part. Un montant ≥ capital n'est pas une part.
  Plusieurs actifs cités ou part hors de 0–100 % → question à l'utilisateur. Deux traces : « Construction du mandat », « Extraction de la demande ».

## Agent Explicabilité (app/src/agents/explicabilite.py, prompts/explicabilite.md, config/garde_fous.yaml)
- **On décrit des limites, jamais de conseil** (énoncé : « ne pas se présenter comme fournissant un conseil
  financier personnalisé »). Ex. : « le point de bascule se situe à 3 % », jamais « mettez 3 % ».
- **Vérificateur de fidélité, deux contrôles en code pur** : (1) chaque chiffre du texte existe dans les traces ;
  (2) aucune expression de conseil (liste dans config/garde_fous.yaml). Échec → régénération stricte, puis gabarit sûr.
  Le contrôle s'applique aussi aux reformulations (« plus simple / plus technique »).
- **Synthétique** : 4 à 6 affirmations, dans l'ordre part des dollars vs part du risque, règles violées, point de bascule,
  rejeu 2022, hypothèse clé. « Fait » = ce qu'une trace dit explicitement ; aucun lien de cause inventé.
- **Courbe de bascule** : part du risque portée par l'actif selon son poids (grille de l'outil point_de_bascule, trace citée),
  limite du profil, point de bascule et demande. Image descriptive, aucune recommandation.
- Rédaction : Claude Sonnet 5.5 sur Bedrock, 4 000 jetons max (1 500 tronquait la réponse JSON). Tout échec Bedrock
  (identifiants expirés, réponse tronquée ou illisible) bascule sur le gabarit, avec le motif affiché.
- Testé sur Bedrock (Robert, TSLA 30 %) : 6 affirmations, 33/33 chiffres vérifiés, aucune formulation de conseil, ~24 s.

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
