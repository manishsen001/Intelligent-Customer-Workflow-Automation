import ast
import sys

with open('app.py', 'r') as f:
    source = f.read()

try:
    ast.parse(source)
    print('Syntax OK')
except SyntaxError as e:
    print(f'SyntaxError at line {e.lineno}: {e.msg}')
    with open('app.py') as f:
        lines = f.readlines()
    for i in range(max(0, e.lineno-10), min(len(open('app.py').readlines()), e.lineno+10)):
        print(f'{i+1:4d}: {lines[i].rstrip()}')