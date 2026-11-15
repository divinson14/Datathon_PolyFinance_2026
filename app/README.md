# app/ — l'application AlphaForge

```
config/      seuils, styles, personas → décidés par l'ÉQUIPE, jamais par le LLM
prompts/     instructions des 4 agents (Bedrock)
src/
  orchestrateur.py     enchaîne les agents, boucle de correction (max. 3 tentatives)
  bedrock_client.py    seul endroit qui appelle Bedrock
  agents/              profil · analyste · gouvernance · explicabilite
  outils/calculs.py    calculs déterministes (→ Lambda) : statistiques, rejeu 2022, volatilité
  regles/moteur.py     vérifie le mandat, sans LLM
  verif/fidelite.py    chaque chiffre de la réponse existe-t-il dans les traces ?
  traces/journal.py    journal d'audit (fichiers locaux ou DynamoDB)
  donnees/chargeur.py  lit data/processed (local ou S3) ; données fictives si absentes
ui/streamlit_app.py    écran « choisis ton profil » puis chat | agents en direct
lambda/handler.py      emballe les outils pour AWS Lambda
tests/                 tests unitaires + scénarios piégés
```

## Démarrer (aucun compte AWS nécessaire)

```bash
cd app
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows : copy .env.example .env
streamlit run ui/streamlit_app.py
```

Par défaut `MODE=local` : les agents sont simulés et, tant que `data/processed/` est vide,
les données sont **fictives** (affiché sous chaque réponse).

## Brancher AWS (dans cet ordre)
1. `aws configure` (jamais de clé dans le code ni dans `.env`).
2. Console Bedrock → activer l'accès aux modèles → copier les identifiants dans `.env`, puis `MODE=bedrock`.
3. `DONNEES=s3` + `S3_BUCKET` une fois que `data/scripts/04_envoyer_s3.py` a tourné.
4. Table DynamoDB `alphaforge-traces` (clé de partition `session`, clé de tri `id`) puis `TRACES=dynamodb`.
5. Guardrail Bedrock (sujet refusé : exécuter des transactions / conseil personnalisé) → `BEDROCK_GUARDRAIL_ID`.
6. Pour les calculs de l'Agent Analyste, renseigner `LAMBDA_OUTILS_URL` dans `.env` (exemple fourni dans `.env.example`).
   L'appel HTTP est signé avec AWS IAM ; la Function URL doit utiliser `AWS_IAM` et le rôle de l'application
   doit avoir `lambda:InvokeFunctionUrl` et `lambda:InvokeFunction`.
   La Lambda doit avoir accès aux mêmes données et à la configuration de calcul nécessaires. Les calculs de
   complétion et le plan de repli restent exécutés localement.

## Tests
```bash
pytest tests/
python tests/lancer_scenarios.py     # tableau à coller dans la documentation
```
