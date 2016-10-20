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
import logging
from subprocess import call
from types import ModuleType
from types import StringTypes

log = logging.getLogger(__name__)


class Dependency(object):
    """A Dependency can be a python package or module
    
    Args:
        name (): module or package name
        deptype (): the type of dependency
        origin (): where this dependency may be found locally
    """
    def __init__(self, name, deptype=None, origin=None, level=0):
        self.name = name
        self.type = deptype
        self.origin = origin
        self.level = level
        self.baseline = False
        self.comment = ''
    
    def __repr__(self):
        return str(self.__dict__)
        
    def __str__(self):
        return '<{} [{}] {:d}>'.format(self.__class__.__name__, self.name, self.level)
        
    
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
        self.import_errors = {}
        self.libs = {}
        self.deps = []
        self.baseline = {}
    
    @property
    def target(self):
        if isinstance(self._target, StringTypes) and os.path.isfile(self._target):
            log.debug('Input File Identified')
            dirname, filename = os.path.split(self._target)
            module_name = os.path.splitext(filename)[0]
            script_txt = 'import sys;sys.path.append(\\"{}\\");'.format(dirname)
            script_txt += '__import__(\\"{}\\")'.format(module_name)
            target = '-c "{}"'.format(script_txt)
            log.debug('Generated Script: {}'.format(script_txt))
            return target
        elif isinstance(self._target, ModuleType):
            log.debug('Module Identified')
            return self._target.__file__
        else:
            try:
                log.debug('Testing Import...')
                module_name = self._target.strip()
                log.debug('Testing Import: {}'.format(module_name))
                oldstdout = sys.stdout
                oldstderr = sys.stderr
                sys.stdout = None
                sys.stderr = None
                __import__(module_name)
                return '-c "import {}"'.format(self._target)
            except ImportError:
                raise
            except AttributeError:
                return '-c "import {}"'.format(self._target)
            finally:
                sys.stdout = oldstdout
                sys.stderr = oldstderr
    
    @staticmethod
    def _parse_stream(stream):
        """returns list of lines related to import"""
        return [l.strip() for l in stream if l.strip().lower().startswith('import')]

    @staticmethod
    def _parse_line(line):
        """returns list of lines related to import"""
        if line.startswith('import '):
            line = line.replace('import ', '')
        return line
        
    def scan(self):
        self._scan_baseline()
        self._scan_using_import_trace()
        self._scan_using_ast()

    def _scan_using_ast(self):
        top_level_imports = get_imports(self._target)
        for t in top_level_imports:

            if t in self.dependencies.keys():
                self.dependencies[t].level = 1
            else:
                log.debug('AST FOUND NEW: "{}"'.format(t))
                dep = Dependency(t, level=1)
                self.deps.append(dep)
                self.dependencies[dep.name] = dep
  

    def _scan_baseline(self):
        baseline=open(tempfile.NamedTemporaryFile().name,'wb')
        try:
            cmd = ' '.join([sys.executable, '-v -c ""'])
            retcode = call(cmd, shell=True, stderr=baseline)
            log.debug('Baseline Scan Return Code: {:d}'.format(retcode))
        except:
            log.debug('Baseline Scan Failed: cmd="{}"'.format(cmd))
        
        baseline.close()
        with open(baseline.name,'rb') as baseline:
            for line in self._parse_stream(baseline):
                log.debug('[BL] {}'.format(line))
                if line.startswith('import'):
                    # get the name, pedigree
                    _name, pedigree = line.split(' ',1)[1].split('#')
                    
                    dep = Dependency(_name.strip())
                    dep.baseline = True
                    dep.comment = pedigree.strip()
                    dep.type = dep.comment.split(' ',1)[0]
                    self.deps.append(dep)
                    self.baseline[_name] = dep
                    
        
    
    def _scan_using_import_trace(self):
        stdout=open(tempfile.NamedTemporaryFile().name,'wb')
        stderr=open(tempfile.NamedTemporaryFile().name,'wb')
        retcode = None
        
        try:
            cmd = ' '.join([sys.executable, '-v', self.target])
            retcode = call(cmd, shell=True, stdout=stdout, stderr=stderr)
            if retcode < 0:
                print >>sys.stderr, "Child was terminated by signal", -retcode
            elif retcode >0:
                log.warn("Child returned : {}".format(str(retcode)))
                log.warn("Missing Dependency in {} likely".format(self._target))
            else:
                log.debug("Child returned : {}".format(str(retcode)))
                
        except OSError as e:
            print >>sys.stderr, "Execution failed:", e

        stdout.close()
        stderr.close()
        
        stderr_list = []
        with open(stderr.name,'rb') as stderr:
            stderr_list = self._parse_stream(stderr)
        
        for line in stderr_list:
            #line = stderr.readline()
            if line.startswith('import'):
                #print(line.strip())
                dep = Dependency('NONE')
                if '#' in line:
                    dep.comment = line.split('#',1)[1]
                    _name, pedigree = line.split(' ',1)[1].split('#')
                    pedigree = pedigree.split('from')
                    dep.name = _name.strip()
                    dep.type = pedigree[0].strip()
                elif ' as ' in line:
                    continue
                    _name, pedigree = line.split(' ',1)[1], ''
                    dep.name = _name.strip()
                    dep.type = 'alias'
                else:
                    log.debug(line)
                    _name, pedigree = line.split(' ',1)[1], ''
                    dep.name = _name.strip()
                
                #print('{:40}    {}'.format(item, origin))
                
                
                if len(pedigree)>1:
                    dep.origin = pedigree[1].strip()

                if 'builtin' in dep.type and dep.name not in self.baseline:
                    self.builtins[_name] = dep.origin
                elif dep.name not in self.baseline:
                    self.dependencies[dep.name] = dep
                
                self.deps.append(dep)
            elif 'ImportError' in line: 
                _name = line.rsplit(' ',1)[1]
                dep = Dependency(_name.strip())
                self.import_errors[_name.strip()] = dep
                self.dependencies[_name.strip()] = dep
                self.deps.append(dep)

                
def _print_title(name, width=80):
    print('='*width)
    title = ''.join(['{:^',str(width), '}'])
    print(title.format(name))
    print('='*width)

def _print_break(width=80):
    print('\n'+'*'*width)
    print('*'*width + '\n')

    

    
def _main():
    logging.basicConfig()
    log.setLevel(logging.WARN)
    
    if len(sys.argv) == 1:
        print('no target provided')
        return 1
    else:
        target = sys.argv[1]

    depscan = DependencyScanner(target)
    depscan.scan()
    
    _print_title('Dependencies', width=80)
    sorted_deps = sorted(depscan.dependencies.items())
    for i, (name, dep) in enumerate(sorted_deps):
        lvl = '(TOP_LEVEL)' if dep.level==1 else ''
        print '{:3d}: {name:40} {level}'.format(i, name=dep.name, level=lvl)

    
    if depscan.import_errors:
        _print_title('Import Errors (Missing Dependencies)', width=80)
        sorted_deps = sorted(depscan.import_errors.items())
        for i, (name, dep) in enumerate(sorted_deps):
            print '{:3d}: {name:40}'.format(i, name=dep.name)
        
if __name__ == '__main__':
    _main()
    

        
        
        
        
        
        
        
        
        
        
        
        
        
