import json
import os
import re as _re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "secrets", ".env"))

_client = None

VALID_MOODS = {
    "colere", "content", "ecole", "excite", "fatigue",
    "icones", "nourriture", "parents_adultes", "pensif",
    "peur", "triste", "zen"
}

SYSTEM_PROMPT = (
    "Tu es une experte en parentalité et en neurodéveloppement, spécialisée dans le TDAH chez l'enfant. "
    "Tu accompagnes des parents débordés, souvent culpabilisés, qui cherchent des réponses concrètes et bienveillantes. "
    "Tu rédiges des carrousels Instagram percutants : hook qui accroche, contenu qui éduque sans jargon, "
    "outro qui invite à l'action et crée de la communauté. "
    "Ton style : phrases courtes, ton chaleureux et direct. "
    "INTERDIT : aucun emoji, aucun symbole spécial, uniquement du texte brut. "
    "tu décules les parents, tu valorises les forces du cerveau TDAH, tu donnes des outils concrets.\n\n"
    "RÈGLE ABSOLUE DE FORMAT : dans CHAQUE champ texte (hook, title, content, outro), "
    "tu DOIS placer exactement un marquage *mot(s)* autour de 1 à 3 mots clés. "
    "Ce marquage est OBLIGATOIRE — sans exception. "
    "Exemple correct pour hook : \"*3 erreurs* que font tous les parents d'enfant TDAH\" "
    "Exemple correct pour title : \"*Routine du matin* : le secret\" "
    "Exemple correct pour content : \"Le cerveau TDAH a besoin de *repères visuels* pour s'organiser.\" "
    "Exemple correct pour outro : \"Sauvegarde ce post. Et toi, quelle *astuce* a changé ton quotidien ?\""
)

CAROUSEL_SCHEMA = """Structure JSON à remplir :
{
  "hook": "<titre accrocheur reprenant le sujet — DOIT contenir le mot TDAH — finit obligatoirement par : ou par ? si c'est une question>",
  "slides": [
    {
      "title": "<titre court de la slide>",
      "content": "<2-3 phrases percutantes>"
    }
  ],
  "outro": "<CTA bienveillant + question engageante>",
  "humeur": "<un mot parmi : colere, content, ecole, excite, fatigue, icones, nourriture, parents_adultes, pensif, peur, triste, zen>"
}

Règles de contenu :
- AUCUN emoji dans aucun champ.
- Le hook finit TOUJOURS par ":" ou par "?" (si c'est une question). Jamais par un point, jamais sans ponctuation finale.
- Les titles ne finissent JAMAIS par un point.
- Dans CHAQUE champ texte (hook, title, content, outro), entoure 1 à 3 mots clés avec *astérisques* : ex. "*3 erreurs* que font les parents" ou "Le cerveau a besoin de *repères visuels*".
- Le marquage *...* est OBLIGATOIRE dans chaque champ. Ne jamais l'omettre."""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-REMPLACER":
            raise ValueError("OPENAI_API_KEY manquante ou non configurée dans secrets/.env")
        _client = OpenAI(api_key=api_key)
    return _client


