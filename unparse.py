import sre_constants as sre
from sre_parse import parse
import re, random, string
from hypothesis import given, strategies as st, note
from greenery import fsm, lego
from test_regex import conservative_regex

sp = "*?+\\()[]|.^${}-"


def ch(v):
    # Escape special chars
    return "\\" * (chr(v) in sp) + chr(v)


def unparse(re):
    s = ""
    for op, av in re:
        if op is sre.LITERAL:
            s += ch(av)
        elif op is sre.ANY:
            s += "."
        elif op in (sre.MAX_REPEAT, sre.MIN_REPEAT):
            s += "(" + unparse(av[2]) + ")"
            if av[1] == sre.MAXREPEAT and av[0] < 2:
                s += "*+"[av[0]]
            elif av[:2] == (0, 1):
                s += "?"
            else:
                s += "{" + str(av[0])
                if av[0] != av[1]:
                    s += ","
                    if av[1] < sre.MAXREPEAT:
                        # Upper bound not inf
                        s += str(av[1])
                s += "}"
            if op is sre.MIN_REPEAT:
                # non-greedy
                s += "?"
        elif op is sre.BRANCH:
            s += "(" + "|".join(unparse(a) for a in av[1]) + ")"
        elif op is sre.SUBPATTERN:
            s += "(" + unparse(av[-1]) + ")"
        elif op is sre.IN:
            s += "[" + unparse(av) + "]"
        elif op is sre.RANGE:
            s += "-".join(map(ch, av))
        elif op is sre.NOT_LITERAL:
            # Didn't know this existed
            s += "[^" + ch(av) + "]"
        elif op is sre.NEGATE:
            s += "^"
        elif op is sre.CATEGORY:
            s += {
                sre.CATEGORY_DIGIT: r"\d",
                sre.CATEGORY_NOT_DIGIT: r"\D",
                sre.CATEGORY_SPACE: r"\s",
                sre.CATEGORY_NOT_SPACE: r"\S",
                sre.CATEGORY_WORD: r"\w",
                sre.CATEGORY_NOT_WORD: r"\W",
            }[av]
        elif op is sre.AT:
            s += {
                sre.AT_BEGINNING: r"^",
                sre.AT_BEGINNING_STRING: r"\A",
                sre.AT_BOUNDARY: r"\b",
                sre.AT_NON_BOUNDARY: r"\B",
                sre.AT_END: r"$",
                sre.AT_END_STRING: r"\Z",
            }[av]
        else:
            raise NotImplementedError(op, "Only true regular expressions supported :^)")
    return s


@given(conservative_regex())
def test_idempotence(r):
    note(unparse(parse(r)))
    note(unparse(parse(unparse(parse(r)))))
    assert unparse(parse(r)) == unparse(parse(unparse(parse(r))))


@given(conservative_regex(), st.data())
def test_equivalence(r, data):
    note(r)
    u = unparse(parse(r))
    s = data.draw(st.from_regex(r, fullmatch=True))
    assert bool(re.match(r, s)) == bool(re.match(u, s))

    s = data.draw(st.from_regex(u, fullmatch=True))
    assert bool(re.match(r, s)) == bool(re.match(u, s))

    s = data.draw(st.text())
    assert bool(re.match(r, s)) == bool(re.match(u, s))


# test_idempotence()
# test_equivalence()
