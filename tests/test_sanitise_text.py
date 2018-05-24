import pytest

from notifications_utils.sanitise_text import SanitiseText, SanitiseGSM, SanitiseASCII


params, ids = zip(
    (('a', 'a'), 'ascii char (a)'),
    # ascii control char (not in GSM)
    (('\t', ' '), 'ascii control char not in gsm (tab)'),
    # thes are not in GSM charset so are downgraded
    (('â', 'a'), 'decomposed unicode char (a with hat)'),
    (('ç', 'c'), 'decomposed unicode char (C with cedilla)'),
    # these unicode chars should change to something completely different for compatibility
    (('–', '-'), 'compatibility transform unicode char (EN DASH (U+2013)'),
    (('—', '-'), 'compatibility transform unicode char (EM DASH (U+2014)'),
    (('…', '...'), 'compatibility transform unicode char (HORIZONTAL ELLIPSIS (U+2026)'),
    (('\u200B', ''), 'compatibility transform unicode char (ZERO WIDTH SPACE (U+200B)'),
    (('‘', '\''), 'compatibility transform unicode char (LEFT SINGLE QUOTATION MARK (U+2018)'),
    (('’', '\''), 'compatibility transform unicode char (RIGHT SINGLE QUOTATION MARK (U+2019)'),
    (('“', '"'), 'compatibility transform unicode char (LEFT DOUBLE QUOTATION MARK (U+201C)	'),
    (('”', '"'), 'compatibility transform unicode char (RIGHT DOUBLE QUOTATION MARK (U+201D)'),
    # this unicode char is not decomposable
    (('😬', '?'), 'undecomposable unicode char (grimace emoji)'),
)


@pytest.mark.parametrize('char, expected', params, ids=ids)
@pytest.mark.parametrize('cls', [SanitiseGSM, SanitiseASCII])
def test_encode_chars_the_same_for_ascii_and_gsm(char, expected, cls):
    assert cls.encode_char(char) == expected


params, ids = zip(
    # ascii control chars are allowed in GSM but not in ASCII
    (('\n', '\n', '?'), 'ascii control char in gsm (newline)'),
    (('\r', '\r', '?'), 'ascii control char in gsm (return)'),
    # These characters are present in GSM but not in ascii
    (('à', 'à', 'a'), 'non-ascii gsm char (a with accent)'),
    (('€', '€', '?'), 'non-ascii gsm char (euro)'),
)


@pytest.mark.parametrize('char, expected_gsm, expected_ascii', params, ids=ids)
def test_encode_chars_different_between_ascii_gsm(char, expected_gsm, expected_ascii):
    assert SanitiseGSM.encode_char(char) == expected_gsm
    assert SanitiseASCII.encode_char(char) == expected_ascii


@pytest.mark.parametrize('codepoint, char', [
    ('0041', 'A'),
    ('0061', 'a'),
])
def test_get_unicode_char_from_codepoint(codepoint, char):
    assert SanitiseText.get_unicode_char_from_codepoint(codepoint) == char


@pytest.mark.parametrize('bad_input', [
    '',
    'GJ',
    '00001',
    '0001";import sys;sys.exit(0)"'
])
def test_get_unicode_char_from_codepoint_rejects_bad_input(bad_input):
    with pytest.raises(ValueError):
        SanitiseText.get_unicode_char_from_codepoint(bad_input)


@pytest.mark.parametrize('content, expected', [
    ('Łódź', '?odz'),
    ('The quick brown fox jumps over the lazy dog', 'The quick brown fox jumps over the lazy dog'),
])
def test_encode_string(content, expected):
    assert SanitiseGSM.encode(content) == expected
    assert SanitiseASCII.encode(content) == expected


@pytest.mark.parametrize('content, cls, expected', [
    ('The quick brown fox jumps over the lazy dog', SanitiseGSM, set()),
    ('The “quick” brown fox has some downgradable characters', SanitiseGSM, set()),
    ('Need more 🐮🔔', SanitiseGSM, {'🐮', '🔔'}),
    ('Lots of GSM chars that arent ascii compatible:\n\r€', SanitiseGSM, set()),
    ('Lots of GSM chars that arent ascii compatible:\n\r€', SanitiseASCII, {'\n', '\r', '€'}),
])
def test_gsm_get_non_compatible_characters(content, cls, expected):
    assert cls.get_non_compatible_characters(content) == expected