def generate_carousel(sujet: str) -> dict:
    """
    Retourne un dict :
    {
        hook: str,
        slides: [{"title": str, "content": str}, ...],
        outro: str,
        humeur: str
    }
    Le nombre de slides est déterminé par le sujet (ex: "5 façons de..." → 5 slides).
    """
    user_prompt = (
        f'Crée un carrousel Instagram sur le sujet : "{sujet}". '
        f'IMPORTANT : le champ "hook" doit reprendre le sujet "{sujet}" quasi tel quel — '
        "c'est le titre de la slide 1, il ne doit pas être réinventé. "
        "Le hook DOIT contenir le mot TDAH (ou TDAH entre astérisques si c'est le mot clé). "
        "Adapte le nombre de slides au sujet : si le sujet mentionne un chiffre (ex: '5 façons'), "
        "génère exactement ce nombre de slides. Sinon, génère le nombre optimal (2 à 5). "
        "Le nombre de slides ne doit JAMAIS dépasser 5. "
        f"Réponds UNIQUEMENT avec ce JSON exact :\n{CAROUSEL_SCHEMA}"
    )

    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    # Validation
    for key in ("hook", "slides", "outro", "humeur"):
        if key not in data:
            raise ValueError(f"Clé manquante '{key}' dans la réponse API.\nRéponse : {raw}")

    slides = data["slides"]
    if not isinstance(slides, list) or len(slides) == 0:
        raise ValueError(f"'slides' doit être une liste non vide.\nRéponse : {raw}")

    # Normalise chaque slide
    clean_slides = []
    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            raise ValueError(f"Slide {i+1} invalide : {s}")
        clean_slides.append({
            "title": s.get("title", ""),
            "content": s.get("content", ""),
        })
    data["slides"] = clean_slides

    # Limite max 5 slides → hook + 5 content + outro = 7 slides au total
    data["slides"] = data["slides"][:5]

    humeur = data["humeur"].strip().lower()
    if humeur not in VALID_MOODS:
        humeur = "content"
    data["humeur"] = humeur

    # Garde-fou : si le hook est trop court ou tronqué par rapport au sujet, on utilise le sujet
    hook_clean = _re.sub(r'[*=]', '', data.get("hook", "")).strip()
    sujet_clean = _re.sub(r'[*=]', '', sujet).strip()
    if len(hook_clean) < 5 or len(hook_clean) < len(sujet_clean) * 0.75:
        data["hook"] = sujet

    # Garde-fou markup : si un champ ne contient aucun *...*, on entoure le premier mot significatif
    _MARKUP = _re.compile(r'\*.+?\*')
    _WORD   = _re.compile(r'\b([A-Za-zÀ-ÿ]{4,})\b')

    def _ensure_markup(text: str) -> str:
        if _MARKUP.search(text):
            return text
        m = _WORD.search(text)
        if m:
            w = m.group(1)
            return text.replace(w, f"*{w}*", 1)
        return text

    # Supprime les artefacts du schema que GPT pourrait copier littéralement
    _ARTIFACT_RE = _re.compile(
        r'\s*(OBLIGATOIRE\s*:.*|NE\s+FINIT\s+JAMAIS.*|SANS\s+emoji.*|UN\s+SEUL\s+MOT.*)$',
        _re.IGNORECASE
    )

    def _clean_artifacts(text: str) -> str:
        return _ARTIFACT_RE.sub("", text).strip()

    def _strip_trailing_dot(text: str) -> str:
        return text.rstrip(".").rstrip()

    def _enforce_hook_ending(text: str) -> str:
        """Le hook doit finir par : ou ?  — on corrige si besoin."""
        t = text.strip()
        if t.endswith("?") or t.endswith(":"):
            return t
        # Retire tout point/ponctuation finale avant de trancher
        t = t.rstrip(".!,;")
        # Si le texte contient un marqueur de question, on ajoute ?
        question_words = ("pourquoi", "comment", "est-ce", "sais-tu", "savais-tu", "connaissez")
        if any(t.lower().startswith(w) for w in question_words) or t.endswith("?"):
            return t + " ?"
        return t + " :"

    hook_processed = _ensure_markup(_enforce_hook_ending(_clean_artifacts(data["hook"])))
    # Guardrail : le hook doit toujours contenir "TDAH"
    if "tdah" not in hook_processed.lower():
        # Insère "TDAH" avant le premier ":" ou "?" final, sinon en fin de texte
        for sep in (":", "?"):
            if hook_processed.endswith(sep):
                hook_processed = hook_processed[:-1].rstrip() + f" *TDAH* {sep}"
                break
        else:
            hook_processed = hook_processed.rstrip() + " *TDAH*"
    data["hook"] = hook_processed
    for s in data["slides"]:
        s["title"]   = _ensure_markup(_strip_trailing_dot(_clean_artifacts(s["title"])))
        s["content"] = _ensure_markup(_clean_artifacts(s["content"]))
    data["outro"] = _ensure_markup(_clean_artifacts(data["outro"]))

    return data


if __name__ == "__main__":
    import sys
    sujet = sys.argv[1] if len(sys.argv) > 1 else "5 façons de calmer une crise TDAH"
    result = generate_carousel(sujet)
    print(f"Hook   : {result['hook']}")
    print(f"Slides : {len(result['slides'])}")
    for i, s in enumerate(result["slides"], 1):
        print(f"  {i}. {s['title']} → {s['content'][:60]}…")
    print(f"Outro  : {result['outro']}")
    print(f"Humeur : {result['humeur']}")
