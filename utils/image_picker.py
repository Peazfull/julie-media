from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

ASSETS_DIR = Path(__file__).parent.parent / "assets" / "images"
VALID_MOODS = {
    "colere", "content", "ecole", "excite", "fatigue",
    "icones", "nourriture", "parents_adultes", "pensif",
    "peur", "triste", "zen"
}

# Correspondance humeur → dossier réel (insensible à la casse + tirets/underscores)
def _build_folder_map() -> dict:
    mapping = {}
    if not ASSETS_DIR.exists():
        return mapping
    for d in ASSETS_DIR.iterdir():
        if d.is_dir():
            # Clé normalisée : minuscule + tirets → underscores
            key = d.name.lower().replace("-", "_")
            mapping[key] = d
    return mapping

_FOLDER_MAP: dict = {}


def _get_folder_map() -> dict:
    global _FOLDER_MAP
    if not _FOLDER_MAP:
        _FOLDER_MAP = _build_folder_map()
    return _FOLDER_MAP


def _list_mood_images(humeur: str) -> list:
    folder_map = _get_folder_map()
    mood_dir = folder_map.get(humeur)
    if not mood_dir or not mood_dir.exists():
        # Fallback sur content
        mood_dir = folder_map.get("content")
    if not mood_dir or not mood_dir.exists():
        return []
    return sorted(mood_dir.glob("*.png"))


def pick_image(humeur: str) -> Optional[Path]:
    """Retourne un Path aléatoire dans le dossier d'humeur, ou None si vide."""
    humeur = humeur.lower().strip()
    if humeur not in VALID_MOODS:
        humeur = "content"
    images = _list_mood_images(humeur)
    if not images:
        return None
    return random.choice(images)


def reshuffle(humeur: str, exclude_path: Optional[Path] = None) -> Optional[Path]:
    """Retourne un path différent de exclude_path si possible."""
    humeur = humeur.lower().strip()
    if humeur not in VALID_MOODS:
        humeur = "content"
    images = _list_mood_images(humeur)
    if not images:
        return None
    if len(images) == 1:
        return images[0]
    candidates = [p for p in images if p != exclude_path]
    return random.choice(candidates) if candidates else random.choice(images)


def pick_images_for_carousel(humeur: str, n_content_slides: int = 3) -> dict:
    """
    Retourne un dict {slide_key: path} pour toutes les slides du carrousel.
    Clés : "hook", "slide_0", "slide_1", ..., "slide_{n-1}", "outro"
    """
    humeur = humeur.lower().strip()
    if humeur not in VALID_MOODS:
        humeur = "content"

    images = _list_mood_images(humeur)
    used = []
    result = {}

    def _pick_unused():
        if not images:
            return None
        candidates = [p for p in images if p not in used]
        if not candidates:
            candidates = images
        chosen = random.choice(candidates)
        used.append(chosen)
        return chosen

    result["hook"] = _pick_unused()
    for i in range(n_content_slides):
        result[f"slide_{i}"] = _pick_unused()
    result["outro"] = _pick_unused()

    return result
