# gs2 compiler (version 0.1)
# (c) nooodl 2014

import re
import struct
import sys

if sys.platform == "win32":
    import os, msvcrt
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

tokens = re.findall(r'"[^"]*"|\S+', sys.stdin.read())

mnemonics = {
    'nop': '\x00',
    '{': '\x08',  # open block
    '}': '\x09',  # close block
    'm:': '\xfe', # open rest-of-program map 
    'f:': '\xff', # open rest-of-program filter 

    'new-line': '\x0a',
    'empty-list': '\x0b',
    'empty-block': '\x0c',
    'block-to-array': '\x0d',
    'make-array': '\x0e',
    'exit': '\x0f',
    'negate reverse': '\x20',
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
    '/ div group split each': '\x33',
    "% mod step clean-split map": '\x34',
    '& and get when filter': '\x35',
    '| or unless': '\x36',
    '^ xor concatmap': '\x37',
    'smallest': '\x38',
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
    'printf': '\x50',
    'lprintf': '\x51',
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
    'divides': '\x62',
    'divmod chunks': '\x63',
    'sum even': '\x64',
    'product odd': '\x65',
    'fizzbuzz': '\x66',
    'popcnt': '\x67',
    'base': '\x68',
    'binary': '\x69',
    'is-prime': '\x6a',
    'nth-prime': '\x6b',
    'n-primes': '\x6c',
    'primes-below': '\x6d',
    'next-prime': '\x6e',
    'totient': '\x6f',
    'lt': '\x70',
    'eq': '\x71',
    'gt': '\x72',
    'ge': '\x73',
    'ne': '\x74',
    'le': '\x75',
    'cmp': '\x76',
    'sorted': '\x77',
    'shift-left': '\x78', 
    'shift-right': '\x79', 
    'digit-left': '\x7a', 
    'digit-right': '\x7b', 
    'power-of-2': '\x7c', 
    'power-of-10': '\x7d', 
    'sub-power-of-2': '\x7e', 
    'sub-power-of-10': '\x7f', 
    'empty-matrix': '\x80', 
    'matrix-take': '\x81', 
    'flip': '\x82', 
    'transpose': '\x83', 
    'rotate-cw': '\x84', 
    'rotate-ccw': '\x85', 
    'show-matrix': '\x86', 
    'from-rows': '\x87', 
}

mnemonics = {w: v for k,v in mnemonics.items() for w in k.split()}

for i in xrange(16):
    mnemonics['@%d' % i] = chr(0xA0 | i)
for i, c in enumerate('abcdefgh'):
    mnemonics['save-%s' % c]     = chr(0xB0 | i)
    mnemonics['put-%s' % c]      = chr(0xB8 | i)
    mnemonics['get-%s' % c]      = chr(0xC0 | i)
    mnemonics['exchange-%s' % c] = chr(0xC8 | i)
    mnemonics['tuck-%s' % c]     = chr(0xD0 | i)
    mnemonics['show-%s' % c]     = chr(0xD8 | i)
for i in xrange(8):
    mnemonics['b%d' % (i+1)] = chr(0xE0 | i)
    mnemonics['m%d' % (i+1)] = chr(0xE8 | i)
    mnemonics['f%d' % (i+1)] = chr(0xF0 | i)
    mnemonics['r%d' % (i+1)] = chr(0xF8 | i)
del mnemonics['r7'], mnemonics['r8']

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

string_mode = False
string_array = False
strings = []
output_code = []

for i in tokens:
    sys.stderr.write('[%s]\n' % i)
    try:
        v = compile_num(int(i))
        output_code.append(v)
        continue
    except ValueError: pass

    if i == ')':
        string_mode = False
        s_open  = '\x04'
        s_close = '\x06' if string_array else '\x05'
        output_code.append(s_open + '\x07'.join(strings) + s_close)
    elif string_mode:
        if i[0] == '"':
            strings.append(eval(i))
        else:
            strings.append(i)
    elif i == '(':
        string_mode = True
        string_array = False
        strings = []
    elif i == 'w(':
        string_mode = True
        string_array = True
        strings = []
    elif i.lower() in mnemonics:
        output_code.append(mnemonics[i.lower()])
    else:
        raise Exception('unknown symbol: ' + i)

# shortcut: strip leading \x04
sys.stderr.write('\n'.join(' '.join('{:02x}'.format(ord(c)) for c in x) for x in
    output_code) + '\n')
sys.stdout.write(''.join(output_code).lstrip('\x04'))
