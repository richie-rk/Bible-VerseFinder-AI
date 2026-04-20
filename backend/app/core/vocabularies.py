"""
Shared vocabularies for the query classifier and the summarizer.

CANONICAL_QUERIES: short, stable queries eligible for the summarizer cache.
Changing this set invalidates cache keys — add conservatively.

CONCEPT_VOCAB: tokens used to compute concept-density in the classifier.
Deliberately narrow — ambiguous words like "light", "born", "law", "flesh"
are excluded so phrases like "born again" or "light of the world" stay
purely EXACT_PHRASE rather than picking up stray concept strength.

BIBLICAL_NAMES: proper nouns for named-entity density. NT-heavy to match the
corpus.
"""


CANONICAL_QUERIES: frozenset[str] = frozenset({
    "grace", "faith", "love", "hope", "salvation", "forgiveness",
    "mercy", "peace", "joy", "sin", "repentance", "redemption",
    "baptism", "prayer", "holy spirit", "resurrection", "eternal life",
    "kingdom of god", "kingdom of heaven", "born again", "good shepherd",
})


CONCEPT_VOCAB: frozenset[str] = frozenset({
    # Core doctrine
    "grace", "faith", "love", "hope", "mercy", "peace", "joy",
    "salvation", "forgiveness", "repentance", "redemption",
    "righteousness", "justification", "sanctification", "glorification",
    "holiness", "atonement", "propitiation", "reconciliation",
    "covenant", "gospel",
    # Practices
    "baptism", "prayer", "worship", "discipleship",
    "repent", "repented", "confess", "confession", "pray", "prayed",
    "believe", "believed", "believing",
    # Virtues / fruit of the Spirit
    "patience", "kindness", "goodness", "faithfulness", "gentleness",
    "humility", "compassion", "endurance", "perseverance",
    # Vices
    "sin", "sins", "pride", "wrath", "covetousness", "greed", "lust",
    "hypocrisy", "hypocrite", "disobedience", "idolatry",
    # Theological abstractions
    "wisdom", "truth", "glory", "obedience", "judgment", "judgement",
    "blessing", "curse", "suffering", "temptation", "tribulation",
    "persecution", "commandment", "commandments",
    "miracle", "miracles", "resurrection", "rebirth", "regeneration",
    # Anthropology
    "soul", "conscience",
    # Related person-terms
    "sinner", "sinners", "believer", "believers", "belief", "faithful",
})


BIBLICAL_NAMES: frozenset[str] = frozenset({
    # Divine names / titles
    "jesus", "christ", "god", "lord", "father",
    "messiah", "savior", "saviour", "rabbi", "emmanuel", "immanuel",
    "yahweh", "jehovah", "almighty",

    # OT figures (kept for cross-reference queries)
    "moses", "abraham", "david", "adam", "eve", "noah", "jacob", "isaac",
    "elijah", "elisha", "isaiah", "jeremiah", "daniel", "solomon",
    "joshua", "samuel", "saul", "job", "jonah", "ezekiel", "aaron",
    "melchizedek", "sarah", "rachel", "leah", "hannah",

    # NT — the Twelve + other disciples
    "peter", "simon", "andrew", "james", "john", "philip", "bartholomew",
    "matthew", "thomas", "thaddaeus", "judas", "matthias",

    # NT — other core figures
    "paul", "mary", "joseph", "mark", "luke",
    "nicodemus", "zacchaeus", "stephen", "barnabas", "silas",
    "timothy", "titus", "philemon", "onesimus", "lazarus", "martha",
    "cornelius", "priscilla", "aquila", "apollos", "lydia",
    "demas", "jude", "gabriel", "michael",

    # NT — antagonists / authorities
    "herod", "pilate", "caiaphas", "annas", "barabbas",
    "felix", "festus", "agrippa",

    # Groups / titles
    "pharisee", "pharisees", "sadducee", "sadducees", "scribe", "scribes",
    "apostle", "apostles", "disciple", "disciples", "gentile", "gentiles",
    "jew", "jews", "samaritan", "samaritans", "elder", "elders",
    "centurion", "levite",

    # Places — Israel / Judea
    "israel", "jerusalem", "galilee", "judea", "nazareth", "bethlehem",
    "bethany", "capernaum", "cana", "samaria", "jericho", "gethsemane",
    "calvary", "golgotha",

    # Places — wider NT world
    "ephesus", "corinth", "rome", "philippi", "colossae", "thessalonica",
    "antioch", "tarsus", "damascus", "caesarea", "patmos", "macedonia",
    "asia", "athens", "cyprus", "crete", "malta", "syria", "egypt",
    "babylon",

    # Supernatural
    "heaven", "hell", "satan", "devil", "angel", "angels",
    "demon", "demons", "seraphim", "cherubim", "beast",
})
