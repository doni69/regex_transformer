from greenery import fsm
from sre_parse import parse
import sre_constants as sre
from hypothesis import given,strategies as st,note,assume,settings
import re,string
from test_regex import conservative_regex

D=set("0123456789")
W=set("_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
S=set(" \t\n\r\v\f")
ALL=D#set(map(chr,range(0x80))) #ASCII

def nfa(re,cat=True):
  a=set()
  n=fsm.epsilon(a) if cat else fsm.null(a)
  neg=False
  for op,av in re:
    if op in (sre.LITERAL,sre.NOT_LITERAL,sre.ANY,sre.RANGE,sre.CATEGORY):
      if op is sre.LITERAL:
        av={chr(av)}
      elif op is sre.NOT_LITERAL:
        av=ALL-{chr(av)}
      elif op is sre.ANY:
        av=ALL-{"\n"} #unless re.M
      elif op is sre.RANGE:
        av=set(map(chr,range(av[0],av[1]+1)))
      elif op is sre.CATEGORY:
        av={
      sre.CATEGORY_DIGIT:D,
      sre.CATEGORY_NOT_DIGIT:ALL-D,
      sre.CATEGORY_SPACE:S,
      sre.CATEGORY_NOT_SPACE:ALL-S,
      sre.CATEGORY_WORD:D|W,
      sre.CATEGORY_NOT_WORD:ALL-D-W
      }[av]
      if neg:
        av=ALL-av
        a&=av
      else:
        a|=av
      m=fsm.fsm(
      a,{0,1},
      0,{1},
      {0:{i:1 for i in av}})
    elif op is sre.IN:
      m=nfa(av,False)
    elif op is sre.SUBPATTERN:
      m=nfa(av[-1])
    elif op is sre.BRANCH:
      m=fsm.null(a)
      for i in av[1]:
        m|=nfa(i)
    elif op in (sre.MAX_REPEAT,sre.MIN_REPEAT):
      u=nfa(av[2])
      m=u*av[0]
      if av[1] is sre.MAXREPEAT:
        u=u.star()
      else:
        u|=fsm.epsilon(a)
        u*=av[1]-av[0]
      m+=u
    elif op is sre.NEGATE:
      neg=True
      a=ALL.copy()
      n|=fsm.fsm(
      a,{0,1},0,{1},
      {0:{i:1 for i in a}})
      continue
    else:
      raise NotImplementedError(op,"Only true regular expressions supported :^)")
    if cat:
      n+=m
    elif neg:
      n&=m
    else:
      n|=m
  return n

def rx(n):
  acc=-1
  
  st = [n.initial]
  i = 0
  while i < len(st):
    c = st[i]
    if c in n.map:
      for s in sorted(n.map[c]):
        x = n.map[c][s]
        if x not in st:
          st.append(x)
    i += 1
  assert acc not in st
  brz={}
  for a in n.states:
    brz[a]={}
    for b in n.states:
      brz[a][b]=set()
    brz[a][acc]={""} if a in n.finals else set()
  
  for a in n.map:
    for s in n.map[a]:
      b=n.map[a][s]
      brz[a][b]|={re.escape(s)}
  
  for i in reversed(range(len(st))):
    a=st[i]
    l="("+"|".join(sorted(brz[a][a]))+")*" if brz[a][a] else ""
    del brz[a][a]
    for b in sorted(brz[a]):
      brz[a][b]={l+i for i in brz[a][b]}
    for j in range(i):
      b=st[j]
      if brz[b][a]:
        u="("+"|".join(sorted(brz[b][a]))+")"
        del brz[b][a]
        for c in brz[a]:
          brz[b][c]|={u+i for i in brz[a][c]}
      else:
        del brz[b][a]
        
  return "|".join(sorted(brz[a][acc]))

@given(conservative_regex())
@settings(deadline=None)
def test_idempotence(r):
  global cnt
  cnt+=1
  print(cnt,repr(r))
  u=rx(nfa(parse(r)))
  note(repr(u))
  assert u==rx(nfa(parse(u)))

@given(conservative_regex(),st.data())
@settings(deadline=None)
def test_equivalence(r,data):
  global cnt
  cnt+=1
  print(cnt,repr(r))
  try:
    n=nfa(parse(r))
  except NotImplementedError:
    print("Not Implemented :^)")
    return
  u=rx(n)
  sr=data.draw(st.from_regex(r,fullmatch=True))
  su=data.draw(st.from_regex(u,fullmatch=True))
  s=data.draw(st.text(alphabet=ALL))
  assume(all(i in ALL for i in sr))
  assume(all(i in ALL for i in su))
  
  note(repr(r))
  note(repr(u))
  note(repr(sr))
  note(re.match(u,sr))
  assert bool(re.match(u,sr))
  note(repr(su))
  note(re.match(r,su))
  assert bool(re.match(r,su))
  note(repr(s))
  note(re.match(r,s))
  note(re.match(u,s))
  assert bool(re.match(r,s))==bool(re.match(u,s))

cnt=0
test_idempotence()
cnt=0
test_equivalence()
