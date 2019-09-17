import networkx as nx
from sortedcontainers import SortedListWithKey
from copy import deepcopy
from time import time

from query_iel import gr_ner
from inlinks import find_incoming_links_for_reference_dict
from entity_relatedness_formulas import milne_witten_relatedness
from wiki_db import query_neo4j
from binary_similarity_module import combine_rs_binary_similarity


def query_GKG(named_entities, limit):
    ref_index = -1
    reference_dict = {}

    suggested_types = {}
    for ne in named_entities:
        suggested_types[ne['matched_string']] = ne['suggested_type']

    GKG_results_dictionary = query_neo4j(suggested_types, limit)

    for ne in named_entities:
        ref_index += 1
        reference_dict[ref_index] = GKG_results_dictionary[ne['matched_string']]

    return reference_dict


# here we normalize each set of candidates on its own
def normalize_result_scores(reference_dict):
    for key, value in reference_dict.items():
        if value:
            max_resultScore = value[0]['resultScore']
        for entity in value:
            entity['resultScore'] /= max_resultScore


def nerd(dict):
    ############################################################
    ######## These are important application parameters ########

    GKG_entities_limit = 10

    a = 0.80  # popularity prior impact, combination of result score and document similarity
    b = 1 - a  # relatedness impact, given by some formula like Milne Witten

    c = 1  # neo4j pagerank+string matching metric impact
    d = 1 - c  # document similarity impact, here not utilized at all
    # here we just care about the metric retrieved from neo4j

    if 'text' in dict:
        raw_text = dict['text']

        named_entities = gr_ner(raw_text)['entities']

    else:
        list_of_terms = dict['list']
        separator = dict['separator']

        raw_text = ''
        named_entities = []
        index = 0

        for t in list_of_terms.split(separator):
            raw_text += t + ' '
            named_entities.append({
                'suggested_type': 'UNKNOWN',
                'matched_string': t,
                'start_offset': index,
                'end_offset': index + len(t)
            })
            index += len(t) + 1

    ref_count = len(named_entities)
    named_entity_index = -1
    for named_entity in named_entities:
        named_entity_index += 1

    reference_dict = query_GKG(named_entities, GKG_entities_limit)

    reference_dict_with_candidates = {}
    list_of_entities_with_no_candidates = []

    for named_entity_index, candidate_entity_list in reference_dict.items():
        if candidate_entity_list:
            reference_dict_with_candidates[named_entity_index] = candidate_entity_list
        else:
            ref_count -= 1
            list_of_entities_with_no_candidates.append(named_entity_index)

    reference_dict = reference_dict_with_candidates

    normalize_result_scores(reference_dict)

    if c < 1:
        rs_binary_similarity_ref_dict = combine_rs_binary_similarity(raw_text, reference_dict, c, d)
    else:
        rs_binary_similarity_ref_dict = reference_dict

    candidate_entity_count = {}

    for named_entity_index, candidate_entity_list in rs_binary_similarity_ref_dict.items():
        candidate_entity_count[named_entity_index] = len(candidate_entity_list)

    if ref_count == 0:
        return {}
    elif ref_count == 1:
        max_score = 0
        result_id = ''

        candidates = None
        for candidate_entity_list in rs_binary_similarity_ref_dict.values():
            candidates = candidate_entity_list

        for dictionary in candidates:
            if max_score < dictionary['resultScore']:
                max_score = dictionary['resultScore']
                result_id = dictionary['@id']

        result = []

        res = {}
        res['start_offset'] = named_entities[0]['start_offset']
        res['end_offset'] = named_entities[0]['end_offset']
        res['matched_string'] = raw_text[res['start_offset']:res['end_offset']]
        if 0 in reference_dict:
            cs = reference_dict[0]
            for c in cs:
                if c['@id'].endswith(result_id):
                    res['wiki_page'] = 'https://el.wikipedia.org/wiki/' + c['canonical_title'].replace(' ', '_')
                    break
        else:
            res['wiki_page'] = 'NONE'
        result.append(res)

        return result
    else:

        G = nx.Graph()

        for named_entity_index, candidate_entity_list in rs_binary_similarity_ref_dict.items():
            for entity in candidate_entity_list:
                G.add_node((named_entity_index, entity['@id']), weight=entity['resultScore'])

        inlinks_dict = find_incoming_links_for_reference_dict(rs_binary_similarity_ref_dict)

        temp = deepcopy(rs_binary_similarity_ref_dict)

        for key in rs_binary_similarity_ref_dict.keys():
            value = temp[key]
            del temp[key]
            for other_key, other_value in temp.items():
                for e1 in value:
                    for e2 in other_value:
                        first_node = (key, e1['@id'])
                        second_node = (other_key, e2['@id'])
                        first_node_weight = G.node[first_node]['weight']
                        second_node_weight = G.node[second_node]['weight']
                        relatedness = milne_witten_relatedness(inlinks_dict[e1['canonical_title']],
                                                               inlinks_dict[e2['canonical_title']])
                        popularity_prior = a * ((first_node_weight + second_node_weight) / 2)
                        relatedness_measure = b * relatedness
                        G.add_edge(first_node, second_node,
                                   weight=popularity_prior + relatedness_measure)

        potential = {}

        # for each node n of the graph, the potential_total dictionary holds the nodes that we get from the potential
        # dictionary, but also for each node x_n we get the total weight of the incident edges to x_n in the graph that
        # would be greedily built by n. Note that potential_total[n] does have an index for the set of n, and that should
        # always contain the node n.
        potential_total = {}

        # for each node n of the graph, the important_for_who dictionary holds the nodes that depend on n to make their
        # greedy choice, so if x in important_for_who[n], then the removal of n from the graph would lead to recalculation
        # of the greedy choice for x
        important_for_who = {}

        # this is the sorted list of (node, potential_total, potential), from which we pick the smallest element to remove
        sorted_list = SortedListWithKey(key=lambda tup: (tup[1], tup[2]))

        disambiguated_entities = 0
        for candidate_count in candidate_entity_count.values():
            if candidate_count == 1:
                disambiguated_entities += 1

        for x in G.nodes():
            important_for_who[x] = set()

        for x in G.nodes():
            potential[x] = {}
            potential_total[x] = {}
            x_index = x[0]

            for named_entity_index in candidate_entity_count.keys():
                if x_index != named_entity_index:
                    potential[x][named_entity_index] = SortedListWithKey(key=lambda tup: -tup[1])

            for (u, v, data) in G.edges(x, data=True):
                if x == u:
                    v_index = v[0]
                    potential[x][v_index].add((v, data['weight']))
                else:
                    u_index = u[0]
                    potential[x][u_index].add((u, data['weight']))

            sum_of_potential = 0
            set_of_nodes_in_complete_graph = {x}

            for potential_list in potential[x].values():
                greedily_chosen_node = potential_list[0][0]
                important_for_who[greedily_chosen_node].add(x)
                sum_of_potential += potential_list[0][1]
                set_of_nodes_in_complete_graph.add(greedily_chosen_node)

            for n in set_of_nodes_in_complete_graph:
                # this is the contribution of edges incident to n
                # to the weight of the graph formed by the nodes
                # that are greedily chosen by x
                n_contribution_in_complete_graph = 0
                for other_n in set_of_nodes_in_complete_graph:
                    if n != other_n:
                        n_contribution_in_complete_graph += G[n][other_n]['weight']
                potential_total[x][n[0]] = (n, n_contribution_in_complete_graph)

            resulting_graph_weight = 0
            for _, node_incident_edges_weight in potential_total[x].values():
                resulting_graph_weight += node_incident_edges_weight

            # every edge has been taken into account twice, so this is necessary
            resulting_graph_weight /= 2

            sorted_list.add((x, resulting_graph_weight, sum_of_potential))

        while True:

            if disambiguated_entities == ref_count:
                break

            # sorted list index to remove, first we consider the "smallest" node
            i = 0
            done = False

            while not done:
                node_to_evict, _, _ = sorted_list[i]
                node_to_evict_index = node_to_evict[0]

                # make sure the entity about to be removed isn't the only one in its set
                if candidate_entity_count[node_to_evict_index] > 1:
                    # remove sorted_list entry
                    del sorted_list[i]

                    # update important_for_who dictionary, so there are no nodes that
                    # think that they're important for an already deleted node
                    for potential_list in potential[node_to_evict].values():
                        important_for_who[potential_list[0][0]].remove(node_to_evict)

                    # remove potential and potential_total entries
                    del potential[node_to_evict]
                    del potential_total[node_to_evict]

                    if important_for_who[node_to_evict]:
                        new_sorted_list = SortedListWithKey(key=lambda tup: (tup[1], tup[2]))
                        sorted_list_updates = {}

                        for node in important_for_who[node_to_evict]:

                            same_as_node_to_evict, potential_to_subtract = potential[node][node_to_evict_index][0]
                            assert same_as_node_to_evict == node_to_evict
                            again_same_as_node_to_evict, total_graph_contribution_to_subtract = potential_total[node][
                                node_to_evict_index]
                            assert again_same_as_node_to_evict == node_to_evict

                            del potential[node][node_to_evict_index][0]
                            while potential[node][node_to_evict_index][0][0] not in G:
                                del potential[node][node_to_evict_index][0]

                            new_important_node, potential_to_add = potential[node][node_to_evict_index][0]

                            total_graph_contribution_to_add = 0
                            for index, (node_to_connect_with, node_to_connect_with_contribution) in potential_total[
                                node].items():
                                if index != node_to_evict_index:
                                    total_graph_contribution_to_add += G[new_important_node][node_to_connect_with][
                                        'weight']

                                    potential_total[node][index] = (
                                        node_to_connect_with, node_to_connect_with_contribution +
                                        G[new_important_node][node_to_connect_with]['weight'] -
                                        G[node_to_evict][node_to_connect_with]['weight'])

                            potential_total[node][node_to_evict_index] = (
                                new_important_node, total_graph_contribution_to_add)

                            # now new_important_node is the one "node" depends on
                            important_for_who[new_important_node].add(node)

                            sorted_list_updates[node] = (
                                total_graph_contribution_to_add - total_graph_contribution_to_subtract,
                                potential_to_add - potential_to_subtract)

                        for (node, total_graph_weight, potential_contribution) in sorted_list:
                            if node not in sorted_list_updates:
                                new_sorted_list.add((node, total_graph_weight, potential_contribution))
                            else:
                                new_sorted_list.add((node, total_graph_weight + sorted_list_updates[node][0],
                                                     potential_contribution + sorted_list_updates[node][1]))

                        sorted_list = new_sorted_list

                    # remove important_for_who and graph entries
                    del important_for_who[node_to_evict]
                    G.remove_node(node_to_evict)

                    candidate_entity_count[node_to_evict_index] -= 1
                    if candidate_entity_count[node_to_evict_index] == 1:
                        disambiguated_entities += 1
                    done = True
                else:
                    i += 1

        sorted_result_list = SortedListWithKey(key=lambda tup: tup[0])
        sorted_result_list.update(G.nodes())

        for node in G.nodes():
            total_incident_edge_weight = 0
            for u, v, data in G.edges(node, data=True):
                total_incident_edge_weight += data['weight']

        total_graph_weight = 0
        for u, v, data in G.edges(data=True):
            total_graph_weight += data['weight']

        index_to_GKG = {}

        for element in sorted_result_list:
            number, GKG_id = element
            index_to_GKG[number] = GKG_id

        result = []

        for i in range(len(named_entities)):
            res = {}
            res['start_offset'] = named_entities[i]['start_offset']
            res['end_offset'] = named_entities[i]['end_offset']
            res['matched_string'] = raw_text[res['start_offset']:res['end_offset']]
            if i in reference_dict:
                cs = reference_dict[i]
                for c in cs:
                    if c['@id'].endswith(index_to_GKG[i]):
                        res['wiki_page'] = 'https://el.wikipedia.org/wiki/' + c['canonical_title'].replace(' ', '_')
                        break
            else:
                res['wiki_page'] = 'NONE'
            result.append(res)

        return result
