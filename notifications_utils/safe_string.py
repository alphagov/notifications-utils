import re
import unicodedata


def email_safe(string, whitespace='.'):
    # strips accents, diacritics etc
    string = ''.join(
        c for c in unicodedata.normalize('NFD', string)
        if unicodedata.category(c) != 'Mn'
    )
    string = ''.join(
        word.lower() if word.isalnum() or word == whitespace else ''
        for word in re.sub(r'\s+', whitespace, string.strip())
    )
    string = re.sub(r'\.{2,}', '.', string)
    return string.strip('.')


def id_safe(string):
    return email_safe(string, whitespace='-')
