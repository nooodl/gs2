# gs2 compiler (version 0.1)
# (c) nooodl 2014

import re
import struct
import sys

if sys.platform == "win32":
    import os, msvcrt
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

mnemonics = {
    'nop': '\x00',
    '{': '\x08',  # open block
    '}': '\x09',  # close block
    
    "'": '\xe0',  # block1
    'z1 zipwith1': '\xee',
    'z2 zipwith2': '\xef',
    'dm1 dump-map1': '\xf6',
    'df1 dump-filter1': '\xf7',
    'm:': '\xfe', # open rest-of-program map 
    'f:': '\xff', # open rest-of-program filter 

    'new-line': '\x0a',
    'empty-list': '\x0b',
    'empty-block': '\x0c',
    'space': '\x0d',
    'make-array': '\x0e',
    'exit': '\x0f',
    'negate reverse eval': '\x20',
    'bnot head': '\x21',
    'not tail': '\x22',
    'abs init': '\x23',
    'digits last': '\x24',
    'random': '\x25',
    'dec left-uncons': '\x26',
    'inc right-uncons': '\x27',
    'sign min': '\x28',
    'thousand max': '\x29',
    'double lines': '\x2a',
    'half unlines': '\x2b',
    'square words': '\x2c',
    'sqrt unwords': '\x2d',
    'range length': '\x2e',
    "range1 sort": '\x2f',
    '+ add cat': '\x30',
    '- sub diff': '\x31',
    '* mul join times fold': '\x32',
    '/ div chunks split each': '\x33',
    "% mod step clean-split map": '\x34',
    '& and get when filter': '\x35',
    '| or unless': '\x36',
    '^ xor concatmap': '\x37',
    'smallest both': '\x38',
    'biggest': '\x39',
    'clamp': '\x3a',
    'gcd take': '\x3c',
    'lcm drop': '\x3d',
    'pow index': '\x3e',
    'log member': '\x3f',
    'dup': '\x40',
    'dup2': '\x41',
    'swap': '\x42',
    'rot': '\x43',
    'rrot': '\x44',
    'over': '\x45',
    'nip': '\x46',
    'tuck': '\x47',
    '2dup': '\x48',
    'pick': '\x49',
    'roll': '\x4a',
    'get-stack': '\x4b',
    'leave-top': '\x4c',
    'itemize': '\x4d',
    'rrange': '\x4e',
    'crange': '\x4f',
    
    'show': '\x52',
    'map-show': '\x53',
    'show-lines': '\x54',
    'show-words': '\x55',
    'read-num': '\x56',
    'read-nums': '\x57',
    'show-line': '\x58',
    'show-space': '\x59',
    'show-comma': '\x5a',
    'show-python': '\x5b',
    'ljust': '\x5c',
    'center': '\x5d',
    'rjust': '\x5e',
    'inspect': '\x5f',
    'logical-and': '\x60',
    'logical-or': '\x61',
    'divides left-cons': '\x62',
    'divmod group': '\x63',
    'sum even': '\x64',
    'product odd': '\x65',
    'fizzbuzz': '\x66',
    'popcnt': '\x67',
    'hello': '\x68',
    'base': '\x69',
    'binary': '\x6a',
    'is-prime': '\x6b',
    'primes': '\x6c',
    'scan': '\x6d',
    
    'lt': '\x70',
    'eq': '\x71',
    'gt': '\x72',
    'ge': '\x73',
    'ne': '\x74',
    'le': '\x75',
    'cmp': '\x76',
    'sorted': '\x77',
    'shift-left inits': '\x78', 
    'shift-right tails': '\x79', 
    'digit-left enumerate': '\x7a', 
    'digit-right': '\x7b', 
    'power-of-2': '\x7c', 
    'power-of-10': '\x7d', 
    'sub-power-of-2': '\x7e', 
    'sub-power-of-10': '\x7f', 
    'pair': '\x80',
    'copies': '\x81',
    'take-end': '\x82',
    'cartesian-product': '\x83',
    'uppercase-alphabet': '\x84',
    'lowercase-alphabet': '\x85',
    'ascii-digits': '\x86',
    'printable-ascii': '\x87',
    'is-alnum': '\x88',
    'is-alpha': '\x89',
    'is-digit': '\x8a',
    'is-lower': '\x8b',
    'is-space': '\x8c',
    'is-upper': '\x8d',
    'is-printable': '\x8e',
    'is-hexdigit': '\x8f',
    'dump': '\x90',
    'compress': '\x91',
    'select': '\x92',
    'permutations': '\x93',
    'fold-product': '\x94',
    'repeat-product': '\x95',
    'combinations': '\x96',
    'combinations-with-replacement': '\x97',
    'pairwise': '\x98',
    'flatten': '\x99',
    'transpose': '\x9a',
    'zip': '\xb0',
    'zipwith': '\xb1',
    'counter': '\xb2',
    
    'line-mode': '\x30',
    'word-mode': '\x31',
    'line-mode-skip-first': '\x32',
}

mnemonics = {w: v for k,v in mnemonics.items() for w in k.split()}

for i in xrange(16):
    mnemonics['@%d' % i] = chr(0xA0 | i)
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
