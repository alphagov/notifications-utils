import unicodedata


class SanitiseText:
    ALLOWED_CHARACTERS = set()

    REPLACEMENT_CHARACTERS = {
        '–': '-',  # EN DASH (U+2013)
        '—': '-',  # EM DASH (U+2014)
        '…': '...',  # HORIZONTAL ELLIPSIS (U+2026)
        '‘': '\'',  # LEFT SINGLE QUOTATION MARK (U+2018)
        '’': '\'',  # RIGHT SINGLE QUOTATION MARK (U+2019)
        '“': '"',  # LEFT DOUBLE QUOTATION MARK (U+201C)
        '”': '"',  # RIGHT DOUBLE QUOTATION MARK (U+201D)
        '\u200B': '',  # ZERO WIDTH SPACE (U+200B)
        '\t': ' ',  # TAB
    }

    @classmethod
    def encode(cls, content):
        return ''.join(cls.encode_char(char) for char in content)

    @classmethod
    def get_non_compatible_characters(cls, content):
        """
        Given an input string, return a set of non compatible characters.

        This follows the same rules as `cls.encode`, but returns just the characters that encode would replace with `?`
        """
        return set(c for c in content if c not in cls.ALLOWED_CHARACTERS and cls.downgrade_character(c) is None)

    @classmethod
    def get_unicode_char_from_codepoint(cls, codepoint):
        """
        Given a unicode codepoint (eg 002E for '.', 0061 for 'a', etc), return that actual unicode character.

        unicodedata.decomposition returns strings containing codepoints, so we need to eval them ourselves
        """
        # lets just make sure we aren't evaling anything weird
        if not set(codepoint) <= set('0123456789ABCDEF') or not len(codepoint) == 4:
            raise ValueError('{} is not a valid unicode codepoint'.format(codepoint))
        return eval('"\\u{}"'.format(codepoint))

    @classmethod
    def downgrade_character(cls, c):
        """
        Attempt to downgrade a non-compatible character to the allowed character set.

        Will return None if character is either already valid or has no known downgrade
        """
        decomposed = unicodedata.decomposition(c)
        if decomposed != '' and '<compat>' not in decomposed:
            # if there is a decomposition, which is not a compatibility decomposition (eg … -> ...),
            # then it's probably a letter with a modifier, eg á
            # ASSUMPTION: The first character of a combined unicode character (eg 'á' == '0061 0301')
            # will be the ascii char
            return cls.get_unicode_char_from_codepoint(decomposed.split()[0])
        else:
            # try and find a mapping (eg en dash -> hyphen ('–': '-')), else return None
            return cls.REPLACEMENT_CHARACTERS.get(c)

    @classmethod
    def encode_char(cls, c):
        """
        Given a single unicode character, return a compatible character from the allowed set.
        """
        # char is a good character already - return that native character.
        if c in cls.ALLOWED_CHARACTERS:
            return c
        else:
            c = cls.downgrade_character(c)
            return c if c is not None else '?'


class SanitiseGSM(SanitiseText):
    """
    Given an input string, makes it GSM compatible. This involves removing all non-gsm characters by applying the
    following rules
    * characters within the GSM character set (https://en.wikipedia.org/wiki/GSM_03.38)
      and extension character set are kept

    * characters with sensible downgrades are replaced in place
        * characters with diacritics (accents, umlauts, cedillas etc) are replaced with their base character, eg é -> e
        * en dash and em dash (– and —) are replaced with hyphen (-)
        * left/right quotation marks (‘, ’, “, ”) are replaced with ' and "
        * zero width spaces (sometimes used to stop eg "gov.uk" linkifying) are removed
        * tabs are replaced with a single space

    * any remaining unicode characters (eg chinese/cyrillic/glyphs/emoji) are replaced with ?
    """
    ALLOWED_CHARACTERS = set(
        '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?' +
        '¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿abcdefghijklmnopqrstuvwxyzäöñüà' +
        # character set extension
        '^{}\\[~]|€'
    )


class SanitiseASCII(SanitiseText):
    ALLOWED_CHARACTERS = set('all printable ascii characters')
