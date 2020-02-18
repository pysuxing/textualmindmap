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
  tmmpattern = r'''
  (\((?P<id>[\w\.]+)\))?      # (optional) parentheses enclosed id
  \s*                         # (optional) sperating spaces
  (\[(?P<tags>[\w\.,]+)\])?   # (optional) brakets enclosed tags
  \s*                         # (optional) sperating spaces
  (?P<text>.+)                # (requried) node text'''
  tmmregex = re.compile(tmmpattern, re.VERBOSE)
  def __init__(self, text):
    match = self.tmmregex.fullmatch(text)
    if not match:
      raise InvalideSyntaxError()
    self._text = match.group('text')
    self._identifier = match.group('id')
    self._tags = set()
    if match.group('tags'):
      self._tags = match.group('tags').split(',')
    self._parent = None
    self._children = []
    self._level = 0
    self._index = 0
    self._attributes = dict()
  def __str__(self):
    return self._text
  # getters
  def text(self):
    return self._text;
  def identifier(self):
    return self._identifier;
  def tags(self):
    return self._tags;
  def parent(self):
    return self._parent;
  def attributes(self):
    return self._attributes
  # child add/remove
  def attach(self, parent, update=False):
    assert self._parent is None
    self._parent = parent
    self._parent._children.append(self)
    if update:
      self._index = len(parent._children)-1
      for c in self.dfsiter():
        c._level = c._parent._level+1
  def detach(self, update=False):
    assert self._parent and self._parent._children[self._index] == self
    for sibling in self._parent._children[self._index+1:]:
      sibling._index -= 1
    del self._parent._children[self._index]
    self._parent = None
    if update:
      self._index = 0
      self._level = 0
      for c in self.descendantiter():
        c._level = c._parent._level+1
  # parser support
  def addchild(self, child):
    child.attach(self)
  # predicator
  def identified(self):
    return bool(self._identifier)
  def tagged(self):
    return bool(self._tags)
  def root(self):
    return not self._parent
  def leaf(self):
    return not self._children
  def intermediate(self):
    return self._parent and self._children
  # iterator support
  def childiter(self):
    return iter(self._children)
  def siblingiter(self):
    if self._parent:
      for n in self._parent.children:
        if self != n:
          yield n
  def ancestoriter(self):
    node = self._parent
    while node:
      yield node
      node = node._parent
  def bfsiter(self):
    current = [self]
    while current:
      for n in current:
        yield n
      next = itertools.chain.from_iterable(n.childiter() for n in current)
      current = list(next)
  def descendantiter(self):
    return itertools.chain.from_iterable(c.dfsiter() for c in self.childiter())
  def dfsiter(self):
    yield self
    for n in self.descendantiter():
      yield n
  # update topology
  def canonicalize(self):
    if self._parent:
      self._level = c._parent._level+1
      self._index = self._parent._children.index(self)
    else:
      self._level = 0
      self._index = 0
    for c in self.descendantiter():
      c._level = c._parent._level+1
    for n in itertools.takewhile(lambda n: not n.leaf(), self.dfsiter()):
      for i, c in enumerate(n._children):
        c._index = i

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

class NonuniqueGroupError(Exception):
  def __init__(self, node):
    self._node = node
  def __str__(self):
    return 'Nonunique groups for node ' + str(node)
class LinkNodeError(Exception):
  def __init__(self, node):
    self._node = node
  def __str__(self):
    return 'Invalide link node ' + str(node)

class GVNode(Node):
  def __init__(self, text, **kwargs):
    super().__init__(text)
    self._attrs = kwargs
    self._edgeattrs = dict()
    self._group=None
  def attr(self, **kwargs):
    self._attrs.update(kwargs)
  def edgeattr(self, **kwargs):
    self._edgeattrs.update(kwargs)
