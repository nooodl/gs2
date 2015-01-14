# gs2 interpreter (version 0.2)
# (c) nooodl 2014

import copy
import inspect
import itertools as it
import math
import operator
import os
import random
import re
import string
import struct
import sys
import traceback

from collections import namedtuple
from fractions import gcd

Block = namedtuple('Block', 'code')
STRING_ENDS = '\x05\x06' + ''.join(map(chr, range(0x9b, 0xa0)))

DEBUG = False

def log(x):
    if not DEBUG: return
    line, name = inspect.stack()[1][2:4]
    sys.stderr.write('\x1b[36m%s:%d\x1b[34m: %r\x1b[0m\n' % (name, line, x))

def lcm(a, b):
    if (a, b) == (0, 0): return 0
    return abs(a * b) // gcd(a, b)

def product(xs):
    p = 1
    for x in xs:
        p *= x
    return p

def split(a, b, clean=False):
    res = [[]]
    lb = len(b)

    i = 0
    while i <= len(a) - lb:
        if a[i:i + lb] == b:
            res.append([])
            i += lb
        else:
            res[-1].append(a[i])
            i += 1

    return filter(None, res) if clean else res

def join(a, b):
    res = []
    for i, x in enumerate(a):
        if i > 0:
            res.extend(b)
        res.extend(x)
    return res

def set_diff(a, b):
    res = []
    for i in a:
        if i not in b:
            res.append(i)
    return res

def set_and(a, b):
    res = []
    for i in a:
        if i in b:
            res.append(i)
    return res

def set_or(a, b):
    return a + set_diff(b, a)

def set_xor(a, b):
    return set_diff(a, b) + set_diff(b, a)

# prime number functions
prime_list = []
sieved = 2
composite = set([1])

def sieve(limit):
    global prime_list
    global sieved
    global composite
    if limit <= sieved: return

    prime_list = []
    for i in range(2, limit):
        if i in composite: continue
        for j in range(i*2, limit, i):
            composite.add(j)
        prime_list.append(i)
    sieved = limit

sieve(1000)

def is_prime(n):
    global prime_list
    sieve(n+1)
    return n not in composite

def nth_prime(n):
    global prime_list
    sieve(int(math.log(n) * n) + 100)
    return prime_list[n-1]

def n_primes(n):
    global prime_list
    sieve(int(math.log(n) * n) + 100)
    return prime_list[:n]

def primes_below(n):
    global prime_list
    sieve(n+1)
    return list(it.takewhile(lambda x: x < n, prime_list))

def next_prime(n):
    n += 1
    while not is_prime(n): n += 1
    return n

def totient(n):
    count = 0
    for i in xrange(1, n+1):
        if gcd(n, i) == 1: count += 1
    return count
    
def factor(n, exps=False):
    if is_num(n):
        p = 2
        res = []
        while n > 1:
            while n % p == 0:
                res.append(p)
                n //= p
            p = next_prime(p)
        if exps:
            res = [[k, len(g)] for k, g in it.groupby(res)]
        return res
    elif is_list(n):
        if is_num(n[0]):
            n = group(n, 2)
        p = 1
        for b, e in n: p *= b ** e
        return p
    else:
        raise TypeError('factor')

def chunks(x, y):
    # chunks(range(12), 3) ==> [[0, 1, 2], [3, 4, 5], ...]
    while x:
        yield x[:y]
        x = x[y:]

