from zeep import Client
import requests
from xml.etree import ElementTree as et
from conllu import parse
import re


def gr_ner(text):
    client = Client('http://nlp.ilsp.gr/soaplab2-axis/typed/services/getstarted.ilsp_nlp?wsdl')
    output_url = client.service.runAndWaitFor(language='el',
                                              InputType='txt',
                                              input_direct_data=text)['output_url']

    client = Client('http://nlp.ilsp.gr/soaplab2-axis/typed/services/ilsp.ilsp_nerc?wsdl')
    output_url = client.service.runAndWaitFor(language='el',
                                              InputType='xceslemma',
                                              input_url=output_url)['output_url']

    r = requests.get(output_url)
    e_text = r.text
    root = et.fromstring(e_text)

    client = Client('http://nlp.ilsp.gr/soaplab2-axis/typed/services/getstarted.ilsp_nlp?wsdl')
    output_url = client.service.runAndWaitFor(language='el',
                                              OutputType='conllu',
                                              InputType='txt',
                                              input_direct_data=text)['output_url']

    tokens = []
    accumulator = 0

    ttext = text
    r = requests.get(output_url)

    for s in parse(r.text):
        for t in s:
            k = t['form']
            nind = ttext.find(k)
            lenk = len(k)
            ind = nind + accumulator
            ttext = ttext[nind + lenk:]
            accumulator += lenk + nind

            tokens.append({
                'lemma': t['lemma'],
                'POS': t['upostag'],
                'start_offset': ind,
                'end_offset': ind + len(k),
                'matched_string': text[ind:ind + len(k)]
            })

    entities = []

    for a_s in root.findall('AnnotationSet'):
        for x in a_s.iter():
            attrs = x.attrib
            if 'Type' in attrs and attrs['Type'] in {'LOC', 'PER', 'ORG'}:
                entities.append({
                    'start_node': int(attrs['StartNode']),
                    'end_node': int(attrs['EndNode']),
                    'type': attrs['Type']

                })

    twn = re.findall(r'<TextWithNodes>(?s).*</TextWithNodes>', e_text)

    s = twn[0] if twn else ''

    r = re.compile(r'<Node id="(\d*)"/>')
    p = re.compile(r'<Node id="\d*"/>')

    rs = r.findall(s)
    ps = p.findall(s)

    d = {}

    for i in range(len(ps) - 1):
        start_p = ps[i]
        end_p = ps[i + 1]

        start_index = s.find(start_p) + len(start_p)
        end_index = s.find(end_p)

        d[(int(rs[i]), int(rs[i + 1]))] = s[start_index:end_index]

    entities = sorted(entities, key=lambda k: k['start_node'])

    f_entities = []
    accumulator = 0
    ttext = text

    for e in entities:
        entity_type = e['type']
        rng = (e['start_node'], e['end_node'])

        if rng in d:
            match = d[rng]
        else:
            match = ''
            temp = []
            for (x, y), v in d.items():
                if ((x >= rng[0]) and (y <= rng[1])):
                    temp.append((x, v))
            temp = sorted(temp, key=lambda t: t[0])
            for t in temp:
                match += t[1]

        nind = ttext.find(match)
        lenk = len(match)
        ind = nind + accumulator
        ttext = ttext[nind + lenk:]
        accumulator += lenk + nind

        f_entities.append({
            'matched_string': text[ind:ind + len(match)],
            'start_offset': ind,
            'end_offset': ind + len(match),
            'suggested_type': entity_type
        })

    response = {'tokens': tokens, 'entities': f_entities}
    print(len(response['entities']))

    return response

