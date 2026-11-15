# Régénérer les PDF des livrables
Outils hors de l'application (dépendances : `pip install reportlab pypdf svglib`), polices Arial de macOS.

```bash
python docs/livrables/sources/md2pdf.py docs/documentation_technique.md docs/livrables/InvestIA_documentation_technique.pdf --taille 10 --marge 18
python docs/livrables/sources/flyer.py docs/livrables/sources/courbe.json docs/livrables/InvestIA_one_pager.pdf
python docs/livrables/sources/carte_aws.py docs/livrables/InvestIA_architecture_AWS.pdf "Streamlit Community Cloud"
```

- `courbe.json` : courbe de bascule réelle (Robert, TSLA), exportée de `calculs.point_de_bascule`.
- Le one-pager reprend le contenu de `docs/one_pager.md` en format visuel.
- Le 2ᵉ argument de `carte_aws.py` est l'hébergement de l'application affiché sur la carte.
