from py2neo import Graph

graph = Graph(password="password")


def query_neo4j(queries, limit):
    results_dict = {}
    for s, t in queries.items():
        entities = (graph.data("""
            CALL db.index.fulltext.queryNodes("titles", "{}") YIELD node, score
        RETURN node.title as title, node.pagerank as pagerank, score as matching_score ORDER BY score DESCENDING LIMIT {}
        """.format(s, limit)))

        results_dict[s] = sorted([{
            '@id': x['title'],
            'name': x['title'],
            'canonical_title': x['title'],
            'resultScore': 0.5 * x['pagerank'] + 0.5 * x['matching_score']
        } for x in entities], key=lambda x: x['resultScore'], reverse=True)

    return results_dict
