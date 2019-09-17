from nltk.corpus import stopwords
from nltk.tokenize import RegexpTokenizer
from unidecode import unidecode  # important to remove accents, like in François Hollande
from math import log
from fuzzywuzzy import process, fuzz

tokenizer = RegexpTokenizer(r'\w+')
english_stop_words = set(stopwords.words('greek'))


def combine_rs_binary_similarity(context, normalized_ref_dict, c, d):
    context_lower_no_accents = unidecode(context).lower()
    context_words = tokenizer.tokenize(context_lower_no_accents)
    context_words_no_stopwords = [w for w in context_words if w not in english_stop_words]

    result = {}
    for key, value in normalized_ref_dict.items():
        temp = binary_similarity_measure(context_words_no_stopwords, value, c, d)
        result[key] = temp

    return result


def binary_similarity_measure(context_stemmed_words_no_stopwords, candidate_entities, c, d):
    if not candidate_entities:
        return []
    else:
        detailedDescriptions = [dictionary['articleBody'] for dictionary in candidate_entities]

        curated_detailedDescriptions = []

        for detailedDescription in detailedDescriptions:
            detailedDescription_lower_no_accents = unidecode(detailedDescription).lower()
            detailedDescription_words = tokenizer.tokenize(detailedDescription_lower_no_accents)
            detailedDescription_words_no_stopwords = [w for w in detailedDescription_words if
                                                      w not in english_stop_words]
            curated_detailedDescriptions.append(set(detailedDescription_words_no_stopwords))

        result = []
        index = -1
        log_number_of_context_terms = log(1 + len(context_stemmed_words_no_stopwords))

        for dictionary in candidate_entities:
            index += 1
            common_terms_count = 0
            for term in context_stemmed_words_no_stopwords:
                best_match = process.extractOne(term, curated_detailedDescriptions[index], score_cutoff=90,
                                                scorer=fuzz.ratio)
                if best_match is not None:
                    common_terms_count += 1

            if log_number_of_context_terms != 0:
                similarity = log(1 + common_terms_count) / log_number_of_context_terms
            else:
                similarity = 0

            normalized_value = c * dictionary['resultScore'] + d * similarity
            result.append(dictionary)
            result[index]['resultScore'] = normalized_value

        return result
