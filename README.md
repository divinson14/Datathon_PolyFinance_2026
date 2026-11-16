# InvestIA
**On ne vous dit pas quoi acheter. On vous montre jusqu'où votre décision reste cohérente avec vous.**

Copilote d'investissement **agentique et auto-explicatif**, en simulation. Datathon PolyFinances 2026 ·
Banque Nationale × AWS.

- **Outil déployé :** https://datathonpolyfinance2026-mxffdccgcsajtvrgwrguj8.streamlit.app 
- **Vidéo de démonstration :** https://drive.google.com/file/d/1m3k_9L89c2hqjmGbsCBXVWMsSA_yzjpL/view?usp=sharing
- **One-pager :** [`docs/one_pager.md`](docs/one_pager.md) · **Documentation technique :** [`docs/documentation_technique.md`](docs/documentation_technique.md)

> Simulation éducative sur des profils fictifs : aucune transaction réelle, aucun conseil financier personnalisé.
> Les performances passées ne prédisent pas les résultats futurs.

---

## Le problème, la réponse
On pense en dollars, mais un portefeuille réagit au risque : pour un investisseur prudent, **30 % en Tesla, c'est
près de 90 % du risque** de tout son portefeuille. InvestIA répond à une question simple : *ce placement est-il
cohérent avec mon profil, et sinon, jusqu'où le serait-il ?* C'est le **point de bascule** : même question, prudent
**3 %**, équilibré **6 %**, audacieux **13 %**. Chaque chiffre affiché renvoie à la preuve de son calcul.

