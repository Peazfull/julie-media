import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "secrets", ".env"))

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-REMPLACER":
            raise ValueError("OPENAI_API_KEY manquante ou non configurée dans secrets/.env")
        _client = OpenAI(api_key=api_key)
    return _client


SYSTEM_PROMPT = (
    "Tu es une experte en parentalité et en neurodéveloppement, spécialisée dans le TDAH chez l'enfant, "
    "ET experte en copywriting Instagram viral. "
    "Tu maîtrises les deux faces du contenu qui performe : "
    "la crédibilité experte (neuropsychologie, éducation positive, vécu des familles TDAH) "
    "ET l'accroche émotionnelle (curiosity gap, pattern interrupt, promesse concrète, mot tabou). "
    "Tes titres font stopper le scroll parce qu'ils parlent VRAI au parent épuisé, culpabilisé, incompris. "
    "Tu n'écris jamais de titres génériques ou mièvres. Chaque sujet doit provoquer une réaction : "
    "'c'est exactement ça', 'je savais pas ça', 'il faut que je lise ça maintenant'."
)


def generate_topics(prev_topics=None) -> list:
    """Retourne une liste de 5 sujets de carrousel uniques."""
    prev_topics = prev_topics or []
    prev_str = ", ".join(f'"{t}"' for t in prev_topics) if prev_topics else "aucun"

    user_prompt = (
        "Génère 6 sujets de carrousel Instagram pour des parents d'enfants TDAH. "
        f"Sujets déjà utilisés à éviter : {prev_str}. "
        "\n\nRègle d'or : chaque sujet doit être copywrité comme un titre de presse qui fait STOPPER LE SCROLL. "
        "Techniques à utiliser : curiosity gap (ce que personne ne te dit), pattern interrupt (contre-intuition), "
        "promesse ultra-concrète, mot émotionnel fort, identification immédiate du parent. "
        "JAMAIS de titre générique, JAMAIS de titre déjà vu. "
        "\n\nMix obligatoire sur les 5 : "
        "• 3 narratifs/révélateurs SANS chiffre — provoquent la curiosité ou brisent une croyance "
        '(ex: "Ce que le cerveau TDAH de ton enfant essaie vraiment de te dire", '
        '"Pourquoi punir un enfant TDAH empire tout (et ce qui marche vraiment)", '
        '"TDAH : le petit rituel du soir que personne ne t\'explique") ; '
        "• 2 avec chiffre ENTRE 3 ET 5 — promesse actionnable et précise "
        '(ex: "3 phrases à dire à ton enfant TDAH quand il explose", '
        '"5 signaux que ton enfant est en surcharge (et pas juste difficile)") ; '
        "• 1 question ou mythe brisé — interpelle directement le parent "
        '(ex: "Ton enfant TDAH est-il vraiment paresseux ? La réponse va te surprendre", '
        '"Non, ton enfant ne fait pas exprès. Voilà la preuve."). '
        "\n\nChaque sujet doit être bienveillant ET expert ET clickbait. "
        'Réponds UNIQUEMENT avec un JSON : {"topics": ["sujet1", ..., "sujet6"]}'
    )

    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.9,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    topics = data.get("topics", [])

    if not isinstance(topics, list) or len(topics) == 0:
        raise ValueError(f"Réponse API inattendue : {raw}")

    return topics[:6]


if __name__ == "__main__":
    topics = generate_topics()
    for i, t in enumerate(topics, 1):
        print(f"{i}. {t}")
