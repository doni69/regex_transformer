from greenery import fsm
from sre_parse import parse
from unparse import unparse
import sre_constants as sre
from hypothesis import given, strategies as st, note, assume, settings
import re, string
from test_regex import conservative_regex

# D = set(map(ord, string.digits))
# W = set(map(ord, string.ascii_letters)) | D | {ord("_")}
# S = set(map(ord, string.whitespace))
D = set(map(ord, re.findall(r"\d", "".join(map(chr, range(0x110000))))))
W = set(map(ord, re.findall(r"\w", "".join(map(chr, range(0x110000))))))
S = set(map(ord, re.findall(r"\s", "".join(map(chr, range(0x110000))))))


# from SubPattern to greenery FSM
def to_fsm(pat):
    n = fsm.epsilon([])
    for op, av in pat:
        if op is sre.LITERAL:
            m = fsm.fsm({av}, {0, 1}, 0, {1}, {0: {av: 1}})
        elif op in (sre.ANY, sre.NOT_LITERAL):
            if op is sre.ANY:
                av = ord("\n")  # unless re.M
            m = fsm.fsm(
                {av, fsm.anything_else}, {0, 1}, 0, {1}, {0: {fsm.anything_else: 1}}
            )
        elif op is sre.IN:
            al = set()
            neg = False
            for op, av in av:
                if op is sre.NEGATE:
                    al |= {fsm.anything_else}
                    neg = True
                if op is sre.LITERAL:
                    al |= {av}
                elif op is sre.RANGE:
                    al |= set(range(av[0], av[1] + 1))
                elif op is sre.CATEGORY:
                    al |= {
                        sre.CATEGORY_DIGIT: D,
                        sre.CATEGORY_NOT_DIGIT: D,
                        sre.CATEGORY_SPACE: S,
                        sre.CATEGORY_NOT_SPACE: S,
                        sre.CATEGORY_WORD: W,
                        sre.CATEGORY_NOT_WORD: W,
                    }[av]
                    if av in (
                        sre.CATEGORY_NOT_DIGIT,
                        sre.CATEGORY_NOT_SPACE,
                        sre.CATEGORY_NOT_WORD,
                    ):
                        al |= {fsm.anything_else}
                        neg = True
            m = fsm.fsm(
                al,
                {0, 1},
                0,
                {1},
                {0: {fsm.anything_else: 1} if neg else {i: 1 for i in al}},
            )
        elif op is sre.SUBPATTERN:
            m = to_fsm(av[-1])
        elif op is sre.BRANCH:
            m = fsm.null([])
            for i in av[1]:
                m |= to_fsm(i)
        elif op in (sre.MAX_REPEAT, sre.MIN_REPEAT):
            u = to_fsm(av[2])
            m = u * av[0]
            if av[1] is sre.MAXREPEAT:
                u = u.star()
            else:
                u |= fsm.epsilon([])
                u *= av[1] - av[0]
            m += u
        else:
            raise NotImplementedError(op, "Only true regular expressions supported :^)")
        n += m
    return n