def tokenize(prog):
    # string hack
    cs = STRING_ENDS
    if re.match('^[^\x04]*[%s]' % cs, prog):
        prog = '\x04' + prog
    
    mode = None
    if prog[0] in '\x30\x31\x32': # set mode
        mode = prog[0]
        prog = prog[1:]
    
    token_re = [
        '\x01.',                     # unsigned byte
        '\x02..',                    # signed short
        '\x03....',                  # signed long
        '\x04[^%s]*[%s]' % (cs, cs), # string (array)
        '\x07.',                     # 1 char string
        '.',                         # regular token
    ]

    tokens = re.findall('|'.join(token_re), prog, re.DOTALL)

    final = []
    blocks = [Block([])]
    i = 0 
    while i < len(tokens):
        t = tokens[i]
        log(tokens[i:])
        if t == '\x08': #= {
            blocks.append(Block([]))
            final.append('\x00')
        elif t == '\x09': #= }
            blocks[-2].code.append(blocks.pop())
            blocks[-1].code.append(final.pop())
        elif '\xe0' <= t <= '\xff' and ord(t) & 7 < 6:
            # quick block
            # 0b111XXYYY -- Y+1 is number of tokens, X is end token:
            #   0 = nop (0x00)  2 = filter (0x35)
            #   1 = map (0x34)  3 = both (0x38)
            # but 0xfe and 0xff are special (see below.)
            num = (ord(t) & 7) + 1
            ts = blocks[-1].code[-num:]
            del blocks[-1].code[-num:]
            blocks[-1].code.append(Block(ts))
            blocks[-1].code.append('\x00\x34\x35\x38'[(ord(t) >> 3) & 3])
        elif t in '\xee\xef': #= z1 zipwith1, z2 zipwith2
            # zipwith (1/2 tokens)
            num = (ord(t) & 1) + 1
            ts = blocks[-1].code[-num:]
            del blocks[-1].code[-num:]
            blocks[-1].code.append(Block(ts))
            blocks[-1].code.append('\xb1')
        elif t in '\xf6\xf7': #= dm1 dump-map1, df1 dump-filter1
            # like m1/f1 with dump prepended to block
            # useful with transpose, pairwise, cartesian-product, etc.
            f = {'\xf6': '\x34', '\xf7': '\x35'}[t]
            x = blocks[-1].code.pop()
            blocks[-1].code.extend([Block(['\x90', x]), f])
        elif t == '\xfe': #= m:
            blocks.append(Block([]))
            final.append('\x34')
        elif t == '\xff': #= f:
            blocks.append(Block([]))
            final.append('\x35')
        else:
            blocks[-1].code.append(t)
        i += 1

    while final:
        blocks[-2].code.append(blocks.pop())
        blocks[-1].code.append(final.pop())
    
    assert len(blocks) == 1
    main = blocks[0]
    
    if mode == '\x30': #= line-mode
        main = Block(['\x2a', main, '\x34', '\x54'])
    elif mode == '\x31': #= word-mode
        main = Block(['\x2c', main, '\x34', '\x55'])
    elif mode == '\x32': #= line-mode-skip-first
        main = Block(['\x2a', '\x22', main, '\x34', '\x54'])
    
    main.code.extend(final)
    return main

is_num   = lambda v: isinstance(v, (int, long))
is_list  = lambda v: isinstance(v, list)
is_block = lambda v: isinstance(v, Block)

def to_gs(ps): return map(ord, ps)

def to_ps(gs):
    if is_list(gs): return ''.join(map(chr, gs))
    else: return chr(gs)
    
def regex_count(pattern):
    c = 0
    if pattern[0] == ']':
        c = 1
        pattern = pattern[1:]
    elif pattern[0] == '}':
        c = ord(pattern[1])
        pattern = pattern[2:]
    return (c, pattern)

def show(value, nest=False):
    if is_list(value):
        return ''.join(show(x, nest=True) for x in value)
    elif nest and is_num(value):
        return chr(value)
    else:
        return str(value)

class Stack(list):
    def __init__(self, *args):
        list.__init__(self, *args)
        self.junk = []
    def pop(self, i=-1, junk=True):
        x = list.pop(self, i)
        if junk: self.junk.append(x)
        return x

