# gs2 compiler (version 0.2)
# (c) nooodl 2014

import re
import struct
import sys

if sys.platform == "win32":
    import os, msvcrt
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

mnemonics = {}
with open('gs2.py') as f:
    for line in f:
        if '#=' in line:
            a, b = line.split('#=')
            a = re.findall(r'\\x(..)', a.strip())
            b = b.strip().split(', ')
            assert len(a) == len(b)
            for i, j in zip(a, b):
                for k in j.split():
                    mnemonics[k] = chr(int(i, 16))

mnemonics["'"] = '\xe0'  # block1

for i in xrange(16):
    mnemonics['@%d' % i]    = chr(0xA0 | i)
    mnemonics['junk%d' % i] = chr(0xA0 | i)
for i, c in enumerate('abcd'):
    mnemonics['save-%s' % c] = chr(0xC8 | i)
    mnemonics['pop-%s' % c]  = chr(0xCC | i)
    mnemonics['push-%s' % c] = chr(0xD0 | i)
    mnemonics['nip-%s' % c]  = chr(0xD4 | i)
    mnemonics['tuck-%s' % c] = chr(0xD8 | i)
    mnemonics['show-%s' % c] = chr(0xDC | i)
for i in xrange(8):
    mnemonics['b%d'      % (i+1)] = chr(0xE0 | i)
    mnemonics['block%d'  % (i+1)] = chr(0xE0 | i)
    mnemonics['m%d'      % (i+1)] = chr(0xE8 | i)
    mnemonics['map%d'    % (i+1)] = chr(0xE8 | i)
    mnemonics['f%d'      % (i+1)] = chr(0xF0 | i)
    mnemonics['filter%d' % (i+1)] = chr(0xF0 | i)
    if 0xF8 | i < 0xFD:
        mnemonics['t%d'      % (i+1)] = chr(0xF8 | i)
        mnemonics['both%d'   % (i+1)] = chr(0xF8 | i)

def compile_num(i):
    if 0 <= i <= 10:
        return chr(i + 0x10)
    elif i == 100:
        return '\x1b'
    elif i == 1000:
        return '\x1c'
    elif i == 16:
        return '\x1d'
    elif i == 64:
        return '\x1e'
    elif i == 256:
        return '\x1f'

    elif 0x00 <= i <= 0xFF:
        return '\x01' + struct.pack('B', i)
    elif -0x8000 <= i <= 0x7FFF:
        return '\x02' + struct.pack('<h', i)
    elif -0x80000000 <= i <= 0x7FFFFFFF:
        return '\x03' + struct.pack('<l', i)
    else:
        raise Exception("couldn't compile number: %s" % i)

def compile_gs2(s):
    s = '\n'.join(l for l in s.split('\n') if l and l[0] != '#')
    tokens = re.findall(r'"[^"]*"|\S+', s)
    string_mode = False
    string_array = False
    strings = []
    output_code = []

    for i in tokens:
        # sys.stderr.write('[%s]\n' % i)
        try:
            v = compile_num(int(i))
            output_code.append(v)
            continue
        except ValueError: pass

        if i[0] == "'" and len(i) > 1:
            v = compile_num(ord(i[1]))
            output_code.append(v)
        elif i == ')':
            string_mode = False
            s_open  = '\x04'
            s_close = {
                'regular': '\x05',
                'array': '\x06',
                'printf': '\x9b',
                'regex-match': '\x9c',
                'regex-sub': '\x9d',
                'regex-find': '\x9e',
                'regex-split': '\x9f',
            }[string_type]
            if len(strings) == 1 and len(strings[0]) == 1:
                output_code.append('\x07' + strings[0])
            else:
                output_code.append(s_open + '\x07'.join(strings) + s_close)
        elif string_mode or i[0] == '"':
            if i[0] == '"':
                if string_mode:
                    strings.append(eval(i))
                elif len(eval(i)) == 1:
                    output_code.append('\x07' + eval(i))
                else:
                    output_code.append('\x04' + eval(i) + '\x05')
            else:
                strings.append(i)
        elif i in ['(', 'w(', 'p(', 'm(', 's(', 'f(', 'v(']:
            string_mode = True
            string_type = {
                '(': 'regular',
                'w(': 'array',
                'p(': 'printf',
                'm(': 'regex-match',
                's(': 'regex-sub',
                'f(': 'regex-find',
                'v(': 'regex-split',
            }[i]
            strings = []
        elif i.lower() in mnemonics:
            output_code.append(mnemonics[i.lower()])
        else:
            raise Exception('unknown symbol: ' + i)
    # shortcut: strip leading \x04
    return ''.join(output_code).lstrip('\x04')

if __name__ == '__main__':
    sys.stdout.write(compile_gs2(sys.stdin.read()))
