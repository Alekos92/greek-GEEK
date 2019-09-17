import json


def find_incoming_links_for_reference_dict(reference_dict):
    inlinks_dict = {}
    set_of_canonical_titles = set()

    with open('./inlinks.json', 'r') as fp:
        i_d = json.load(fp)

    for key, value in reference_dict.items():
        for entity in value:
            set_of_canonical_titles.add(entity['canonical_title'])

    for canonical_title in set_of_canonical_titles:
        inlinks_dict[canonical_title] = i_d[canonical_title] if canonical_title in i_d else []


    return inlinks_dict
