import pytest

from notifications_utils.sanitise_text import SanitiseASCII, SanitiseSMS, SanitiseText

params, ids = zip(
    (("a", "a", "a"), "ascii char (a)"),
    # ascii control char (not in GSM)
    (("\t", " ", " "), "ascii control char not in gsm (tab)"),
    # these are not in GSM charset so are downgraded
    (("ç", "ç", "c"), "decomposed unicode char (C with cedilla)"),
    # these unicode chars should change to something completely different for compatibility
    (("–", "-", "-"), "compatibility transform unicode char (EN DASH (U+2013)"),
    (("—", "-", "-"), "compatibility transform unicode char (EM DASH (U+2014)"),
    (("…", "...", "..."), "compatibility transform unicode char (HORIZONTAL ELLIPSIS (U+2026)"),
    (("\u200b", "", ""), "compatibility transform unicode char (ZERO WIDTH SPACE (U+200B)"),
    (("‘", "'", "'"), "compatibility transform unicode char (LEFT SINGLE QUOTATION MARK (U+2018)"),
    (("’", "'", "'"), "compatibility transform unicode char (RIGHT SINGLE QUOTATION MARK (U+2019)"),
    (("“", '"', '"'), "compatibility transform unicode char (LEFT DOUBLE QUOTATION MARK (U+201C)	"),
    (("”", '"', '"'), "compatibility transform unicode char (RIGHT DOUBLE QUOTATION MARK (U+201D)"),
    (("\xa0", " ", " "), "nobreak transform unicode char (NO-BREAK SPACE (U+00A0))"),
    # this unicode char is not decomposable
    (("😬", "😬", "?"), "undecomposable unicode char (grimace emoji)"),
    (("↉", "↉", "?"), "vulgar fraction (↉) that we do not try decomposing"),
    # Unicode plane 2, decomposes but not to ASCII characters
    (("嶲", "嶲", "?"), "CJK Extension F"),
    strict=True,
)


@pytest.mark.parametrize("char, expected_sms, expected_ascii", params, ids=ids)
def test_encode_chars_the_same_for_ascii_and_sms(char, expected_sms, expected_ascii):
    assert SanitiseSMS.encode(char) == expected_sms
    assert SanitiseASCII.encode(char) == expected_ascii


params, ids = zip(
    # ascii control chars are allowed in GSM but not in ASCII
    (("\n", "\n", "?"), "ascii control char in gsm (newline)"),
    (("\r", "\r", "?"), "ascii control char in gsm (return)"),
    # These characters are present in GSM but not in ascii
    (("à", "à", "a"), "non-ascii gsm char (a with accent)"),
    (("€", "€", "?"), "non-ascii gsm char (euro)"),
    # These characters are Welsh characters that are not present in GSM
    (("â", "â", "a"), "non-gsm Welsh char (a with hat)"),
    (("Ŷ", "Ŷ", "Y"), "non-gsm Welsh char (capital y with hat)"),
    (("ë", "ë", "e"), "non-gsm Welsh char (e with dots)"),
    (("Ò", "Ò", "O"), "non-gsm Welsh char (capital O with grave accent)"),
    (("í", "í", "i"), "non-gsm Welsh char (i with accent)"),
    strict=True,
)


@pytest.mark.parametrize("char, expected_sms, expected_ascii", params, ids=ids)
def test_encode_chars_different_between_ascii_and_sms(char, expected_sms, expected_ascii):
    assert SanitiseSMS.encode(char) == expected_sms
    assert SanitiseASCII.encode(char) == expected_ascii


@pytest.mark.parametrize(
    "codepoint, char",
    [
        ("0041", "A"),
        ("0061", "a"),
    ],
)
def test_get_unicode_char_from_codepoint(codepoint, char):
    assert SanitiseASCII.get_unicode_char_from_codepoint(codepoint) == char


@pytest.mark.parametrize("bad_input", ["", "GJ", "00001", '0001";import sys;sys.exit(0)"'])
def test_get_unicode_char_from_codepoint_rejects_bad_input(bad_input):
    with pytest.raises(ValueError):
        SanitiseText.get_unicode_char_from_codepoint(bad_input)


@pytest.mark.parametrize(
    "content, expected_sms, expected_ascii",
    [
        ("Łōdź", "Łōdź", "Lodz"),
        ("It Just Works™", "It Just Works™", "It Just Works?"),
        (
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumps over the lazy dog",
        ),
        ("🏳️‍🌈", "🏳️‍🌈", "???"),  # Rainbow flag is 🏳 + joiner + 🌈
    ],
)
def test_encode_string(content, expected_sms, expected_ascii):
    assert SanitiseSMS.encode(content) == expected_sms
    assert SanitiseASCII.encode(content) == expected_ascii
