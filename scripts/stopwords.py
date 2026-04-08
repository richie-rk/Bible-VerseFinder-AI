"""
Biblical stopword list for BM25 tokenization.

Curated for Bible search: removes noise words while preserving
theologically significant terms like negations and contrasts.

IMPORTANT: This list must match exactly between index-time (scripts/create_bm25_index.py)
and query-time (backend/app/services/search.py). Keep both copies in sync.
"""

BIBLICAL_STOPWORDS = [
    # Articles & Determiners
    "a", "an", "the",

    # Prepositions
    "of", "to", "in", "on", "at", "by", "for", "from", "with", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "about", "up", "down", "over", "under", "near", "off", "out",

    # Conjunctions (non-contrastive)
    "and", "or", "as", "if", "than", "then", "while", "until", "unless",

    # Auxiliary & Copula verbs
    "is", "are", "was", "were", "am", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "shall", "can", "may", "might", "must",

    # Interrogatives
    "what", "which", "who", "whom", "whose", "when", "where", "how", "why",

    # Pronouns — first person
    "i", "me", "my", "mine", "myself",
    # Pronouns — second person
    "you", "your", "yours", "yourself", "yourselves",
    # Pronouns — third person masculine
    "he", "him", "his", "himself",
    # Pronouns — third person feminine
    "she", "her", "hers", "herself",
    # Pronouns — third person neuter
    "it", "its", "itself",
    # Pronouns — first person plural
    "we", "us", "our", "ours", "ourselves",
    # Pronouns — third person plural
    "they", "them", "their", "theirs", "themselves",

    # Demonstratives
    "this", "that", "these", "those",

    # Adverbs (noise)
    "very", "just", "also", "only", "so", "too", "quite", "rather",
    "again", "once", "here", "there", "now", "then", "soon",
    "further", "furthermore", "moreover",

    # Narrative / transitional
    "said", "came", "went", "upon",

    # --- EXPLICITLY KEPT (never add to this list) ---
    # Negations: not, no, nor, never, neither
    # Contrast: but, yet, however
    #
    # --- Commented-out quantifiers for future tuning ---
    # "all", "any", "some", "few", "each", "every",
    # "many", "much", "more", "most", "other", "another",
]
