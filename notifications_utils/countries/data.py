import json
import os


def _load_data(filename):
    with open(
        os.path.join(os.path.dirname(__file__), '_data', filename)
    ) as contents:
        if filename.endswith('.json'):
            return json.load(contents)
        return [line.strip() for line in contents.readlines()]


def find_canonical(item, graph, key):
    if item['meta']['canonical']:
        return key, item['names']['en-GB']
    return find_canonical(
        graph[item['edges']['from'][0]],
        graph,
        key,
    )


# Copied from
# https://github.com/alphagov/govuk-country-and-territory-autocomplete
# /blob/b61091a502983fd2a77b3cdb5f94a604412eb093
# /dist/location-autocomplete-graph.json
_graph = _load_data('location-autocomplete-graph.json')

UK = 'United Kingdom'

COUNTRIES_AND_TERRITORIES = [
    find_canonical(item, _graph, item['names']['en-GB'])
    for item in _graph.values()
]

ADDITIONAL_SYNONYMS = [
    (key, value)
    for key, value in _load_data('synonyms.json').items()
]

_UK_ISLANDS_LIST = _load_data('uk-islands.txt')
_EUROPEAN_ISLANDS_LIST = _load_data('european-islands.txt')

UK_ISLANDS = [
    (synonym, synonym) for synonym in _UK_ISLANDS_LIST
]

EUROPEAN_ISLANDS = [
    (synonym, synonym) for synonym in _EUROPEAN_ISLANDS_LIST
]

# Copied from https://www.royalmail.com/international-zones#europe
# Modified to use the canonical names for countries where incorrect
ROYAL_MAIL_EUROPEAN = _load_data('europe.txt')

UK_POSTAGE_REGIONS = [UK] + _UK_ISLANDS_LIST


class Postage:
    UK = UK
    EUROPE = 'Europe'
    REST_OF_WORLD = 'rest of world'
