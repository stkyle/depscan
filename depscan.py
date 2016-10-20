# -*- coding: utf-8 -*-
"""
Created on Wed Oct 19 19:51:01 2016

@author: steve
"""
import sys
import os
from subprocess import call
import tempfile
from types import ModuleType
from types import StringTypes



class DependencyScanner(object):
    """
    target (str, module)
    """
    def __init__(self, target):
        self._target = target
        self.builtins = {}
        self.dependencies = {}
    
    @property
    def target(self):
        if isinstance(self._target, StringTypes) and os.path.isfile(self._target):
            return self._target
        elif isinstance(self._target, ModuleType):
            return self._target.__file__
        else:
            try:
                mod = __import__(self._target)
                return mod.__file__
            except ImportError:
                raise
            except AttributeError:
                return '-c import {}'.format(self._target)
    
    def scan(self):
        stdout=open(tempfile.NamedTemporaryFile().name,'wb')
        stderr=open(tempfile.NamedTemporaryFile().name,'wb')
        try:
            cmd = ' '.join([sys.executable, '-v', self.target])
            retcode = call(cmd, shell=True, stdout=stdout, stderr=stderr)
            if retcode < 0:
                print >>sys.stderr, "Child was terminated by signal", -retcode
            else:
                print >>sys.stderr, "Child returned", retcode
        except OSError as e:
            print >>sys.stderr, "Execution failed:", e

        stdout.close()
        stderr.close()
        
        with open(stderr.name,'rb') as stderr:
            for line in stderr:
                #line = stderr.readline()
                if line.startswith('import'):
                    #print(line.strip())
                    item, origin = line.strip().split(' ',1)[1].split('#')
                    #print('{:40}    {}'.format(item, origin))
                    if 'builtin' in origin:
                        self.builtins[item] = origin
                    else:
                        self.dependencies[item] = origin


def print_title(name, width=80):
    print('='*width)
    title = ''.join(['{:^',str(width), '}'])
    print(title.format(name))
    print('='*width)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('no target provided')
        sys.exit()
    else:
        target = sys.argv[1]
    
    depscan = DependencyScanner(target)
    depscan.scan()
    
    print_title('Dependencies')
    for k in sorted(depscan.dependencies.keys()):
        print('  {:50}    {}'.format(k,depscan.dependencies[k]))

    print_title('Builtins')
    for k in sorted(depscan.builtins.keys()):
        print('  {:50}    {}'.format(k,depscan.builtins[k]))
    
