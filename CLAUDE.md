# Consignes pour les assistants de code (Claude Code, Copilot…)

- Projet de SIMULATION : jamais de transaction réelle ni de conseil personnalisé.
- Les LLM ne produisent jamais de chiffres : tout calcul va dans app/src/outils/ et écrit une trace.
- Les seuils viennent de app/config/*.yaml ; ne jamais les coder en dur.
- Un seul point d'appel à Bedrock : app/src/bedrock_client.py.
- Le moteur de règles et le vérificateur de fidélité restent du code pur, sans LLM.
- Ne jamais committer de clés AWS ni le fichier .env.
- Code et commentaires en français ; noms de variables en français.
- Lancer `pytest tests/` (depuis app/) avant de proposer un commit.
