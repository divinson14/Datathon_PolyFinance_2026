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
  Mesure (audit du 2026-11-14) : ce jour-là `adj_close` fait +2,8 % contre +0,6 % pour `close` ; le dividende de 0,75 $
  explique ≈ 1 point de l'écart, le reste (≈ 1 point) est l'artefact.
- Fériés propres à une bourse : le calendrier est l'union TSX + NYSE ; un jour férié d'un seul côté donne un rendement
  nul aux titres de l'autre place (report de la veille). Sans effet sur les mesures hebdomadaires ; pour la pire fenêtre
  de 12 mois (quotidienne, 252 jours de bourse), la fenêtre couvre légèrement moins de 12 mois civils.
- Macro : seule V39079 (taux directeur) est lue par l'application. Les séries BD.CDN.2YR, BD.CDN.10YR, DFF, DGS2 et DGS10
  sont copiées dans `macro_quotidien.csv` mais **non utilisées** (piste : expliquer la baisse de XBB et TLT en 2022).
- Toutes les mesures sont **en CAD** (effet de change inclus) : SPY 2022 = −18,2 % en USD mais −12,6 % en CAD.
  Les traces de calcul, l'explication et l'interface le précisent.

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
Sortie : `data/processed/esg_drapeaux.csv` (via `02_construire_esg.py`). Sources détaillées dans `data/sources/sources_added.csv`.

