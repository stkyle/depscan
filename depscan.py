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


from collections import namedtuple


class Dependency:
    def __init__(self, name, deptype=None, origin=None):
        self.name = name
        self.type = deptype
        self.origin = origin
        
        
class DependencyScanner(object):
    """
    target (str, module)
    """
    def __init__(self, target):
        self._target = target.strip()
        self.builtins = {}
        self.dependencies = {}
        self.libs = {}
        self.deps = []
        self.baseline = {}
    
    @property
    def target(self):
        if isinstance(self._target, StringTypes) and os.path.isfile(self._target):
            dirname, filename = os.path.split(self._target)
            script_txt = 'import sys;sys.path.append(\\"{}\\");'.format(dirname)
            script_txt += 'import {}'.format(os.path.splitext(filename)[0])
            target = '-c "{}"'.format(script_txt)
            return target
        elif isinstance(self._target, ModuleType):
            return self._target.__file__
        else:
            try:
                
                oldstdout = sys.stdout
                oldstderr = sys.stderr
                sys.stdout = None
                sys.stderr = None
                __import__(self._target.strip())
                return '-c "import {}"'.format(self._target)
            except ImportError:
                raise
            except AttributeError:
                return '-c "import {}"'.format(self._target)
            finally:
                sys.stdout = oldstdout
                sys.stderr = oldstderr
    
    def scan(self):
        stdout=open(tempfile.NamedTemporaryFile().name,'wb')
        stderr=open(tempfile.NamedTemporaryFile().name,'wb')
        
        baseline=open(tempfile.NamedTemporaryFile().name,'wb')
        try:
            cmd = ' '.join([sys.executable, '-v -c ""'])
            retcode = call(cmd, shell=True, stdout=stdout, stderr=baseline)
        except:
            pass
        
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
        baseline.close()
        
        with open(baseline.name,'rb') as base:
            for line in base:
                #line = stderr.readline()
                if line.startswith('import'):
                    #print(line.strip())
                    _name, pedigree = line.strip().split(' ',1)[1].split('#')
                    self.baseline[_name] = pedigree
        
        with open(stderr.name,'rb') as stderr:
            for line in stderr:
                #line = stderr.readline()
                if line.startswith('import'):
                    #print(line.strip())
                    _name, pedigree = line.strip().split(' ',1)[1].split('#')
                    dep = Dependency(_name.strip())
                    #print('{:40}    {}'.format(item, origin))
                    
                    pedigree = pedigree.split('from')
                    dep.type = pedigree[0].strip()
                    if len(pedigree)>1:
                        dep.origin = pedigree[1].strip()

                    if 'builtin' in dep.type and _name not in self.baseline:
                        self.builtins[_name] = dep.origin
                    elif _name not in self.baseline:
                        self.dependencies[_name] = dep.origin
                    
                    self.deps.append(dep)


def print_title(name, width=80):
    print('='*width)
    title = ''.join(['{:^',str(width), '}'])
    print(title.format(name))
    print('='*width)


baseline_cmd = 'python -vc ""'


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('no target provided')
        sys.exit()
    else:
        target = sys.argv[1]
    
    depscan = DependencyScanner(target)
    depscan.scan()
    
    print_title('Dependencies [{}]'.format(str(len(depscan.dependencies.keys()))))
    for k in sorted(depscan.dependencies.keys()):
        print('  {:50}    {}'.format(k,depscan.dependencies[k]))

    print_title('Builtins [{}]'.format(str(len(depscan.builtins.keys()))))
    for k in sorted(depscan.builtins.keys()):
        print('  {:50}    {}'.format(k,depscan.builtins[k]))
    
    print_title('Baseline Imports [{}]'.format(str(len(depscan.baseline.keys()))))
    for k in sorted(depscan.baseline.keys()):
        print('  {:50}    {}'.format(k,depscan.baseline[k]))
    
