from abc import ABC, abstractmethod
import os
SEP='/'

class NodeObject(ABC):
    '''Base class for NodeFile and NodeDir.'''
    def __init__(self, id:str, dir, is_dir=False):
        self.id = id
        if dir:
            self.abs_id = (dir.abs_id if not dir.abs_id.endswith(SEP) else dir.abs_id[:-len(SEP)]) + SEP + id
        else:
            self.abs_id = id if id else SEP
        self._is_dir = is_dir
        self.dir = dir
        self.data = None

    def get_dir(self):
        return self.dir
    
    def set_data(self, data):
        self.data = data
        
    def get_data(self):
        return self.data
    
    def get_root(self):
        cnt = self
        while(cnt.dir):
            cnt = cnt.dir
        return cnt
    
    def get_root_id(self):
        root = self.get_root()
        return root.id
    
    def get_root_abs_id(self):
        root = self.get_root()
        return root.abs_id
    
    def get_true_path(self, drive:str):
        return drive + self.abs_id
    
    @abstractmethod
    def is_leaf(self) -> bool:
        pass
    
    def is_dir(self) -> bool:
        return self._is_dir
    
    def pop(self):
        '''Remove the current node from its directory.'''
        if not self.dir:
            raise ValueError("Root directory can not be removed.")
        
        return self.dir.elements.pop(self.id)
    
    def __str__(self) -> str:
        return self.abs_id
    
class NodeFile(NodeObject):
    '''Represents files.'''
    def __init__(self, id:str, dir) -> None:
        super().__init__(id, dir, is_dir=False)
    
    def is_leaf(self) -> bool:
        return True
    
class NodeDir(NodeObject):
    '''Represents directories.'''
    def __init__(self, id:str, dir):
        super().__init__(id, dir, is_dir=True)
        self.elements = {}
        
    def __getitem__(self, key):
        return self.elements[key]
    
    def is_root(self) -> bool:
        return self.dir is None
    
    def is_leaf(self) -> bool:
        return not self.elements.items()
        
    def get_elements(self):
        return self.elements.items()
    
    def ls(self, path:str='', filter=None, abs_id=False) -> str:
        '''Get the representation string for the current directory.'''
        dir = self.cd(path)
        prnt = dir._ls(self, 0, '', filter, abs_id)
        return prnt
    
    def _ls(self, node:NodeObject, depth:int, prnt:str, filter=None, abs_id=False) -> str:
        if not filter:
            filter = lambda _ : True
        
        for id, n in node.get_elements():
            if filter(n):
                if not n.is_dir():
                    prnt += '  ' * depth + '- ' + (str(n) if abs_id else id) + '\n'
                else:
                    prnt += '  ' * depth + '+ ' + (str(n) if abs_id else id) + '\n'
                    prnt = self._ls(n, depth+1, prnt, filter=filter, abs_id=abs_id) + '\n'

        return prnt.strip()

    def touch(self, path:str):
        '''Create a file under the specified directory.'''
        sections = path.split(SEP)
        cnt = self
        for sect in sections[:-1]:
            if sect not in cnt.elements.keys():
                cnt.elements.update({sect: NodeDir(sect, cnt)})
            cnt = cnt[sect]
        file_name = sections[-1]
        cnt.elements.update({file_name: NodeFile(file_name, cnt)})
                
        return self
    
    def mkdir(self, path:str):
        '''Create a sub directory under the specified directory.'''
        sections = path.split(SEP)
        cnt = self
        for sect in sections:
            if sect not in cnt.elements.keys():
                cnt.elements.update({sect: NodeDir(sect, cnt)})
            cnt = cnt[sect]
                
        return self

    def rm(self, path:str):
        '''Remove a node from the specified directory.'''
        sections = path.split(SEP)
        cnt = self
        for sect in sections:
            if sect in cnt.elements.keys():
                cnt = cnt[sect]
            else:
                raise ValueError(f"Invalid relative path {sect} for directory {cnt}.")
        
        return cnt.pop()
    
    def concat(self, node:NodeObject):
        '''Concatenate a node (a file or a directory) under the current directory.'''
        self.elements.update({node.id:node})
        return self
    
    def cd(self, path:str=''):
        '''Change directory. Return the new node.'''
        path = path.strip()
        if not path:
            return self
        
        sections = path.split(SEP)
        if sections[0] == self.get_root_id():
            root = self.get_root()
            return root.cd(SEP.join(sections[1:]))
        
        cnt = self
        for sect in sections:
            if sect in cnt.elements.keys():
                 cnt = cnt[sect]
            else:
                raise ValueError(f"Invalid relative path {sect} for directory {cnt}")
        return cnt
    
    def walk(self, filter=None) -> list:
        '''Get all the nodes under current directory.'''
        if not filter:
            filter = lambda _ : True
            
        lst = []
        for _, n in self.get_elements():
            if filter(n):
                lst.append(n)
            if n.is_dir():
                lst.extend(n.walk(filter))

        return lst
    
    
if __name__ == "__main__":
    root = NodeDir('', dir=None)
    print(f"root: {root}")
    a = root.mkdir('a')['a']
    g = a.touch('g')['g']
    h = a.mkdir('h')['h']
    i = h.mkdir('i')['i']
    b = root.touch('b')['b']
    c = root.mkdir('c')['c']
    d = c.touch('d')['d']
    e = c.mkdir('e')['e']
    e.touch('f')
    e.mkdir('o/p')
    
    filter = lambda n: n.get_data() != 'remove'
    print(f"Before modifying:")
    print(root.ls(path='', filter=filter))
    print(f"cd to f'a{SEP}h'")
    print(root.cd(f'a{SEP}h'))
    
    print(f"rm a/h from {root}")
    root.rm(f'a{SEP}h')
    print(f"After modifying:")
    print(root.ls(path='', filter=filter, abs_id=True))
    
    print(f"cd to 'c/e' from {c}")
    print(c.cd(f'{SEP}c{SEP}e'))
    print(f"ls from c")
    print(c.ls(path='', filter=filter))
    