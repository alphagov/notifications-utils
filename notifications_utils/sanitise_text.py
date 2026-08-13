import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Mapping, Set

from ordered_set import OrderedSet


class SanitiseText(ABC):
    REPLACEMENT_CHARACTERS: Mapping[str, str] = {
        "‑": "-",  # NON-BREAKING HYPHEN (U+2011)
        "–": "-",  # EN DASH (U+2013)
        "—": "-",  # EM DASH (U+2014)
        "−": "-",  # MINUS SIGN (U+2212)
        "…": "...",  # HORIZONTAL ELLIPSIS (U+2026)
        "‘": "'",  # LEFT SINGLE QUOTATION MARK (U+2018)
        "’": "'",  # RIGHT SINGLE QUOTATION MARK (U+2019)
        "“": '"',  # LEFT DOUBLE QUOTATION MARK (U+201C)
        "”": '"',  # RIGHT DOUBLE QUOTATION MARK (U+201D)
        "‚": "'",  # SINGLE LOW-9 QUOTATION MARK (U+201A)
        "„": '"',  # DOUBLE LOW-9 QUOTATION MARK (U+201E)
        "\u180e": "",  # Mongolian vowel separator
        "\u200b": "",  # zero width space
        "\u200c": "",  # zero width non-joiner
        "\u2060": "",  # word joiner
        "\ufeff": "",  # zero width non-breaking space
        "\u2028": "",  # line separator
        "\u2029": "",  # paragraph separator
        "\u00a0": " ",  # NON BREAKING WHITE SPACE (U+200B)
        "\u202f": " ",  # narrow no break space
        "\t": " ",  # TAB
    }

    @classmethod
    @abstractmethod
    def encode(cls, content: str) -> str:
        pass

    @staticmethod
    def get_unicode_char_from_codepoint(codepoint: str) -> str:
        """
        Given a unicode codepoint (eg 002E for '.', 0061 for 'a', etc), return that actual unicode character.

        unicodedata.decomposition returns strings containing codepoints, so we need to eval them ourselves
        """
        # lets just make sure we aren't evaling anything weird
        if not set(codepoint) <= set("0123456789ABCDEF") or not len(codepoint) == 4:
            raise ValueError(f"{codepoint} is not a valid unicode codepoint")
        return eval(f'"\\u{codepoint}"')


class SanitiseSMS(SanitiseText):
    """
    Given an input string, make it GSM character compatible where acceptable.

    Acceptable means a character replacement which does not change the meaning of the
    message, such as:
        * en dash and em dash (– and —) are replaced with hyphen (-)
        * left/right quotation marks (‘, ’, “, ”) are replaced with ' and "
        * zero width spaces (sometimes used to stop eg "gov.uk" linkifying) are removed
        * tabs are replaced with a single space

    Even when other characters (for example Ŵ) mean we can’t GSM-encode the message we
    still do these replacements for consistency.
    """

    EXTENDED_GSM_CHARACTERS: Set[str] = set("^{}\\[~]|€")

    GSM_CHARACTERS: Set[str] = (
        set(
            "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
            "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
        )
        | EXTENDED_GSM_CHARACTERS
    )

    CHARACTERS_NOT_REQUIRING_UNICODE: Set[str] = GSM_CHARACTERS | set(SanitiseText.REPLACEMENT_CHARACTERS)

    @classmethod
    def encode(cls, content: str) -> str:
        return "".join(cls.REPLACEMENT_CHARACTERS.get(c, c) for c in content)

    @classmethod
    def get_non_gsm_characters(cls, content: str) -> Set:
        """
        Return a set of characters which can’t be encoded to GSM-7, either through replacement or decomposition.
        """
        return OrderedSet(content) - cls.CHARACTERS_NOT_REQUIRING_UNICODE


class SanitiseASCII(SanitiseText):
    """
    Allow only printable ascii, from character range 32 to 126 inclusive.
    [chr(x) for x in range(32, 127)]
    """

    REPLACEMENT_CHARACTERS: Mapping[str, str] = dict(SanitiseText.REPLACEMENT_CHARACTERS) | {
        "Ł": "L",  # LATIN CAPITAL LETTER L WITH STROKE (U+0141)
        "ł": "l",  # LATIN SMALL LETTER L WITH STROKE (U+0142)
        "\u200d": "",  # zero width joiner
    }

    ALLOWED_CHARACTERS: Set[str] = set(
        " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
    )

    @classmethod
    def encode(cls, content: str) -> str:
        return "".join(cls.encode_char(char) for char in content)

    @classmethod
    def downgrade_character(cls, c: str) -> str | None:
        """
        Attempt to downgrade a non-compatible character to the allowed character set. May downgrade to multiple
        characters, eg `… -> ...`

        Will return None if character is either already valid or has no known downgrade
        """
        decomposed = unicodedata.decomposition(c)
        if decomposed != "" and "<" not in decomposed:
            # decomposition lists the unicode code points a character is made up of, if it's made up of multiple
            # points. For example the á character returns '0061 0301', as in, the character a, followed by a combining
            # acute accent. The decomposition might, however, also contain a decomposition mapping in angle brackets.
            # For a full list of the types, see here: https://www.compart.com/en/unicode/decomposition.
            # If it's got a mapping, we're not sure how best to downgrade it, so just see if it's in the
            # REPLACEMENT_CHARACTERS map. If not, then it's probably a letter with a modifier, eg á
            # If this is the case then the first character of a combined unicode character (eg 'á' == '0061 0301')
            # will be an ASCII char in ALLOWED_CHARACTERS
            first_character_of_decomposition = cls.get_unicode_char_from_codepoint(decomposed.split()[0])
            if first_character_of_decomposition in cls.ALLOWED_CHARACTERS:
                return first_character_of_decomposition
            return None
        else:
            # try and find a mapping (eg en dash -> hyphen ('–': '-')), else return None
            return cls.REPLACEMENT_CHARACTERS.get(c)

    @classmethod
    def encode_char(cls, c: str) -> str:
        """
        Given a single unicode character, return a compatible character from the allowed set.
        """
        # char is a good character already - return that native character.
        if c in cls.ALLOWED_CHARACTERS:
            return c
        else:
            downgraded = cls.downgrade_character(c)
            return downgraded if downgraded is not None else "?"