- **Titres détenus par des FNB ESG** (`raw/added/esg_etf_holdings.csv`) :
  - ESGV (Vanguard, données au 2026-11-12) pour les 10 actions américaines : relevé manuel des 40 premiers titres ;
    un titre absent de ce top 40 (poids < 0,35 %) est considéré comme exclu.
  - XESG (iShares, fichier de l'émetteur au 2026-10-02) pour les 10 actions canadiennes, car ESGV ne détient que des
    actions américaines. XESG n'est pas dans l'univers ; il sert seulement de référence. `dans_fnb_esg` = « dans ESGV ou XESG ».
- **Statuts ESG** (`raw/added/esg_controverses.csv`, colonne `controverse`, une ligne par actif de l'univers) :

  | Statut | Actifs | Effet dans le moteur de règles |
  |---|---|---|
  | `oui` | ENB.TO, CNQ.TO, XOM | ❌ viole la règle « Exclusions ESG » |
  | `non` | 16 actions (dont TSLA) | ✅ respecte la règle |
  | `conforme` | ESGV (FNB filtré ESG) | ✅ comme `non` |
  | `non applicable` | XBB.TO, ZST.TO, AGG, TLT, GLD | ➖ **neutre** : ni confirmé conforme, ni information manquante |
  | `non évalué` | XIU.TO, SPY, QQQ, BTC-USD, ETH-USD, JNJ | ⚠️ information manquante, jamais déclaré conforme |

  Colonne `motif` (pour les `oui`) : « secteur énergie (règle de l'équipe) » ou « exclu par ESGV (Vanguard) ».
  Les 3 `oui` actuels relèvent tous de la règle énergie (XOM est en plus absente du top 40 d'ESGV).
- **Règle « énergie = exclusion » (choix de l'équipe).** Tout titre du secteur Énergie (GICS) de l'univers est marqué
  controverse importante, qu'il soit ou non détenu par un FNB ESG. Raison : l'énoncé demande d'exclure les entreprises
  liées à des controverses environnementales importantes ; pipelines (ENB), sables bitumineux (CNQ) et pétrole intégré (XOM)
  en sont l'exemple le plus défendable et le plus simple à expliquer. C'est une règle **sectorielle**, pas une évaluation
  entreprise par entreprise : elle est stricte pour l'énergie et aveugle aux controverses des autres secteurs.
- **Désaccord XESG / ESGV.** Les deux FNB de référence ne suivent pas la même logique :
  - ESGV (Vanguard, indice FTSE US All Cap Choice) **exclut** l'énergie fossile et filtre la conduite des entreprises ;
  - XESG (iShares, indice MSCI Canada ESG Focus) **pondère** selon les notes ESG MSCI **sans exclure** l'énergie :
    ENB et CNQ y figurent.
  Si l'on suivait XESG, ENB et CNQ seraient « sans controverse » ; si l'on suivait ESGV, elles seraient exclues. L'équipe
  tranche par sa règle énergie (exclusion), cohérente avec ESGV. `dans_fnb_esg` (« dans ESGV ou XESG ») n'a donc pas le même
  sens pour une action canadienne et pour une action américaine : il est affiché, mais le moteur ne s'en sert pas.
- **JNJ : exclusion d'ESGV à vérifier dans la liste complète du fonds — sinon passer en "non évalué".**
  Tentative du 2026-11-14 : la liste complète (https://investor.vanguard.com/investment-products/etfs/profile/esgv,
  onglet Portfolio) est une page dynamique non consultable par l'outil ; seule piste trouvée, un article d'opinion
  (https://seekingalpha.com/article/4707741-esgv-diversification-is-key-for-esg-investors) citant JNJ parmi les exclusions
  par filtre de conduite — insuffisant. **JNJ est donc passée en « non évalué »** (motif retiré). À reprendre à la main :
  télécharger la liste complète des titres d'ESGV et noter URL + date dans `sources_added.csv`.
- Traçabilité : `esg_etf_holdings.csv` porte, pour chaque titre, le FNB de référence (`fnb` : ESGV ou XESG) et la date
  du relevé de l'émetteur (`date_donnees`).
- **Limites** :
  - règle simplifiée, sans revue détaillée par entreprise : elle ne capte pas les controverses sociales
    ou de gouvernance que les filtres ESGV/XESG ne reflètent pas ;
  - méthodologies d'émetteurs différentes (voir le désaccord ci-dessus) ;
  - instantané 2026 appliqué à toute la période (biais d'anticipation).
- **Conséquence pour Mateo** : TSLA est `non` (détenue par ESGV, hors énergie). Une évaluation ciblée de TSLA avec une
  source officielle datée reste une amélioration possible.
- **Périmètre du moteur** (décision du 2026-11-14) : la règle « Exclusions ESG » s'applique à **tous les actifs détenus**,
  FNB compris (avant : actions et crypto seulement). Raison : Mateo exclut les controverses mais son portefeuille supposé
  contient 25 % de XIU.TO, qui détient ENB et CNQ ; ignorer les FNB revenait à valider en silence un actif non évalué.
  Conséquence : chaque réponse à Mateo signale « non évalué : XIU.TO (portefeuille supposé) » comme **information manquante**
  (⚠️, pas une violation) ; le statut, le point de bascule et les alternatives ne changent pas. Le libellé
  « (portefeuille supposé) » indique que le manque ne vient pas de la demande. Les tensions de profil (Agent Gouvernance)
  suivent le même périmètre.

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

## Bedrock Guardrails (src/verif/guardrails.py, bedrock_client.appliquer_guardrail)
- **Rôle** : filet de sécurité AWS, en plus des garde-fous en code. Il ne calcule rien et ne remplace ni le moteur
  de règles ni le vérificateur de fidélité ; il bloque ce qui ne doit ni entrer ni sortir (transaction réelle,
  conseil personnalisé, contenu inapproprié, tentative de contournement).
- **Entrée** (début de l'orchestrateur) : regex locale (rapide, sans AWS), PUIS ApplyGuardrail `source=INPUT`
  si MODE=bedrock et `BEDROCK_GUARDRAIL_ID` défini. Guardrails est consulté même si la regex bloque déjà :
  la trace montre les deux verdicts. Intervention → arrêt « Demande bloquée par Bedrock Guardrails : … ».
  Une politique en mode « Detect » (action NONE, `detected: true`) est affichée dans la trace et l'étape
  (« détecté par Bedrock Guardrails : Transaction-reelle ») sans bloquer.
- **Les sujets refusés bloquaient des simulations légitimes à l'entrée** (faux positifs mesurés : 8/13, puis 5, puis 3)
  → **détection en entrée, blocage en sortie** ; les ordres réels restent bloqués par une règle en code
  (regex de l'Agent Profil). Mesure : `python tests/verifier_guardrail.py` (rapide) ou `--complet` (14 scénarios).
- **Règle en code des ordres réels** (`profil.MOTS_TRANSACTION`) : un ordre = l'utilisateur demande à l'assistant d'AGIR.
  Motifs : verbe d'achat / vente suivi de « moi » ou « pour moi » (fautes tolérées : « achte moi », « achete ») ; impératif
  en début de phrase (« Achetez… », « Vends… ») ; demande directe (« tu peux m'acheter… ») ; « passer un ordre » ;
  « exécute la transaction ». Une hypothèse (« si j'achète… », « je pense mettre… », « bon investissement pour moi ? »)
  n'est PAS un ordre. Correction du 2026-11-15 : « achte moi 30% d'action chez tesla » passait (faute de frappe),
  « si j'achète 30 % de Tesla, quel risque ? » était bloqué. 15 ordres et 9 simulations testés (tests/test_guardrails.py).
- **Sortie** (fin de `rediger_verifie`, donc aussi pour les reformulations) : ApplyGuardrail `source=OUTPUT` sur le
  texte réellement affiché. Intervention → message de remplacement sûr (aucun chiffre, aucun conseil) + trace.
- **Traces** « Bedrock Guardrails · demande / réponse » : action (NONE / GUARDRAIL_INTERVENED), politiques
  déclenchées lues dans les `assessments`, ID et version du guardrail, latence. Ce sont des traces de CONTRÔLE
  (`controle=True`) : le vérificateur de fidélité ne les utilise jamais comme source de chiffres.
- **Panne** (droits IAM, réseau, guardrail inexistant) : pas de plantage ; trace « Guardrails indisponible » ;
  l'étape affiche « garde-fou local seulement ». Sans guardrail configuré (MODE=local) : « garde-fou local seulement ».
- **Pas de guardrail sur les appels internes des agents** (Converse, Strands) : leurs prompts contiennent des consignes
  (« aucun conseil personnalisé »…) qu'un sujet refusé bloquerait à tort. Guardrails contrôle ce que l'utilisateur
  écrit et ce qu'il lit.
- Version vide dans .env → `DRAFT`.
- **Politiques configurées** (guardrail `7xq7ledpn2cm`, console Bedrock > Guardrails) :

  | Politique | Entrée (demande) | Sortie (réponse affichée) | Pourquoi |
  |---|---|---|---|
  | Sujet refusé « Transaction-reelle » | Detect | Block | Aucun ordre réel ; en entrée, la règle en code bloque (le sujet attrapait des simulations) |
  | Sujet refusé « Promesse-de-rendement » | Detect | Block | Aucune promesse de rendement dans une réponse ; en entrée, « tout le monde parle de Tesla » était bloqué |
  | Filtres de contenu, mots interdits, informations sensibles, message de blocage | *à compléter par l'équipe* | | |

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
- 2026-11-14 — Sens du taux USD/CAD vérifié : `usdcad` varie de 1,245 à 1,460, donc CAD pour 1 USD ; les prix en USD
  sont multipliés par ce taux, sans inversion — conforme à `sources_metadata.csv` (série FXUSDCAD de la Banque du Canada) — P1
- 2026-11-14 — Trous dans les séries : report de la dernière valeur sur 3 jours de bourse au plus — les trous viennent
  des fériés propres à la TSX ou aux bourses américaines (27 jours par titre sur 5 ans) ; aucun trou plus long n'existe,
  donc aucune valeur inventée au-delà d'un congé — P1
- 2026-11-14 — Audit des données (docs/audit_donnees.md) : aucun point bloquant ; bandeau « données fictives »,
  test anti-repli (tests/test_donnees.py), mention CAD dans traces/explication/interface, limites documentées — P1
- 2026-11-14 — Correction de `01_nettoyer_prix.py` : le report se fait maintenant APRÈS la réduction aux jours de bourse —
  avant, les fins de semaine (lignes crypto) comptaient dans la limite de 3 et les 13 titres `.TO` gardaient 3 trous
  (2021-12-28, 2022-12-27, 2023-12-26 : Noël TSX collé à un week-end). Résultat : 0 valeur manquante sur les 31 actifs — P1