## Essayer en 2 minutes (dans l'outil)
1. Choisir **Robert**, puis écrire : `Tout le monde parle de Tesla, je pense mettre 30 % dedans. Bonne idée ?`
2. Lire le verdict, la **courbe de bascule**, puis ouvrir **« Voir comment j'ai décidé »** (les agents, un par un)
   et **« Voir les traces »** (le journal d'audit).
3. Enchaîner : `et à 5 % ?`, puis `et qu'en est-il pour NVIDIA ?` (la mémoire reprend l'actif ou la part, et le dit).
4. Changer pour **Amira** ou **Mateo** et reposer la même question : même demande, autre limite.
5. Tester les garde-fous : `Achète-moi 10 % de Tesla` (transaction réelle refusée), `bonjour` (aucune analyse lancée).

---

## Installation et lancement (sans compte AWS)
**Prérequis :** Python **3.11 ou plus récent** (développé et testé avec 3.14), Git. Les données de marché déjà
nettoyées sont **incluses dans le dépôt** : rien à télécharger.

**macOS / Linux**
```bash
git clone https://github.com/divinson14/Datathon_PolyFinance_2026.git
cd Datathon_PolyFinance_2026/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run ui/streamlit_app.py
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/divinson14/Datathon_PolyFinance_2026.git
cd Datathon_PolyFinance_2026\app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run ui/streamlit_app.py
```

L'application s'ouvre sur http://localhost:8501. Avec `.env` tel quel (`MODE=local`), **les calculs, le moteur de
règles, le vérificateur et les traces sont réels** ; seuls les textes des agents viennent de gabarits au lieu
d'Amazon Bedrock. Le bandeau en haut à droite indique le mode actif.

## Lancement avec AWS (mode complet)
1. **Identifiants AWS** dans le terminal, jamais dans le code ni dans git : `aws configure`, un profil SSO, ou les
   variables `export AWS_…` fournies par l'événement. Région : `us-east-1`.
2. **Accès aux modèles** : console Amazon Bedrock, activer un modèle rapide et un modèle de rédaction.
3. **Compléter `app/.env`** :

| Variable | Rôle | Exemple |
|---|---|---|
| `MODE` | `local` (gabarits) ou `bedrock` (agents LLM) | `bedrock` |
| `BEDROCK_MODELE_RAPIDE` | Agent Profil | `us.anthropic.claude-haiku-5-5` |
| `BEDROCK_MODELE_REDACTION` | Explicabilité, Gouvernance, Analyste | `us.anthropic.claude-sonnet-5-5` |
| `BEDROCK_GUARDRAIL_ID` / `_VERSION` | Bedrock Guardrails (demande et réponse) | ID de la console |
| `ANALYSTE` | `strands` (agent qui choisit ses outils) ou `fixe` | `strands` |
| `LAMBDA_OUTILS_URL` | Function URL des outils de calcul (signée IAM) | déjà renseignée |
| `DONNEES`, `S3_BUCKET`, `S3_PREFIX` | Lecture des données dans Amazon S3 | `s3`, nom du bucket, `processed/` |
| `TRACES`, `DYNAMODB_TABLE` | Journal d'audit dans Amazon DynamoDB | `dynamodb`, `alphaforge-traces` |

4. **Vérifier** (depuis `app/`) : `python tests/tester_profil.py --aws` (identifiants, région, modèles), puis
   `python tests/tester_profil.py --bedrock` (vrais appels, quelques centimes).
5. Relancer `streamlit run ui/streamlit_app.py`.

Mise en place des ressources (bucket privé et chiffré, table à la demande, Function URL IAM, guardrail) :
[`app/README.md`](app/README.md) et [`docs/decisions.md`](docs/decisions.md).

---

## Architecture
**Le code juge et calcule, le LLM comprend et rédige, le code vérifie ce que le LLM a écrit.**

```
Message ─► Garde-fous (règle locale + Bedrock Guardrails)
        ─► Agent Profil ........ mandat JSON (profil + limites) et demande {actif, part}     Claude Haiku
        ─► Agent Analyste ...... choisit ses outils de calcul (AWS Lambda)                 Claude Sonnet · Strands
        ─► Agent Gouvernance ... juge le mandat (moteur de règles, code) ; le LLM formule    Claude Sonnet
              └─ si corrigeable : « teste au point de bascule » → retour à l'Analyste (3 tentatives max)
        ─► Agent Explicabilité . 4 à 6 affirmations Fait / Hypothèse / Scénario fictif      Claude Sonnet
        ─► Vérificateur ........ chaque chiffre est-il dans une trace ? aucun conseil ?      code pur
                                 sinon : régénération, puis texte de secours
Chaque étape écrit une trace horodatée (entrées, sortie, source) ─► Amazon DynamoDB
```

| Service AWS | Utilisation |
|---|---|
| **Amazon Bedrock** | Claude Haiku (Profil), Claude Sonnet (Analyste via Strands, Gouvernance, Explicabilité) |
| **Bedrock Guardrails** | Refuse les transactions réelles et le conseil personnalisé, en entrée et en sortie |
| **AWS Lambda** | Outils de calcul de l'Analyste, exposés par une Function URL authentifiée IAM |
| **Amazon S3** | Données propres (prix en CAD, macro, ESG), bucket privé et chiffré |
| **Amazon DynamoDB** | Journal d'audit : une trace par calcul, verdict et vérification |

**Garanties vérifiées par le code (pas par un prompt) :** aucun chiffre ne vient du LLM ; les seuils viennent de
`app/config/*.yaml` ; la tolérance au risque n'est jamais déduite ; toute formulation de conseil est rejetée
(`app/config/garde_fous.yaml`) ; chaque échec d'AWS bascule sur un repli affiché, jamais sur un plantage.

## Données
| Source | Contenu | Traitement |
|---|---|---|
| Jeu de départ du datathon (Yahoo Finance via yfinance) | 31 actifs, prix quotidiens du 2021-11-12 au 2026-11-12 | Clôture ajustée ; rendements hebdomadaires (261 semaines) |
| Banque du Canada (Valet) | USD/CAD quotidien, taux directeur, rendements 2 et 10 ans | Tout est converti en **CAD** ; séries quotidiennes seulement |
| FRED | Taux et indicateurs américains | Séries mensuelles exclues (publiées après la date : pas de « regard vers le futur ») |
| Ajouts de l'équipe | Drapeaux ESG (règle sectorielle, fonds ESGV), avec motif et source | `data/sources/sources_added.csv` |

Reproduire les données : [`data/README.md`](data/README.md) (scripts `01` à `04`). Qualité et limites :
[`docs/audit_donnees.md`](docs/audit_donnees.md). Conditions d'utilisation : `data/raw/starter/sources_metadata.csv`.

## Tests
```bash
cd app
pytest tests/                       # tests unitaires (mode local, sans AWS)
python tests/lancer_scenarios.py    # scénarios piégés : tableau prêt pour la documentation
```

## Structure du dépôt
| Dossier | Contenu |
|---|---|
| `app/src/agents/` | Profil, Analyste (Strands), Gouvernance, Explicabilité |
| `app/src/outils/` | Calculs déterministes : part du risque, point de bascule, rejeu 2022… |
| `app/src/regles/`, `app/src/verif/` | Moteur de règles, vérificateur de fidélité, Guardrails |
| `app/src/traces/` | Journal d'audit (fichiers locaux ou DynamoDB) |
| `app/config/` | Seuils des profils, personas, garde-fous : hypothèses de l'équipe |
| `app/ui/` | Interface Streamlit · `app/lambda/` : handler AWS Lambda |
| `data/` | Préparation des données · `docs/` : documentation, décisions, one-pager, livrables PDF |

## Limites assumées
Cinq ans de données (un seul cycle de taux) et biais du survivant ; seuils des profils = hypothèses documentées ;
portefeuille de départ supposé pour chaque persona ; une demande analysée à la fois.

**ESG : implémentation partielle, assumée.** Ce n'est pas une note ESG. La règle d'exclusion de Mateo repose sur
(1) une règle sectorielle de l'équipe (énergie = controverse) et (2) la présence dans un FNB ESG (ESGV, XESG). Il n'y a
**ni revue des controverses sociales ou de gouvernance, ni évaluation des FNB titre par titre** : un fonds comme XIU
est donc signalé « à vérifier », jamais déclaré conforme. Les données sont un instantané de 2026 appliqué à toute la
période. Détail : [`docs/documentation_technique.md`](docs/documentation_technique.md), section 7.

## Équipe
Equipe 19.
