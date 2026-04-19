"""
Shared vocabularies for the query classifier and the summarizer.

Splits into three sets:

- `CANONICAL_QUERIES`: small, stable set of one/two-word theological queries
  eligible for the summarizer's 7-day cache. Changing this set invalidates
  cache keys, so keep additions conservative.

- `CONCEPT_VOCAB`: single-token theological / abstract concepts the classifier
  uses to compute concept-density. Kept deliberately narrow — only tokens
  that are almost always theological-concept when they appear in a query.
  Ambiguous words (e.g. "light", "born", "law", "flesh") are excluded to
  avoid producing spurious concept signals on phrases like "born again" or
  "light of the world" that should classify as EXACT_PHRASE.

- `BIBLICAL_NAMES`: proper nouns (people, places, titles, supernatural
  entities) used to compute named-entity density. Weighted toward New
  Testament figures because the corpus is NT-only (Matthew–Revelation,
  7,953 verses).
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
