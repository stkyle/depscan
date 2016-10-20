#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module provides functions to scan python source files for dependencies.

@author: steve
"""
import sys
import os
import ast
import tempfile
from subprocess import call
from types import ModuleType
from types import StringTypes


class Dependency:
    """A Dependency can be a python package or module
    
    Args:
        name (): module or package name
        deptype (): the type of dependency
        origin (): where this dependency may be found locally
    """
    def __init__(self, name, deptype=None, origin=None):
        self.name = name
        self.type = deptype
        self.origin = origin
        
class Visitor(ast.NodeVisitor):
    """Base Class for Abstract Syntax Tree Traversal"""

    def __init__(self):
        self._data = []
        self.nodes=[]

    def add(self, datum):
        self._data.append(datum)

    @property
    def data(self):
        return self._data

    def visit(self, node):
        super(Visitor, self).visit(node)
        return self


class FuncLister(Visitor):
    """Traverse Abstract Syntax Tree and extract function definitions"""

    def visit_FunctionDef(self, node):
        self.nodes.append(node)
        self.add(node.name)
        self.generic_visit(node)

class KeywordLister(Visitor):
    """Traverse Abstract Syntax Tree and extract function definitions"""

    def visit_keyword(self, node):
        self.nodes.append(node)
        self.add(node.arg)
        self.generic_visit(node)

class ClassLister(Visitor):
    """Traverse Abstract Syntax Tree and extract class definitions"""
    def visit_ClassDef(self, node):
        self.add(node.name)
        self.nodes.append(node)
        self.generic_visit(node)


class ImportLister(Visitor):
    """Traverse Abstract Syntax Tree and extract import items"""

    def visit_Import(self, node):
        for name in node.names:
            self.add(name.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module_name = node.module
        self.add(module_name)
        self.generic_visit(node)


def get_ast(source_or_file):
    """returns an abstract syntax tree (ast) object"""
    source = source_or_file
    filename = '<unknown>'
    source_type = type(source_or_file)

    if source_type in StringTypes:
        if os.path.isfile(source):
            filename = source
            source = open(source_or_file, 'rb').read()

    return ast.parse(source, filename, mode='exec')


def get_functions(source_or_file, prop='data'):
    """extract function names and return as list"""
    tree = get_ast(source_or_file)
    lister = FuncLister().visit(tree)
    return getattr(lister, prop)


def get_classes(source_or_file, prop='data'):
    """extract class names and return as list"""
    tree = get_ast(source_or_file)
    lister = ClassLister().visit(tree)
    return getattr(lister, prop)


def get_imports(source_or_file):
    """extract imports and return as list"""
    tree = get_ast(source_or_file)
    lister = ImportLister().visit(tree)
    return lister.data

def get_keywords(source_or_file):
    """extract imports and return as list"""
    tree = get_ast(source_or_file)
    lister = KeywordLister().visit(tree)
    return lister.data


class DependencyScanner(object):
    """
    target (str|module): the item under test
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
    
