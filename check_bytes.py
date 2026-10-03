import sys

with open('app.py', 'rb') as f:
    content = f.read()

lines = content.splitlines()
for i in range(610, 630):
    line = lines[i]
    # Check for any non-ASCII or control characters
    for j, ch in enumerate(line):
        if ch > 127 or (ch < 32 and ch not in (9, 10, 13)):
            print(f'Line {i+1}, pos {j}: non-ASCII/control char {repr(chr(ch))} ord={ch}')
    # Check for any non-printable chars
    for j, ch in enumerate(line):
        if ch < 32 and ch not in (9, 10, 13):
            print(f'Line {i+1}, pos {j}: control char {repr(chr(ch))}')