class GVGroup(Node):
  def __init__(self, name, **kwargs):
    super().__init__(name)
    self._attrs = kwargs
    self._groupattrs = dict()
    self._graph = None
  def attr(self, **kwargs):
    self._attrs.update(kwargs)
  def groupattr(self, **kwargs):
    self._groupattrs.update(kwargs)
  def postdfsiter(self):
    for n in itertools.chain.from_iterable(c.postdfsiter() for c in self.childiter()):
      yield n
    yield self
  def commonancestor(self, other):
    assert self != other
    ancestors = set(self.ancestoriter())
    for g in other.ancestoriter():
      if g in ancestors:
        return g
    assert False

class GraphvizBackend:
  def __init__(self, root, **kwargs):
    self._root = root
    self._grouproot = GVGroup('grouproot', **kwargs)
    self._passes = []
    self._identifiednodes = dict()
    self.linkpredicate = lambda n: 'link' in n.tags()
    self.nodenamefn = Node.text
    self.extraedgeattrs = dict(weight='0.01', style='dashed', color='red')
  # grouping
  def group(self, nodes, name=None, parent=None, **kwargs):
    if parent is None:
      parent = self._grouproot
    if name is None:
      name = 'anongroup-{}-{}'.format(id(parent), len(parent._children))
    group = GVGroup(name, **kwargs)
    group.attach(parent)
    for n in nodes:
      if n._group:
        raise NonuniqueGroupError(n)
      n._group = group
    return group
  def groupsubtree(self, node, name=None, parent=None, **kwargs):
    return self.group(node.dfsiter(), name, parent, **kwargs)

  # group node op
  def groupnodeop(self, node):
    if not node._group:
      node._group = self._grouproot
  # create graph op
  def creategraphop(self, group):
    group._graph = gv.Graph(group.text(), **group._attrs)
    group._graph.attr(**group._groupattrs)
  # render node opeartion
  def rendernodeop(self, node):
    if self.linkpredicate(node):
      return
    name = self.nodenamefn(node)
    label = None
    if not self.nodenamefn is Node.text:
      label = node.text()
    assert node._group and node._group._graph
    node._group._graph.node(name, label, **node._attrs)
  # assemble graph op
  def assemblegraphop(self, group):
    if group.parent():
      group.parent()._graph.subgraph(group._graph)
  # render edge operation
  def renderedgeop(self, node):
    if not node.parent() or self.linkpredicate(node):
      return
    parent = node.parent()
    headname = self.nodenamefn(node)
    tailname = self.nodenamefn(parent)
    # add edge to the root graph
    self._grouproot._graph.edge(tailname, headname, **node._edgeattrs)
  # collect node identifier op
  def collectnodeidop(self, node):
    if node.identified():
      if node.identifier() in self._identifiednodes:
        raise RedefinedIdentifierError(node.identifier())
      self._identifiednodes[node.identifier()] = node
  # extra edge operation
  def extraedgeop(self, node):
    if not node.parent() or not self.linkpredicate(node):
      return
    if node.text() not in self._identifiednodes:
      raise UndefinedIdentifierError(node.text())
    if node._children:
      raise LinkNodeError(node)
    tail = node.parent()
    head = self._identifiednodes[node.text()]
    tailname = self.nodenamefn(tail)
    headname = self.nodenamefn(head)
    # add edge to the root graph
    attrs = self.extraedgeattrs.copy()
    attrs.update(node._edgeattrs)
    self._grouproot._graph.edge(tailname, headname, **attrs)

  def _populatestdpasses(self):
    self._passes.append((self.groupnodeop, self._root.dfsiter()))
    self._passes.append((self.creategraphop, self._grouproot.dfsiter()))
    self._passes.append((self.rendernodeop, self._root.dfsiter()))
    self._passes.append((self.assemblegraphop, self._grouproot.postdfsiter()))
    self._passes.append((self.renderedgeop, self._root.dfsiter()))
    self._passes.append((self.collectnodeidop, self._root.dfsiter()))
    self._passes.append((self.extraedgeop, self._root.dfsiter()))
  def render(self):
    self._populatestdpasses()
    for op, it in self._passes:
      for n in it:
        op(n)
    return self._grouproot._graph