# Modified from greenery.lego
# from fsm to subpattern
def from_fsm(n):
    acc = -1  # Accept state

    # A list of states in order of distance from the initial state
    st = [n.initial]
    i = 0
    while i < len(st):
        c = st[i]
        if c in n.map:
            for s in sorted(n.map[c], key=fsm.key):
                x = n.map[c][s]
                if x not in st:
                    st.append(x)
        i += 1
    assert acc not in st  # sanity check

    # brz[a][b] is the subpattern describing the transition from state a to state b
    # each subpattern in the list is a branch: [p,q,r] would represent p OR q OR r

    # Initialise
    brz = {}
    for a in n.states:
        brz[a] = {}
        for b in n.states:
            brz[a][b] = []
        brz[a][acc] = [[]] if a in n.finals else []

    # Populate map with unit transitions between neighbouring states
    for a in n.map:
        for ch in n.map[a]:
            b = n.map[a][ch]
            if ch is fsm.anything_else:
                brz[a][b].append(
                    [
                        (
                            sre.IN,
                            [(sre.NEGATE, None)]
                            + [
                                (sre.LITERAL, c)
                                for c in n.alphabet
                                if c is not fsm.anything_else
                            ],
                        )
                    ]
                )
            else:
                brz[a][b].append([(sre.LITERAL, ch)])

    # Collapse states
    for i in reversed(range(len(st))):
        # Loops
        a = st[i]
        if len(brz[a][a]) > 1:
            lp = [(sre.BRANCH, (None, brz[a][a]))]
        elif len(brz[a][a]) == 1:
            lp = brz[a][a][0]
        lp = [(sre.MAX_REPEAT, (0, sre.MAXREPEAT, lp))] if brz[a][a] else []
        del brz[a][a]
        # State a to b via a (loop)
        for b in brz[a]:
            brz[a][b] = [lp + sp for sp in brz[a][b]]

        for j in range(i):
            b = st[j]
            if brz[b][a]:
                u = (
                    [(sre.BRANCH, (None, brz[b][a]))]
                    if len(brz[b][a]) > 1
                    else brz[b][a][0]
                )
                del brz[b][a]
                # State b to c via a
                for c in brz[a]:
                    brz[b][c] += [u + sp for sp in brz[a][c]]
            else:
                del brz[b][a]

    # Initial state to accept state
    return (
        [(sre.BRANCH, (None, brz[a][acc]))]
        if len(brz[a][acc]) > 1
        else brz[a][acc][0]
        if brz[a][acc]
        else []
    )


# Useful shorthands
def inter(r, s):
    return unparse(from_fsm(to_fsm(parse(r)) & to_fsm(parse(s))))


def diff(r, s):
    return unparse(from_fsm(to_fsm(parse(r)) - to_fsm(parse(s))))


def symdif(r, s):
    return unparse(from_fsm(to_fsm(parse(r)) ^ to_fsm(parse(s))))


# This test is mostly useless due to set order not being preserved
@given(conservative_regex())
@settings(deadline=None)
def test_idempotence(r):
    try:
        n = to_fsm(parse(r))
    except NotImplementedError:
        reject()

    u = from_fsm(n)
    note(repr(u))
    v = from_fsm(to_fsm(u))
    note(repr(v))
    assert u == v


@given(conservative_regex(), st.data())
@settings(deadline=None)
def test_equivalence(r, data):
    try:
        n = to_fsm(parse(r))
    except NotImplementedError:
        reject()

    u = re.compile(unparse(from_fsm(n)))
    sr = data.draw(st.from_regex(r, fullmatch=True))
    su = data.draw(st.from_regex(u, fullmatch=True))
    s = data.draw(st.text())

    note(repr(r))
    note(repr(u))

    note(repr(sr))
    assert re.fullmatch(u, sr)

    note(repr(su))
    assert re.fullmatch(r, su)

    note(repr(s))
    assert bool(re.fullmatch(r, s)) == bool(re.fullmatch(u, s))


@given(conservative_regex(), conservative_regex(), st.data())
@settings(deadline=None)
def test_intersection(r, s, d):
    t = d.draw(st.text())
    try:
        i = inter(r, s)
    except NotImplementedError:
        reject()
    assume(i)  # There is no distinction between null and epsilon language

    note(repr(i[:100]))
    assert bool(re.fullmatch(r, t) and re.fullmatch(s, t)) == bool(re.fullmatch(i, t))


@given(conservative_regex(), conservative_regex(), st.data())
@settings(deadline=None)
def test_difference(r, s, d):
    t = d.draw(st.text())
    try:
        i = diff(r, s)
    except NotImplementedError:
        reject()
    assume(i)  # There is no distinction between null and epsilon language

    note(repr(i[:100]))
    assert bool(re.fullmatch(r, t) and not re.fullmatch(s, t)) == bool(
        re.fullmatch(i, t)
    )


# test_equivalence()
# test_intersection()
# test_difference()
