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
  tmmnodepattern = r'''(\(\s*(?P<id>[\w\.]+)\s*\))?  # (optional) parentheses enclosed id
                       \s*                         # (optional) sperating spaces
                       (\[\s*(?P<label>[\w\.]+)\s*\])?# (optional) brakets enclosed label
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
    self._level = -1
    self._index = -1
    self._attributes = dict()
    self._visible = True
    self.graph=None
  def __str__(self):
    return self._text
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
  # transformer
  def hide(self):
    self._visible = False
  def show(self):
    self._visible = True
  def asattr(self):
    if not self._label:
      raise AnonymousAttributeError(self)
    self._parent._attributes[self._label] = self._text
  def topology(self):
    if not self._parent:
      self._level = 0
    elif self._parent._level >= 0:
      self._level = self._parent._level+1
    for i, c in enumerate(self._children):
      c.index = i
  # iterator support
  def childiter(self):
    return iter(self._children)
  def labeledchilditer(self):
    return filter(lambda n: n._label, self._children)
  def unlabeledchilditer(self):
    return filter(lambda n: not n.l_abel, self._children)
  def identifiedchilditer(self):
    return filter(lambda n: n._identifier, self._children)
  def unidentifiedchilditer(self):
    return filter(lambda n: not n._identifier, self._children)
  def visiblechilditer(self):
    return filter(lambda n: n._visible, self._children)
  def invisiblechilditer(self):
    return filter(lambda n: not n._visible, self._children)
  def ancestoriter(self):
    node = self._parent
    while node:
      yield node
      node = node._parent
  def siblingiter(self):
    if self._parent:
      for n in self._parent.children:
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
      indent = len(match.group('indent'))
      text = match.group('text')
      node = self._nodefn(text)
      while self._stack and self._stack[-1][1] >= indent:
        n, i = self._stack.pop()
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
      return [pseudoroot]
    return roots

# class UndefinedGroupError(Exception):
#   def __init__(self, group):
#     self._group = group
#   def __str__(self):
#     return 'Undefined group ' + self._group

class GraphvizBackend:
  class Group(Node):
    def __init__(self, name, graph):
      super().__init__(name)
      self.graph = graph
    def subgroup(self, group):
      self.addchild(self, group)
    def bottomupiter(self):
      for n in itertools.chain.from_iterable(c.bottomupiter()
                                             for c in self.childiter()):
        yield n
      yield self
  
  def __init__(self, root, nodenamefn=Node.text, extralinkattrs=None, **kwargs):
    self.root = root
    self.nodenamefn = nodenamefn
    if not extralinkattrs:
      extralinkattrs = {
        'style': 'dashed',
        'weight': '0.1'}
    self.extralinkattrs = extralinkattrs
    self._gvoptions = kwargs
    self._graph = gv.Graph(**self._gvoptions)
    self._passes = []
    self._identifiednodes = dict()
    self._grouproot = GraphvizBackend.Group('root', self._graph)
    # predicate for groups, links and graphviz attributes
    self._linkpred = lambda n: n.label() == 'link'
    self._attrpred = self.patternmatcher(Node.label, r'\A[gne]\..+')

  @staticmethod
  def patternmatcher(nodefn, pattern, flags=0):
    if not isinstance(pattern, re.Pattern):
      pattern = re.compile(pattern, flags)
    return lambda node: nodefn(node) and pattern.match(nodefn(node))
  @staticmethod
  def enumeratedmatcher(nodefn, eset):
    if not isinstance(eset, set):
      eset = set(eset)
    return lambda node: nodefn(node) in eset

  # grouping
  def group(self, nodes, name=None, parent=None, **kwargs):
    if parent is None:
      parent = self._grouproot
    if name is None:
      name = 'anonymousgroup'+str(len(self._groups))
    # graphattrs = self._gvoptions.copy()
    # graphattrs.update(kwargs)
    # subgraph = gv.Graph(name, **graphattrs)
    subgraph = gv.Graph(name)
    subgraph.attr(**kwargs)
    subgroup = GraphvizBackend.Group(name, subgraph)
    parent.subgroup(subgroup)
    for n in nodes:
      n.graph = subgraph
    return subgroup
  def groupsubtree(self, node, name=None, parent=None, **kwargs):
    return self.group(node.dfsiter(), name, parent, **kwargs)
      
  # group assemble op
  def groupassembleop(self, group):
    parent = group.parent()
    if parent:
      parent.graph.subgraph(group.graph)
  # collect identifier op
  def collectidentifiedop(self, node):
    if node.identified():
      if node.identifier() in self._identifiednodes:
        raise RedefinedIdentifierError(node.identifier())
      self._identifiednodes[node.identifier()] = node
  # hide attribute op
  def nodeattrop(self, node):
    if self._attrpred(node):
      node.asattr()
      node.hide()
    # hide extra link nodes
    if self._linkpred(node):
      node.hide()
  # extra link operation
  def extralinkop(self, node):
    if not self._linkpred(node):
      return
    if node.text() not in self._identifiednodes:
      raise UndefinedIdentifierError(node.text())
    tail = node.parent()
    head = self._identifiednodes[node.text()]
    if not tail.visible() or not head.visible():
      return
    edgeattrs = self.extralinkattrs.copy()
    edgeattrs.update({k[2:]: v for k, v in node.attributes().items()
                      if k.startswith('e.')})
    tailname = self.nodenamefn(tail)
    headname = self.nodenamefn(head)
    self._graph.edge(tailname, headname, **edgeattrs)
  # node render opeartion
  def noderenderop(self, node):
    if not node.visible():
      return
    name = self.nodenamefn(node)
    label = node.text()
    if self.nodenamefn is Node.text:
      label = None
    nodeattrs = {k[2:]: v for k, v in node.attributes().items()
                 if k.startswith('n.')}
    graph = node.graph
    if graph is None:
      graph = self._graph
    graph.node(name, label, **nodeattrs)
  # edge render operation
  def edgerenderop(self, node):
    parent = node.parent()
    if parent and node.visible() and parent.visible():
      edgeattrs = {k[2:]: v for k, v in node.attributes().items()
                   if k.startswith('e.')}
      name = self.nodenamefn(node)
      parentname = self.nodenamefn(parent)
      self._graph.edge(parentname, name, **edgeattrs)

  def _populatestdpasses(self):
    self._passes.append((self.collectidentifiedop, self.root.dfsiter()))
    self._passes.append((self.nodeattrop, self.root.dfsiter()))
    self._passes.append((self.noderenderop, self.root.dfsiter()))
    self._passes.append((self.groupassembleop, self._grouproot.bottomupiter()))
    self._passes.append((self.edgerenderop, self.root.dfsiter()))
    self._passes.append((self.extralinkop, self.root.dfsiter()))
  def render(self, prepasses=None, postpasses=None):
    if prepasses:
      self._passes.extend(prepasses)
    self._populatestdpasses()
    if postpasses:
      self._passes.extend(postpasses)
    for op, it in self._passes:
      for n in it:
        op(n)
    return self._graph
