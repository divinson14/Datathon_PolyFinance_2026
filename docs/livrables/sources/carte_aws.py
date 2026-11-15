"""Page PDF de l'architecture AWS (format 16:9) à partir de l'image de l'équipe.
Usage : python carte_aws.py docs/architecture_aws.png docs/livrables/InvestIA_architecture_AWS.pdf"""
import sys

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

source, sortie = sys.argv[1], sys.argv[2]
w, h = ImageReader(source).getSize()
largeur = 960                                   # points ; la hauteur suit les proportions de l'image
page = (largeur, largeur * h / w)
c = canvas.Canvas(sortie, pagesize=page)
c.setTitle("InvestIA — Architecture AWS"); c.setAuthor("Équipe InvestIA")
c.drawImage(source, 0, 0, *page)
c.showPage(); c.save()
