import re
import itertools
import graphviz as gv

class InvalideSyntaxError(Exception):
  def __str__(self):
    return 'Invalide node specification'
class UndefinedIdentifierError(Exception):
  def __init__(self, identifier):
    self._identifier = identifier
  def __str__(self):
    return 'Undefined identifier ' + self._identifier
class RedefinedIdentifierError(Exception):
  def __init__(self, identifier):
    self._identifier = identifier
  def __str__(self):
    return 'Redefined identifier ' + self._identifier
class AnonymousAttributeError(Exception):
  def __init__(self, node):
    self._node = node
  def __str__(self):
    return str(node)

class Node:
  tmmnodepattern = r'''(\(\s*(?P<id>[\w]+)\s*\))?  # (optional) parentheses enclosed id
                       \s*                         # (optional) sperating spaces
                       (\[\s*(?P<label>[\w]+)\s*\])?# (optional) brakets enclosed label
                       \s*                         # (optional) sperating spaces
                       (?P<text>.+)                # (requried) node text'''
  tmmnoderegex = re.compile(tmmnodepattern, re.VERBOSE)
  def __init__(self, text):
    match = Node.tmmnoderegex.fullmatch(text)
    if not match:
      raise InvalideSyntaxError()
    self._text = match.group('text')
    self._identifier = match.group('id')
    self._label = match.group('label')
    self._parent = None
    self._children = []
    self._group = False
    self._level = -1
    self._index = -1
    self._attributes = dict()
    self._visible = True
  def __str__(self):
    return self.text
  # getters
  def text(self):
    return self._text;
  def identifier(self):
    return self._identifier;
  def label(self):
    return self._label;
  def parent(self):
    return self._parent;
  def attributes(self):
    return self._attributes
  # parser support
  @staticmethod
  def addchild(parent, child):
    parent._children.append(child)
    child._parent = parent
  # predicator
  def root(self):
    return not self._parent
  def leaf(self):
    return not self._children
  def intermediate(self):
    return self._parent and self._children
  def identified(self):
    return bool(self._identifier)
  def labeled(self):
    return bool(self._label)
  def visible(self):
    return self._visible
  @staticmethod
  def idpred(pattern, flags=0):
    if not isinstance(pattern, re.Pattern):
      pattern = re.compile(pattern, flags)
    return lambda node: pattern.match(node.identifier)
  @staticmethod
  def labelpred(pattern, flags=0):
    if not isinstance(pattern, re.Pattern):
      pattern = re.compile(pattern, flags)
    return lambda node: pattern.match(node.label)
  @staticmethod
  def textpred(pattern, flags=0):
    if not isinstance(pattern, re.Pattern):
      pattern = re.compile(pattern, flags)
    return lambda node: pattern.match(node.text)
  @staticmethod
  def attrpred(attr, value=None):
    return lambda node: (attr in node.attributes and
                         (value == None or value == node.attributes[attr]))
  # transformer
  def hide(self):
    self.visible = False
  def show(self):
    self.visible = False
  def asattr(self):
    if not self.label:
      raise AnonymousAttributeError(self)
    self.parent.attributes[self.label] = self
  def topology(self):
    if not self.parent:
      self.level = 0
    elif self.parent.level >= 0:
      self.level = self.parent.level+1
    for i, c in enumerate(self._children):
      c.index = i
  # iterator support
  def childiter(self):
    return iter(self._children)
  def labeledchilditer(self):
    return filter(lambda n: n.label, self._children)
  def unlabeledchilditer(self):
    return filter(lambda n: not n.label, self._children)
  def identifiedchilditer(self):
    return filter(lambda n: n.identifier, self._children)
  def unidentifiedchilditer(self):
    return filter(lambda n: not n.identifier, self._children)
  def visiblechilditer(self):
    return filter(lambda n: n.visible, self._children)
  def invisiblechilditer(self):
    return filter(lambda n: not n.visible, self._children)
  def siblingiter(self):
    if self.parent:
      for n in self.parent.children:
        if self != n:
          yield n
  def bfsiter(self):
    current = [self]
    while current:
      for n in current:
        yield n
      next = itertools.chain.from_iterable(n.childiter() for n in current)
      current = list(next)
  def dfsiter(self):
    yield self
    for n in itertools.chain.from_iterable(c.dfsiter() for c in self.childiter()):
      yield n

class Parser:
  nodepattern = r'''\A(?P<indent>[\s]*)     # (optional) leading spaces
                    [\*\-\+]                # (required) bullet 
                    \s*                     # (optional) sperating spaces
                    (?P<text>.+)            # (requried) node text
                    \n?\Z                   # (optional) end of line'''
  commentpattern = r'''\A(?P<indent>[\s]*)  # (optional) leading spaces
                       \#                   # (required) comment mark
                       (?P<text>.+)         # (requried) comment text
                       \n?\Z                # (optional) end of line'''
  noderegex = re.compile(nodepattern, re.VERBOSE)
  commentregex = re.compile(commentpattern, re.VERBOSE)
  # interface
  def __init__(self, nodefn, edgefn, singleroot = 'root'):
    ''' 
    nodefn(text) creates a node object,
    edgefn(pred, succ) creates an edge between pred and succ
    '''
    self._nodefn = nodefn
    self._edgefn = edgefn
    self._current = None
    self._stack = []
    self._singleroot = singleroot
  def parse(self, fileobj):
    roots = []
    for line in fileobj:
      if line.isspace():
        continue
      match = self.commentregex.fullmatch(line)
      if match:
        continue
      match = self.noderegex.fullmatch(line)
      if not match:
        raise InvalideSyntaxError()
      indent = match.group('indent')
      text = match.group('text')
      node = self._nodefn(text)
      while self._stack and self._stack[-1][1] >= indent:
        self._stack.pop()
      if self._stack:
        parent, _ = self._stack[-1]
        self._edgefn(parent, node)
      else:
        roots.append(node)
      self._stack.append((node, indent))
    if len(roots) > 1 and self._singleroot:
      pseudoroot = self._nodefn(self._singleroot)
      for root in roots:
        self._edgefn(pseudoroot, root);
      return pseudoroot
    return roots

class GraphvizBackend:
  def __init__(self, root, nodenamefn=Node.text, **kwargs):
    self.root = root
    self.nodenamefn = nodenamefn
    self._gvoptions = kwargs
  def render(self):
    graph = gv.Graph(**self._gvoptions)
    for n in self.root.dfsiter():
      # generate node name/label
      name = self.nodenamefn(n)
      label = n.text
      if self.nodenamefn is Node.text:
        label = None
      # nodes
      graph.node(name, label, **n.attributes())
      # edges
      for c in n.childiter():
        childname = self.nodenamefn(c)
        graph.edge(name, childname) # no edge label/attrs
    return graph
  
