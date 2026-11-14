# data/ — préparation des données

Ce dossier transforme le jeu de départ du datathon en fichiers **propres** que l'application lit.
Il se lance **une fois** (ou à chaque ajout de données), avant l'application.

```
raw/starter/   ← copiez ici les fichiers fournis (ne jamais les modifier)
raw/added/     ← vos ajouts (ESG). Chaque fichier est décrit dans sources/sources_added.csv
scripts/       ← à lancer dans l'ordre 01 → 04
processed/     ← sorties propres (lues par app/)
reports/       ← rapport de qualité pour la documentation
```

## Lancer

```bash
cd data
pip install -r requirements.txt
cd scripts
python 01_nettoyer_prix.py
python 02_construire_esg.py      # quand les fichiers ESG sont remplis
python 03_rapport_qualite.py
python 04_envoyer_s3.py          # quand le bucket S3 existe (variable S3_BUCKET)
```

Si un script dit « Colonne introuvable », ouvrez `raw/starter/README.md` du datathon pour voir les vrais
noms de colonnes et ajoutez-les dans la liste des candidats du script.

## Règles
- On ne modifie **jamais** `raw/`. Tout traitement passe par un script.
- Chaque source ajoutée a sa ligne dans `sources/sources_added.csv` (origine, date, licence, traitement, limites).
