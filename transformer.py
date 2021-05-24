from greenery import fsm
from sre_parse import parse
from unparse import unparse
import sre_constants as sre
from hypothesis import given,strategies as st,note,assume,settings,example
import re,string
from test_regex import conservative_regex

#D=set(map(ord,string.digits))
D=set(map(ord,re.findall(r"\d","".join(map(chr,range(0x110000))))))
#W=set(map(ord,string.ascii_letters))|D|{ord("_")}
W=set(map(ord,re.findall(r"\w","".join(map(chr,range(0x110000))))))
#S=set(map(ord,string.whitespace))
S=set(map(ord,re.findall(r"\s","".join(map(chr,range(0x110000))))))
#print(*map(len,(W,D,S)))


#from SubPattern to greenery FSM
def nfa(r):
  n=fsm.epsilon([])
  for op,av in r:
    if op is sre.LITERAL:
      m=fsm.fsm({av},{0,1},0,{1},{0:{av:1}})
    elif op in (sre.ANY,sre.NOT_LITERAL):
      if op is sre.ANY:
        av=ord("\n") #unless re.M
      m=fsm.fsm({av,fsm.anything_else},{0,1},0,{1},{0:{fsm.anything_else:1}})
    elif op is sre.IN:
      a=set()
      x=False
      for op,av in av:
        if op is sre.NEGATE:
        	a|={fsm.anything_else}
        	x=True
        if op is sre.LITERAL:
          a|={av}
        elif op is sre.RANGE:
        	a|=set(range(av[0],av[1]+1))
        elif op is sre.CATEGORY:
          a|={sre.CATEGORY_DIGIT:D,
              sre.CATEGORY_NOT_DIGIT:D,
              sre.CATEGORY_SPACE:S,
              sre.CATEGORY_NOT_SPACE:S,
              sre.CATEGORY_WORD:W,
              sre.CATEGORY_NOT_WORD:W}[av]
          if av in (sre.CATEGORY_NOT_DIGIT,sre.CATEGORY_NOT_SPACE,sre.CATEGORY_NOT_WORD):
            a|={fsm.anything_else}
            x=True
      m=fsm.fsm(a,{0,1},0,{1},
      {0:{fsm.anything_else:1} if x else {i:1 for i in a}})
    elif op is sre.SUBPATTERN:
      m=nfa(av[-1])
    elif op is sre.BRANCH:
      m=fsm.null([])
      for i in av[1]:
        m|=nfa(i)
    elif op in (sre.MAX_REPEAT,sre.MIN_REPEAT):
      u=nfa(av[2])
      m=u*av[0]
      if av[1] is sre.MAXREPEAT:
        u=u.star()
      else:
        u|=fsm.epsilon([])
        u*=av[1]-av[0]
      m+=u
    else:
      raise NotImplementedError(op,"Only true regular expressions supported :^)")
    n+=m
  return n 
      
#from fsm to subpattern
def rx(n):
  acc=-1 #accept state
  
  st = [n.initial]
  i = 0
  while i < len(st):
    c = st[i]
    if c in n.map:
      for s in sorted(n.map[c],key=fsm.key):
        x = n.map[c][s]
        if x not in st:
          st.append(x)
    i += 1
  assert acc not in st #sanity check
  
  brz={}
  for a in n.states:
    brz[a]={}
    for b in n.states:
      brz[a][b]=[]
    brz[a][acc]=[[]] if a in n.finals else []
 
   
  for a in n.map:
    for s in n.map[a]:
      b=n.map[a][s]
      if s is fsm.anything_else:
        brz[a][b].append([(sre.IN,[(sre.NEGATE,None)]+[(sre.LITERAL,i) for i in n.alphabet if i is not fsm.anything_else])])
      else:
        brz[a][b].append([(sre.LITERAL,s)])
  
  for i in reversed(range(len(st))):
    a=st[i]
    if len(brz[a][a])>1:
      l=[(sre.BRANCH,(None,brz[a][a]))]
    elif len(brz[a][a])==1:
      l=brz[a][a][0]
    l=[(sre.MAX_REPEAT,(0,sre.MAXREPEAT,l))] if brz[a][a] else []
    del brz[a][a]
    for b in brz[a]:
      brz[a][b]=[l+i for i in brz[a][b]]
    for j in range(i):
      b=st[j]
      if brz[b][a]:
        u=[(sre.BRANCH,(None,brz[b][a]))] if len(brz[b][a])>1 else brz[b][a][0]
        del brz[b][a]
        for c in brz[a]:
          brz[b][c]+=[u+i for i in brz[a][c]]
      else:
        del brz[b][a]
  
  return [(sre.BRANCH,(None,brz[a][acc]))] if len(brz[a][acc])>1 else brz[a][acc][0] if brz[a][acc] else []
  

@given(conservative_regex())
@settings(deadline=None)
def test_idempotence(r):
  global cnt
  cnt+=1
  print(cnt,repr(r))
  u=rx(nfa(parse(r)))
  note(repr(u))
  v=rx(nfa(u))
  note(repr(v))
  assert u==rx(nfa(u))

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
    reject()
  u=re.compile(unparse(rx(n)))
  sr=data.draw(st.from_regex(r,fullmatch=True))
  su=data.draw(st.from_regex(u,fullmatch=True))
  s=data.draw(st.text())
  
  
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


@given(conservative_regex(),conservative_regex(),st.data())
@settings(deadline=None)
def test_intersection(r,s,d):
  global cnt
  cnt+=1
  print(cnt,r,s)
  t=d.draw(st.text())
  i=unparse(rx(nfa(parse(r))&nfa(parse(s))))
  assume(i)
  note(i[:100])
  if re.fullmatch(r,t) and re.fullmatch(s,t):
    note("y")
    assert re.fullmatch(i,t)
  else:
  	note("n")
  	assert not re.fullmatch(i,t)