class GS2(object):
    def __init__(self, code, stdin=''):
        self.code = code
        self.stdin = to_gs(stdin)
        self.stack = Stack([self.stdin])
        self.regs = {
            0: stdin,                # A
            1: len(stdin),           # B
            2: to_gs(code),          # C
            3: random.randint(0, 2), # D
        }
        self.counter = 1

    def run(self):
        try:
            self.evaluate(tokenize(self.code))
            print ''.join(map(show, self.stack))
        except Exception:
            # If the code fails, print something meaningful to stderr,
            # but quine on stdout: this allows GS2 to good at simple
            # "print this string" programs -- just upload a plaintext
            # file, it's unlikely to be valid GS2 code.
            traceback.print_exc()
            if not DEBUG: sys.stdout.write(self.code)

    def evaluate(self, block):
        log(block)
        for t in block.code:
            if is_block(t):
                self.stack.append(t)
            elif t[0] == '\x00': #= nop
                pass
            elif t[0] == '\x01': # push unsigned byte
                self.stack.append(struct.unpack('<B', t[1:])[0])
            elif t[0] == '\x02': # push signed short
                self.stack.append(struct.unpack('<h', t[1:])[0])
            elif t[0] == '\x03': # push signed long
                self.stack.append(struct.unpack('<l', t[1:])[0])

            elif t[0] == '\x04': # string
                assert len(t) >= 2
                assert t[-1] in STRING_ENDS
                strings = t[1:-1].split('\x07')
                strings = map(to_gs, strings)
                if t[-1] == '\x05': # regular
                    self.stack += strings
                elif t[-1] == '\x06': # array
                    self.stack.append(strings)
                elif t[-1] == '\x9b': # printf
                    f = to_ps(strings.pop())
                    n = f.count('%') - f.count('%%') * 2
                    x = tuple(map(to_ps, self.stack[-n:]))
                    del self.stack[-n:]
                    self.stack.append(to_gs(f % x))
                elif t[-1] == '\x9c': # regex match
                    pattern = strings.pop()
                    c, pattern = regex_count(pattern)
                    s = to_ps(self.stack.pop())
                    f = re.match if c else re.search
                    self.stack.append(1 if f(pattern, s) else 0)
                elif t[-1] == '\x9d': # regex sub
                    repl = strings.pop()
                    pattern = strings.pop()
                    c, pattern = regex_count(pattern)
                    s = to_ps(self.stack.pop())
                    m = re.sub(pattern, repl, s, count=c)
                    self.stack.append(to_gs(m))
                elif t[-1] == '\x9e': # regex find
                    pattern = strings.pop()
                    c, pattern = regex_count(pattern)
                    s = to_ps(self.stack.pop())
                    ms = re.findall(pattern, s)
                    if c > 0: ms = ms[0] if ms else []
                    self.stack.append(map(to_gs, ms))
                elif t[-1] == '\x9f': # regex split
                    pattern = strings.pop()
                    c, pattern = regex_count(pattern)
                    s = to_ps(self.stack.pop())
                    m = re.split(pattern, s, maxsplit=c)
                
            elif t[0] == '\x07': # single char string
                self.stack.append([ord(t[1])])

            # \x08 and \x09 are block syntax
            elif t == '\x0a': #= new-line
                self.stack.append([ord('\n')])
            elif t == '\x0b': #= empty-list
                self.stack.append([])
            elif t == '\x0c': #= empty-block
                self.stack.append(Block([]))
            elif t == '\x0d': #= space
                self.stack.append([ord(' ')])
            elif t == '\x0e': #= make-array
                size = self.stack.pop()
                self.stack[-size:] = [self.stack[-size:]]
            elif t == '\x0f': #= exit
                break

            elif 0x10 <= ord(t[0]) <= 0x1a: # push small number
                self.stack.append(ord(t[0]) - 0x10)
            elif t == '\x1b': self.stack.append(100)
            elif t == '\x1c': self.stack.append(1000)
            elif t == '\x1d': self.stack.append(16)
            elif t == '\x1e': self.stack.append(64)
            elif t == '\x1f': self.stack.append(256)

            elif t == '\x20': #= negate reverse eval
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(-x)
                elif is_list(x):
                    self.stack.append(x[::-1])
                elif is_block(x):
                    self.evaluate(x)
                else:
                    raise TypeError('negate / reverse')

            elif t == '\x21': #= bnot head
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(~x)
                elif is_list(x):
                    self.stack.append(x[0])
                else:
                    raise TypeError('bitwise not / head')

            elif t == '\x22': #= not tail
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(0 if x else 1)
                elif is_list(x):
                    self.stack.append(x[1:])
                else:
                    raise TypeError('not / tail')

            elif t == '\x23': #= abs init
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(abs(x))
                elif is_list(x):
                    self.stack.append(x[:-1])
                else:
                    raise TypeError('abs / init')

            elif t == '\x24': #= digits last
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(map(int, str(abs(x))))
                elif is_list(x):
                    self.stack.append(x[-1])
                else:
                    raise ValueError('digits / last')

            elif t == '\x25': #= random
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(random.randrange(x))
                elif is_list(x):
                    self.stack.append(random.choice(x))
                else:
                    raise TypeError('random')

            elif t == '\x26': #= dec left-uncons
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x - 1)
                elif is_list(x):
                    self.stack.append(x[1:])
                    self.stack.append(x[0])
                else:
                    raise TypeError('deincrement / left uncons')

            elif t == '\x27': #= inc right-uncons
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x + 1)
                elif is_list(x):
                    self.stack.append(x[:-1])
                    self.stack.append(x[-1])
                else:
                    raise TypeError('increment / right uncons')

            elif t == '\x28': #= sign min
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(cmp(x, 0))
                elif is_list(x):
                    self.stack.append(min(x))
                else:
                    raise TypeError('sign / min')

            elif t == '\x29': #= thousand max
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x * 1000)
                elif is_list(x):
                    self.stack.append(max(x))
                else:
                    raise TypeError('thousand / max')

            elif t == '\x2a': #= double lines
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x * 2)
                elif is_list(x):
                    self.stack.append(split(x, to_gs('\n')))
                else:
                    raise TypeError('double / line')

            elif t == '\x2b': #= half unlines
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x // 2)
                elif is_list(x):
                    x = [to_gs(show(i)) for i in x]
                    self.stack.append(join(x, to_gs('\n')))
                else:
                    raise TypeError('half / unlines')

            elif t == '\x2c': #= square words
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x * x)
                elif is_list(x):
                    self.stack.append(split(x, to_gs(' ')))
                else:
                    raise TypeError('square / words')

            elif t == '\x2d': #= sqrt unwords
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(int(math.sqrt(x)))
                elif is_list(x):
                    x = [to_gs(show(i)) for i in x]
                    self.stack.append(join(x, to_gs(' ')))
                else:
                    raise TypeError('sqrt / unwords')

            elif t == '\x2e': #= range length
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(range(x))
                elif is_list(x):
                    self.stack.append(len(x))
                else:
                    raise TypeError('range / length')

            elif t == '\x2f': #= range1 sort
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(range(1, x + 1))
                elif is_list(x):
                    self.stack.append(list(sorted(x)))
                elif is_block(x):
                    l = self.stack.pop()
                    def f(z):
                        self.stack.append(z)
                        self.evaluate(x)
                        return self.stack.pop(junk=False)
                    self.stack.append(list(sorted(l, key=f)))
                else:
                    raise TypeError('range1 / sort')

            elif t == '\x30': #= + add catenate
                y = self.stack.pop()
                x = self.stack.pop()
                if is_num(x) and is_num(y):
                    self.stack.append(x + y)
                elif is_list(x) and is_list(y):
                    self.stack.append(x + y)
                elif is_block(x) and is_block(y):
                    self.stack.append(Block(x.code + y.code))
                elif is_list(x) and not is_list(y):
                    self.stack.append(x + [y])
                elif not is_list(x) and is_list(y):
                    self.stack.append([x] + y)
                else:
                    raise TypeError('add / catenate')

            elif t == '\x31': #= - sub diff
                y = self.stack.pop()
                x = self.stack.pop()
                if is_num(x) and is_num(y):
                    self.stack.append(x - y)
                elif is_list(x) and is_list(y):
                    self.stack.append(set_diff(x, y))
                elif is_list(x) and not is_list(y):
                    self.stack.append(set_diff(x, [y]))
                elif not is_list(x) and is_list(y):
                    self.stack.append(set_diff(y, [x]))
                else:
                    raise TypeError('subtract / set diff')

            elif t == '\x32': #= * mul join times fold
                y = self.stack.pop()
                x = self.stack.pop()
                if is_num(x) and (is_block(y) or is_list(y)):
                    x, y = y, x
                if is_block(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x * y)
                elif is_list(x) and is_list(y):
                    self.stack.append(join(x, y))
                elif is_list(x) and is_num(y):
                    self.stack.append(x * y)
                elif is_block(x) and is_num(y):
                    for i in xrange(y):
                        self.evaluate(x)
                elif is_list(x) and is_block(y):
                    self.stack.append(x[0])
                    for i in x[1:]:
                        self.stack.append(i)
                        self.evaluate(y)
                else:
                    raise TypeError('multiply / join / times / fold')

            elif t == '\x33': #= / div chunks split each
                y = self.stack.pop()
                x = self.stack.pop()

                if not is_list(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x // y)
                elif is_list(x) and is_num(y):
                    self.stack.append(list(chunks(x, y)))
                elif is_list(x) and is_list(y):
                    self.stack.append(split(x, y))
                elif is_list(x) and is_block(y):
                    for i in x:
                        self.stack.append(i)
                        self.evaluate(y)
                else:
                    raise TypeError('divide / chunks / split / each')

            elif t == '\x34': #= % mod step clean-split map
                y = self.stack.pop()
                x = self.stack.pop()

                if not is_list(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x % y)
                elif is_list(x) and is_num(y):
                    self.stack.append(x[::y])
                elif is_list(x) and is_list(y):
                    self.stack.append(split(x, y, clean=True))
                elif is_list(x) and is_block(y):
                    self.eval_map(y, x)
                else:
                    raise TypeError('modulo / step / split\' / map')

            elif t == '\x35': #= & and get when filter
                y = self.stack.pop()
                x = self.stack.pop()

                if is_block(x) and is_num(y):
                    x, y = y, x
                if is_num(x) and is_list(y):
                    x, y = y, x
                if is_block(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x & y)
                elif is_list(x) and is_list(y):
                    self.stack.append(set_and(x, y))
                elif is_list(x) and is_num(y):
                    self.stack.append(x[y])
                elif is_num(x) and is_block(y):
                    if x: self.evaluate(y)
                elif is_list(x) and is_block(y):
                    self.eval_filter(y, x)
                else:
                    raise TypeError('and / get / when / filter')

            elif t == '\x36': #= | or unless
                y = self.stack.pop()
                x = self.stack.pop()

                if is_block(x) and is_num(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x | y)
                elif is_list(x) and is_list(y):
                    self.stack.append(set_or(x, y))
                elif is_num(x) and is_block(y):
                    if not x: self.evaluate(y)
                else:
                    raise TypeError('bor / unless')

            elif t == '\x37': #= ^ xor concatmap
                y = self.stack.pop()
                x = self.stack.pop()

                if is_block(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x ^ y)
                elif is_list(x) and is_list(y):
                    self.stack.append(set_xor(x, y))
                elif is_list(x) and is_block(y):
                    res = []
                    for i in x:
                        self.stack.append(i)
                        self.evaluate(y)
                        res.extend(self.stack.pop(junk=False))
                    self.stack.append(res)
                else:
                    raise TypeError('xor / concatmap')

            elif t == '\x38': #= smallest both
                y = self.stack.pop()
                if is_block(y):
                    x = self.stack.pop()
                    self.evaluate(y)
                    self.stack.append(x)
                    self.evaluate(y)
                else:
                    x = self.stack.pop()
                    self.stack.append(min(x, y))

            elif t == '\x39': #= biggest
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(max(x, y))

            elif t == '\x3a': #= clamp
                z = self.stack.pop()
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(min(max(x, y), z))

            elif t == '\x3c': #= gcd take
                y = self.stack.pop()
                x = self.stack.pop()

                if is_num(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(gcd(x, y))
                elif is_list(x) and is_num(y):
                    self.stack.append(x[:y])
                else:
                    raise TypeError('gcd / take')

            elif t == '\x3d': #= lcm drop
                y = self.stack.pop()
                x = self.stack.pop()

                if is_num(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(lcm(x, y))
                elif is_list(x) and is_num(y):
                    self.stack.append(x[y:])
                else:
                    raise TypeError('lcm / drop')

            elif t == '\x3e': #= pow index
                y = self.stack.pop()
                x = self.stack.pop()

                if is_num(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x ** y)
                elif is_list(x) and is_num(y):
                    self.stack.append(x.index(y) if y in x else -1)
                else:
                    raise TypeError('power / index')

            elif t == '\x3f': #= log member
                y = self.stack.pop()
                x = self.stack.pop()
                
                if is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(int(math.log(x, y)))
                elif is_list(x):
                    self.stack.append(1 if y in x else 0)
                else:
                    raise TypeError('log / member')

            elif t == '\x40': #= dup
                self.stack.append(self.stack[-1])
            elif t == '\x41': #= dup2
                self.stack.append(self.stack[-1])
                self.stack.append(self.stack[-1])
            elif t == '\x42': #= swap
                self.stack.append(self.stack.pop(-2))
            elif t == '\x43': #= rot
                self.stack.append(self.stack.pop(-3))
            elif t == '\x44': #= rrot
                self.stack.append(self.stack.pop(-3))
                self.stack.append(self.stack.pop(-3))
            elif t == '\x45': #= over
                self.stack.append(self.stack[-2])
            elif t == '\x46': #= nip
                self.stack.pop(-2)
            elif t == '\x47': #= tuck
                self.stack.insert(-2, self.stack[-1])
            elif t == '\x48': #= 2dup
                self.stack.append(self.stack[-2])
                self.stack.append(self.stack[-2])
            elif t == '\x49': #= pick
                n = self.stack.pop()
                self.stack.append(self.stack[-n])
            elif t == '\x4a': #= roll
                n = self.stack.pop()
                self.stack.append(self.stack.pop(-n))
            elif t == '\x4b': #= wrap-stack
                self.stack = [copy.deepcopy(self.stack)]
            elif t == '\x4c': #= leave-top
                del self.stack[:-1]
            elif t == '\x4d': #= itemize
                self.stack.append([self.stack.pop()])
            elif t == '\x4e': #= rrange
                x = self.stack.pop()
                self.stack.append(range(x)[::-1])
            elif t == '\x4f': #= crange
                y = self.stack.pop()
                x = self.stack.pop()
                if x > y: x, y = y, x
                self.stack.append(range(x, y))
            elif t == '\x52': #= show
                x = self.stack.pop()
                self.stack.append(to_gs(show(x)))
            elif t == '\x53': #= map-show
                x = self.stack.pop()
                self.stack.append(map(to_gs, map(show, x)))
            elif t == '\x54': #= show-lines
                x = self.stack.pop()
                self.stack.append(to_gs('\n'.join(map(show, x))))
            elif t == '\x55': #= show-words
                x = self.stack.pop()
                self.stack.append(to_gs(' '.join(map(show, x))))
            elif t in '\x56\x57': #= read-num, read-nums
                x = to_ps(self.stack.pop())
                nums = map(int, re.findall(r'-?\d+', x))
                self.stack.append(nums[0] if t == '\x56' else nums)
            elif t == '\x58': #= show-line
                x = self.stack.pop()
                self.stack.append(to_gs(show(x) + '\n'))
            elif t == '\x59': #= show-space
                x = self.stack.pop()
                self.stack.append(to_gs(show(x) + ' '))
            elif t == '\x5a': #= show-comma
                x = self.stack.pop()
                self.stack.append(to_gs(', '.join(map(show, x))))
            elif t == '\x5b': #= show-python
                x = self.stack.pop()
                self.stack.append(to_gs(', '.join(map(show, x)).join('[]')))
            elif t in '\x5c\x5d\x5e': #= ljust, center, rjust
                fill = ' ' 
                if is_num(self.stack[-2]):
                    fill = chr(self.stack.pop())
                width = self.stack.pop()
                s = self.stack.pop()
                if t == '\x5c': g = show(s).ljust(width, fill)
                if t == '\x5d': g = show(s).center(width, fill)
                if t == '\x5e': g = show(s).rjust(width, fill)
                self.stack.append(to_gs(g))
            elif t == '\x5f': #= inspect
                self.stack.append(to_gs(repr(self.stack.pop())))
            elif t == '\x60': #= logical-and
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(x and y)
            elif t == '\x61': #= logical-or
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(x or y)
            elif t == '\x62': #= divides left-cons
                y = self.stack.pop()
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(0 if x % y else 1)
                elif is_list(x):
                    self.stack.append([y] + x)
                else:
                    raise TypeError('divides / left-cons')
            elif t == '\x63': #= divmod group
                y = self.stack.pop()
                if is_num(y):
                    x = self.stack.pop()
                    self.stack.append(x // y)
                    self.stack.append(x % y)
                elif is_list(y):
                    gb = [list(g) for k, g in it.groupby(y)]
                    self.stack.append(list(gb))
                else:
                    raise TypeError('divmod / group')
            elif t == '\x64': #= sum even
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(1 if x % 2 == 0 else 0)
                elif is_list(x):
                    self.stack.append(sum(x))
            elif t == '\x65': #= product odd
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(1 if x % 2 == 1 else 0)
                elif is_list(x):
                    self.stack.append(product(x))
            elif t == '\x66': #= fizzbuzz
                fizzbuzz = []
                for i in range(1, 101):
                    s = ("Fizz" if i % 3 == 0 else "") + \
                        ("Buzz" if i % 5 == 0 else "")
                    fizzbuzz.append(s or str(i))
                self.stack.append(to_gs('\n'.join(fizzbuzz)))
            elif t == '\x67': #= popcnt right-cons
                x = self.stack.pop()
                if is_num(x):
                    x = abs(x)
                    p = 0
                    while x:
                        p += (x & 1)
                        x >>= 1
                    self.stack.append(p)
                elif is_list(x):
                    y = self.stack.pop()
                    self.stack.append(x + [y])
            elif t == '\x68': #= hello
                x = 0
                if len(self.stack) >= 1 and is_num(self.stack[-1]):
                    x = self.stack.pop()
                    x = (range(0, 11) + [100, 1000, 16, 64, 256]).index(x)
                s1 = 'h' if x & 1 else 'H'
                s2 = 'W' if x & 2 else 'w'
                s3 = ['!', '', '.', '...'][((x & 4) >> 2) | ((x & 16) >> 3)]
                s4 = '' if x & 8 else ','
                f = '%sello%s %sorld%s' % (s1, s4, s2, s3)
                self.stack.append(to_gs(f))
            elif t in '\x69\x6a': #= base, binary
                b = 2 if t == '\x6a' else self.stack.pop()
                x = self.stack.pop()
                if is_num(x):
                    x = abs(x)
                    res = []
                    while x:
                        res.append(x % b)
                        x //= b
                    self.stack.append(res[::-1])
                elif is_list(x):
                    res = 0
                    for i in x[::-1]:
                        res = res * b + i
                    self.stack.append(res)
                else:
                    raise TypeError('base / binary')
            elif t == '\x6b': #= is-prime
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(1 if is_prime(x) else 0)
                elif is_list(x):
                    self.stack.append(filter(is_prime, x))
                else:
                    raise TypeError('is-prime')
            elif t == '\x6c': #= primes
                op = self.stack.pop()
                x = self.stack.pop()
                if op == 0:   self.stack.append(n_primes(x))
                elif op == 1: self.stack.append(primes_below(x))
                elif op == 2: self.stack.append(next_prime(x))
                elif op == 3: self.stack.append(totient(x))
                elif op == 4: self.stack.append(factor(x, exps=False))
                elif op == 5: self.stack.append(factor(x, exps=True))
            elif t == '\x6d': #= scan
                f = self.stack.pop()
                def call_f(x, y):
                    self.stack.append(x)
                    self.stack.append(y)
                    self.evaluate(f)
                    return self.stack.pop()
                xs = self.stack.pop()
                res = [xs.pop(0)]
                while xs:
                    res.append(call_f(res[-1], xs.pop(0)))
                self.stack.append(res)
            elif t in '\x70\x71\x72\x73\x74\x75': #= lt <, eq =, gt >, ge >=, ne !=, le <=
                y = self.stack.pop()
                x = self.stack.pop()
                ops = {
                    '\x70': operator.lt,
                    '\x71': operator.eq,
                    '\x72': operator.gt,
                    '\x73': operator.ge,
                    '\x74': operator.ne,
                    '\x75': operator.le,
                }
                self.stack.append(1 if ops[t](x, y) else 0)
            elif t == '\x76': #= cmp
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(cmp(x, y))
            elif t == '\x77': #= is-sorted
                x = self.stack.pop()
                if is_list(x):
                    self.stack.append(1 if x == list(sorted(x)) else 0)
                elif is_block(x):
                    l = self.stack.pop()
                    def f(z):
                        self.stack.append(z)
                        self.evaluate(x)
                        return self.stack.pop()
                    sorted_l = list(sorted(l, key=f))
                    self.stack.append(1 if l == sorted_l else 0)
                else:
                    raise TypeError('sorted')
            elif t == '\x78': #= shift-left inits
                y = self.stack.pop()
                if is_list(y):
                    inits = []
                    for i in xrange(len(y) + 1):
                        inits.append(y[:i])
                    self.stack.append(inits)
                else:
                    x = self.stack.pop()
                    self.stack.append(x << y)
            elif t == '\x79': #= shift-right tails
                y = self.stack.pop()
                if is_list(y):
                    tails = []
                    for i in xrange(len(y) + 1):
                        tails.append(y[len(y)-i:])
                    self.stack.append(tails)
                else:
                    x = self.stack.pop()
                    self.stack.append(x >> y)
            elif t == '\x7a': #= digit-left enumerate
                y = self.stack.pop()
                if is_list(y):
                    self.stack.append(list(map(list, enumerate(y))))
                else:
                    x = self.stack.pop()
                    self.stack.append(x * (10 ** y))
            elif t == '\x7b': #= digit-right
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(x // (10 ** y))
            elif t == '\x7c': #= power-of-2
                self.stack.append(2 ** self.stack.pop())
            elif t == '\x7d': #= power-of-10
                self.stack.append(10 ** self.stack.pop())
            elif t == '\x7e': #= sub-power-of-2
                self.stack.append(2 ** self.stack.pop() - 1)
            elif t == '\x7f': #= sub-power-of-10
                self.stack.append(10 ** self.stack.pop() - 1)

            elif t == '\x80': #= pair
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append([x, y])
            elif t == '\x81': #= copies
                n = self.stack.pop()
                x = self.stack.pop()
                self.stack.append([x for _ in xrange(n)])
            elif t == '\x82': #= take-end
                y = self.stack.pop()
                x = self.stack.pop()
                if is_num(x) and is_list(y):
                    x, y = y, x
                self.stack.append(x[-y:])
            elif t == '\x83': #= cartesian-product
                y = self.stack.pop()
                x = self.stack.pop()
                p = it.product(x, y)
                self.stack.append(list(map(list, p)))
            elif t == '\x84': #= uppercase-alphabet
                self.stack.append(range(ord('A'), ord('Z') + 1))
            elif t == '\x85': #= lowercase-alphabet
                self.stack.append(range(ord('a'), ord('z') + 1))
            elif t == '\x86': #= ascii-digits
                self.stack.append(range(ord('0'), ord('9') + 1))
            elif t == '\x87': #= printable-ascii
                self.stack.append(range(32, 127))
            elif t in '\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f': #= is-alnum, is-alpha, is-digit, is-lower, is-space, is-upper, is-printable, is-hexdigit
                m = [str.isalnum, str.isalpha, str.isdigit,
                     str.islower, str.isspace, str.isupper,
                     lambda x: all(32 <= ord(c) <= 126 for c in x),
                     lambda x: x in '0123456789abcdefABCDEF']
                p = m[ord(t) - 0x88]
                x = to_ps(self.stack.pop())
                self.stack.append(1 if p(x) else 0)
            elif t == '\x90': #= dump
                for i in self.stack.pop():
                    self.stack.append(i)
            elif t == '\x91': #= compress
                ns = self.stack.pop()
                xs = self.stack.pop()
                new = []
                for n, x in zip(ns, xs):
                    new += [x for _ in xrange(n)]
                self.stack.append(new)
            elif t == '\x92': #= select
                xs = self.stack.pop()
                iis = self.stack.pop()
                new = []
                for i in iis:
                    new.append(xs[i])
                self.stack.append(new)
            elif t == '\x93': #= permutations
                xs = self.stack.pop()
                if is_num(xs):
                    n = xs
                    xs = self.stack.pop()
                else:
                    n = None
                ps = list(map(list, it.permutations(xs, n)))
                self.stack.append(ps)
            elif t == '\x94': #= fold-product
                xss = self.stack.pop()
                ys = list(map(list, it.product(*xss)))
                self.stack.append(ys)
            elif t == '\x95': #= repeat-product
                n = self.stack.pop()
                xs = self.stack.pop()
                ys = list(map(list, it.product(xs, repeat=n)))
                self.stack.append(ys)
            elif t == '\x96': #= combinations
                n = self.stack.pop()
                xs = self.stack.pop()
                ys = list(map(list, it.combinations(xs, n)))
                self.stack.append(ys)
            elif t == '\x97': #= combinations-with-replacement
                n = self.stack.pop()
                xs = self.stack.pop()
                ys = list(map(list, it.combinations_with_replacement(xs, n)))
                self.stack.append(ys)
            elif t == '\x98': #= pairwise
                xs = self.stack.pop()
                ys = map(list, zip(xs, xs[1:]))
                self.stack.append(ys)
            elif t == '\x99': #= flatten
                def flatten(xs):
                    acc = []
                    for x in xs:
                        if is_list(x):
                            acc += flatten(x)
                        else:
                            acc.append(x)
                    return acc
                xs = self.stack.pop()
                self.stack.append(flatten(xs))
            elif t == '\x9a': #= transpose
                xs = self.stack.pop()
                self.stack.append(map(list, zip(*xs)))
            elif '\xa0' <= t <= '\xaf': # junk (recently popped items)
                self.stack.append(self.stack.junk[-1 - (ord(t) & 15)])
            elif t == '\xb0': #= zip
                xs = self.stack.pop()
                ys = self.stack.pop()
                self.stack.append(map(list, zip(xs, ys)))
            elif t == '\xb1': #= zipwith
                f = self.stack.pop()
                xs = self.stack.pop()
                ys = self.stack.pop()
                l0 = len(self.stack)
                for x, y in zip(xs, ys):
                    self.stack.append(x)
                    self.stack.append(y)
                    self.evaluate(f)
                self.stack[l0:] = [self.stack[l0:]]
            elif t == '\xb2': #= counter
                self.stack.append(self.counter)
                self.counter += 1
            elif '\xc8' <= t <= '\xcb': # save
                self.regs[ord(t) & 3] = self.stack[-1]
            elif '\xcc' <= t <= '\xcf': # put
                self.regs[ord(t) & 3] = self.stack.pop()
            elif '\xd0' <= t <= '\xd3': # get
                self.stack.append(self.regs[ord(t) & 3])
            elif '\xd4' <= t <= '\xd7': # nip
                self.regs[ord(t) & 3] = self.stack.pop(-2)
            elif '\xd8' <= t <= '\xdb': # tuck
                self.stack.insert(-1, self.regs[ord(t) & 3])
            elif '\xdc' <= t <= '\xdf': # show
                self.stack.append(show(self.regs[ord(t) & 3]))
            else:
                raise ValueError('invalid token %r' % t) 

    def eval_map(self, f, x):
        l0 = len(self.stack)
        for i in x:
            self.stack.append(i)
            self.evaluate(f)
        self.stack[l0:] = [self.stack[l0:]]

    def eval_filter(self, f, x):
        l0 = len(self.stack)
        for i in x:
            self.stack.append(i)
            self.evaluate(f)
            if self.stack.pop():
                self.stack.append(i)
        self.stack[l0:] = [self.stack[l0:]]

if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print >> sys.stderr, 'usage: python %s [-d] <code file>' % sys.argv[0]
        sys.exit(1)

    if sys.argv[1] == '-d':
        DEBUG = True
        sys.argv.pop(1)

    code = open(sys.argv[1], 'rb').read()
    stdin = '' if sys.stdin.isatty() else sys.stdin.read()
    GS2(code, stdin).run()
