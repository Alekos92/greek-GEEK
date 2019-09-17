from math import log


def milne_witten_relatedness(setA, setB):
    setA = set(setA)
    setB = set(setB)
    W = 945038
    # W = 20000000

    a = len(setA)
    b = len(setB)

    if a == 0 or b == 0:
        return 0

    common = len(setA & setB)

    if common == 0:
        return 0

    num = log(max(a, b)) - log(common)
    den = log(W) - log(min(a, b))
    relatedness = 1 - (num / den)
    if relatedness > 0:
        return relatedness

    return 0


def pmi_relatedness(setA, setB):
    W = 5388705

    a = len(setA)
    b = len(setB)

    if a == 0 or b == 0:
        return 0

    common = len(setA & setB)

    if common == 0:
        return 0

    num = common / W
    den = (a / W) * (b / W)

    return num / den


def jaccard_relatedness(setA, setB):
    common = len(setA & setB)

    if common == 0:
        return 0

    unified = len(setA | setB)

    return common / unified


def my_relatedness(setA, setB):
    a = len(setA)
    b = len(setB)

    if a == 0 or b == 0:
        return 0

    common = len(setA & setB)

    if common == 0:
        return 0

    num = log(1 + common)
    den = log(1 + min(a, b))

    return num / den


def milne_witten_relatedness_roots(canonical_title_A, canonical_title_B, setA, setB):
    W = 5388705
    a = len(setA)
    b = len(setB)

    if a == 0 or b == 0:
        return 0

    common = len(setA & setB)

    if common == 0:
        return 0

    num = log(max(a, b)) - log(common)
    den = log(W) - log(min(a, b))
    relatedness = 1 - (num / den)
    if relatedness <= 0:
        return 0

    A_links_to_B = canonical_title_A in setB
    B_links_to_A = canonical_title_B in setA

    if A_links_to_B and B_links_to_A:
        return relatedness ** (1 / 3)
    elif A_links_to_B or B_links_to_A:
        return relatedness ** (1 / 2)
    else:
        return relatedness
