"""Formats d'affichage. Les MÊMES fonctions servent aux traces et aux explications,
ce qui permet au vérificateur de fidélité de comparer les chiffres tels qu'écrits."""


def sep(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", " ")


def money(x: float) -> str:
    arrondi = round(x / 100) * 100
    return ("-" if arrondi < 0 else "") + sep(abs(arrondi)) + " $"


def pct(x: float, d: int = 1) -> str:
    s = f"{x * 100:.{d}f}".replace(".", ",")
    if s.endswith(",0"):
        s = s[:-2]
    if s in ("-0", "-0,0"):
        s = "0"
    return s + " %"


def poids_texte(poids: dict) -> str:
    return " · ".join(f"{k} {pct(v)}" for k, v in poids.items() if v > 1e-4)


def nombre(x: float, d: int = 1) -> str:
    """Nombre décimal à la française (virgule), sans unité : 2,6 · 0,84."""
    return f"{x:.{d}f}".replace(".", ",")
