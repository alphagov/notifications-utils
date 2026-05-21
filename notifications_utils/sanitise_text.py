import unicodedata

class SanitiseText:
    @classmethod
    def encode(cls, content):
        if not content:
            return ""
        return "".join(cls.encode_char(char) for char in content)

    # Global characters we explicitly want to intercept and normalize/remove
    REPLACEMENT_CHARACTERS = {
        "‑": "-", "–": "-", "—": "-", "−": "-", "…": "...",
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "\u180e": "", "\u200b": "", "\u200c": "", "\u200d": "", "\u2060": "", "\ufeff": "",
        "\u2028": "", "\u2029": "", "\u00a0": " ", "\u202f": " ", "\t": " ",
        "Ł": "L", "ł": "l"
    }

    @classmethod
    def is_allowed(cls, c):
        """
        Determines if a character is fundamentally valid.
        We filter out dangerous structural control characters, but allow all international alphabets.
        """
        # Explicitly allow standard whitespaces, carriage returns, and line feeds
        if c in ("\n", "\r", " "):
            return True
            
        category = unicodedata.category(c)
        
        # Block control characters (Cc), formatting characters (Cf), and private use (Co)
        # This protects your database and output channels from hidden parsing structural traps.
        if category in ("Cc", "Cf", "Co"):
            return False
            
        return True

    @classmethod
    def downgrade_character(cls, c):
        """
        Extracts base forms from complex characters using NFKD normalization,
        or falls back to explicit translation maps.
        """
        if c in cls.REPLACEMENT_CHARACTERS:
            return cls.REPLACEMENT_CHARACTERS[c]
            
        # Strip diacritics/accents from Latin scripts (e.g., Ć -> C, Ž -> Z)
        normalized = unicodedata.normalize('NFKD', c)
        base_chars = "".join([char for char in normalized if not unicodedata.combining(char)])
        
        if base_chars and all(cls.is_allowed(bc) for bc in base_chars):
            return base_chars
            
        return None

    @classmethod
    def encode_char(cls, c):
        # 1. If it maps to a direct replacement, use it
        if c in cls.REPLACEMENT_CHARACTERS:
            return cls.REPLACEMENT_CHARACTERS[c]
            
        # 2. Check if the character is inherently safe/allowed across all global scripts
        if cls.is_allowed(c):
            return c
            
        # 3. Attempt a structural downgrade if it's structurally disallowed
        downgraded = cls.downgrade_character(c)
        if downgraded is not None:
            return downgraded
            
        # 4. Fallback for illegal characters
        return "?"

    @classmethod
    def get_non_compatible_characters(cls, content):
        return {c for c in content if cls.encode_char(c) == "?" and c != "?"}


class SanitiseSMS(SanitiseText):
    """
    Accepts all international languages natively.
    Maintains clean replacement overrides for punctuation/whitespaces.
    """
    pass


class SanitiseASCII(SanitiseText):
    """
    Preserved for instances where down-sampling strictly to standard US-ASCII is required.
    """
    ALLOWED_CHARACTERS = set(chr(x) for x in range(32, 127))

    @classmethod
    def is_allowed(cls, c):
        return c in cls.ALLOWED_CHARACTERS