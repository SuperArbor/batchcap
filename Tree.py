from abc import ABC, abstractmethod

class NodeObject(ABC):
    '''Base class for NodeFile and NodeDir.'''
    def __init__(self, id:str, dir, is_dir=False):
        self.id = id
        self.is_dir = is_dir
        self.dir = dir

    def get_dir(self):
        return self.dir
    
    
class NodeFile(NodeObject):
    '''Represents files.'''
    def __init__(self, id:str, dir) -> None:
        super().__init__(id, dir, is_dir=False)
    
    def __str__(self) -> str:
        return self.id
    
class NodeDir(NodeObject):
    '''Represents directories.'''
    def __init__(self, id:str, dir):
        super().__init__(id, dir, is_dir=True)
        self.elements = {}
    
    def __getitem__(self, key):
        return self.elements[key]
    
    def is_root(self):
        return self.dir is None
    
    def get_elements(self):
        return self.elements.items()
    
    def list_tree(self):
        prnt = self._list_tree(self, 0, '')
        return prnt
    
    def _list_tree(self, node:NodeObject, depth:int, prnt:str):
        '''Get the representation string for the current directory.'''
        for id, n in node.get_elements():
            if not n.is_dir:
                prnt += '  ' * depth + '-' + id + '\n'
            else:
                prnt += '  ' * depth + '+' + id + '\n'
                prnt = self._list_tree(n, depth+1, prnt) + '\n'

        return prnt.strip()

    def touch(self, id:str):
        '''Create a file under the current directory.'''
        file = NodeFile(id, self)
        self.elements.update({id:file})
        return file
    
    def mkdir(self, id:str):
        '''Create a sub directory under the current directory.'''
        dir = NodeDir(id, self)
        self.elements.update({id:dir})
        return dir

    def concat(self, node):
        '''Concatenate a node (a file or a directory) under the current directory.'''
        self.elements.update({node.id:node})
        return self

    def __str__(self) -> str:
        return self.list_tree()
    
if __name__ == "__main__":
    root = NodeDir('/', dir=None)
    a = root.mkdir('a')
    a.touch('g')
    b = root.touch('b')
    c = root.mkdir('c')
    c.touch('d')
    e = c.mkdir('e')
    e.touch('f')
    
    print(root)


    

