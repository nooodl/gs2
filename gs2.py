# gs2 interpreter (version 0.1)
# (c) nooodl 2014

import inspect
import itertools as it
import math
import random
import re
import string
import struct
import sys
import traceback

from collections import namedtuple
from fractions import gcd

Block = namedtuple('Block', 'code')

DEBUG = True

def log(x):
    if not DEBUG: return
    line, name = inspect.stack()[1][2:4]
    sys.stderr.write('\x1b[36m%s:%d\x1b[34m: %r\x1b[0m\n' % (name, line, x))

def tokenize(prog):
    # string hack
    if re.match('^[^\x04]*[\x05\x06]', prog):
        prog = '\x04' + prog

    token_re = [
        '\x01.',                      # unsigned byte
        '\x02..',                     # signed short
        '\x03....',                   # signed long
        '\x04[^\x05\x06]*[\x05\x06]', # string (array)
        '\x07.',                      # 1 char string
        '.',                          # regular token
    ]

    tokens = re.findall('|'.join(token_re), prog, re.DOTALL)

    final = []
    blocks = [Block([])]
    i = 0 
    while i < len(tokens):
        t = tokens[i]
        log(tokens[i:])
        if t == '\x08': # open block
            blocks.append(Block([]))
            final.append('')
        elif t == '\x09': # close block
            blocks[-2].code.append(blocks.pop() + final.pop())
        elif t == '\x4d': # open 1-token block
            blocks[-1].code.append(Block([tokens[i + 1]]))
            i += 1
        elif t == '\x4e': # open 1-token map
            blocks[-1].code.append(Block([tokens[i + 1]]))
            blocks[-1].code.append('\x34')
            i += 1
        elif t == '\x4f': # open 2-token map
            blocks[-1].code.append(Block([tokens[i + 1], tokens[i + 2]]))
            blocks[-1].code.append('\x34')
            i += 2
        elif t == '\x5c': # open 1-token filter
            blocks[-1].code.append(Block([tokens[i + 1]]))
            blocks[-1].code.append('\x35')
            i += 1
        elif t == '\x5d': # open 2-token filter
            blocks[-1].code.append(Block([tokens[i + 1], tokens[i + 2]]))
            blocks[-1].code.append('\x35')
            i += 2
        elif t == '\x5e': # open rest-of-program map 
            blocks.append(Block([]))
            final.append('\x34')
        elif t == '\x5f': # open rest-of-program filter 
            blocks.append(Block([]))
            final.append('\x35')
        else:
            blocks[-1].code.append(t)
        i += 1

    log(blocks)
    log(final)
    while final:
        blocks[-2].code.append(blocks.pop())
        blocks[-1].code.append(final.pop())
    log(blocks)

    assert len(blocks) == 1
    blocks[0].code.extend(final)

    return blocks[0]

is_num   = lambda v: isinstance(v, (int, long))
is_list  = lambda v: isinstance(v, list)
is_block = lambda v: isinstance(v, Block)

def to_gs(ps): return map(ord, ps)

def to_ps(gs):
    if is_list(gs): return ''.join(map(chr, gs))
    else: return gs

def show(value, nest=False):
    if is_list(value):
        return ''.join(show(x, nest=True) for x in value)
    elif nest and is_num(value):
        return chr(value)
    else:
        return str(value)

def lcm(a, b):
    if (a, b) == (0, 0): return 0
    return abs(a * b) // gcd(a, b)

def split(a, b, clean=False):
    res = [[]]
    lb = len(b)

    i = 0
    while i <= len(a) - lb + 1:
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
        res.extend(a)
    return res

def group(a, n):
    i = 0
    res = []
    while i < len(a):
        res.append(a[i:i+n])
        i += n
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

# prime number stuff
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

class GS2(object):
    def __init__(self, code, stdin=''):
        self.code = code
        self.stdin = to_gs(stdin)
        self.stack = [self.stdin]
        self.regs = {
            0: stdin, # A
            1: len(stdin), # B
            2: to_gs(code), # C
            3: random.randint(0, 2), # D
        }

    def run(self):
        try:
            self.evaluate(tokenize(self.code))
            print show(self.stack)
        except Exception:
            # If the code fails, print something meaningful to stderr,
            # but quine on stdout: this allows GS2 to good at simple
            # "print this string" programs -- just upload a plaintext
            # file, it's unlikely to be valid GS2 code.
            traceback.print_exc()
            if not DEBUG: print self.code

    def evaluate(self, block):
        for t in block.code:
            if is_block(t):
                self.stack.append(t)
            elif t[0] == '\x00': # nop
                pass
            elif t[0] == '\x01': # push unsigned byte
                self.stack.append(struct.unpack('<B', t[1:])[0])
            elif t[0] == '\x02': # push signed short
                self.stack.append(struct.unpack('<h', t[1:])[0])
            elif t[0] == '\x03': # push signed long
                self.stack.append(struct.unpack('<l', t[1:])[0])

            elif t[0] == '\x04': # string
                assert len(t) >= 2
                assert t[-1] in '\x05\x06'
                strings = t[1:-1].split('\x07')
                strings = map(to_gs, strings)
                if t[-1] == '\x06': self.stack.append(strings)
                else:               self.stack.extend(strings)

            elif t[0] == '\x07': # single char string
                self.stack.append([ord(t[1])])

            # \x08 and \x09 are block syntax
            elif t == '\x0a': # push "\n"
                self.stack.append([ord('\n')])
            elif t == '\x0b': # push []
                self.stack.append([])
            elif t == '\x0c': # push {}
                self.stack.append(Block([]))
            elif t == '\x0d': # block to array
                # Simulate evaluating code on copy of stack,
                # then push extra elements onto real stack
                block = self.stack.pop()
                env = GS2(self.code)
                env.stack = self.stack[:]
                env.evaluate(block)
                new = env.stack[len(self.stack):]
                self.stack.append(new)
            elif t == '\x0e': # array of top n elements
                size = self.stack.pop()
                self.stack[-size:] = [self.stack[-size:]]
            elif t == '\x0f': # stop program
                break

            elif 0x10 <= ord(t[0]) <= 0x1a: # push small number
                self.stack.append(ord(t[0]) - 0x10)
            elif t == '\x1b': self.stack.append(100)
            elif t == '\x1c': self.stack.append(1000)
            elif t == '\x1d': self.stack.append(16)
            elif t == '\x1e': self.stack.append(64)
            elif t == '\x1f': self.stack.append(256)

            elif t == '\x20': # negate / reverse
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(-x)
                elif is_list(x):
                    self.stack.append(x[::-1])
                else:
                    raise TypeError('negate / reverse')

            elif t == '\x21': # bitwise not / head
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(~x)
                elif is_list(x):
                    self.stack.append(x[0])
                else:
                    raise TypeError('bitwise not / head')

            elif t == '\x22': # not / tail
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(0 if x else 1)
                elif is_list(x):
                    self.stack.append(x[1:])
                else:
                    raise TypeError('not / tail')

            elif t == '\x23': # abs / init
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(abs(x))
                elif is_list(x):
                    self.stack.append(x[:-1])
                else:
                    raise TypeError('abs / init')

            elif t == '\x24': # digits / last
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(map(int, str(abs(x))))
                elif is_list(x):
                    self.stack.append(x[-1])
                else:
                    raise ValueError('digits / last')

            elif t == '\x25': # random
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(random.randrange(x))
                elif is_list(x):
                    self.stack.append(random.choice(x))
                else:
                    raise TypeError('random')

            elif t == '\x26': # deincrement / left uncons
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x - 1)
                elif is_list(x):
                    self.stack.append(x[1:])
                    self.stack.append(x[0])
                else:
                    raise TypeError('deincrement / left uncons')

            elif t == '\x27': # increment / right uncons
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x + 1)
                elif is_list(x):
                    self.stack.append(x[:-1])
                    self.stack.append(x[-1])
                else:
                    raise TypeError('increment / right uncons')

            elif t == '\x28': # sign / min
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(cmp(x, 0))
                elif is_list(x):
                    self.stack.append(min(x))
                else:
                    raise TypeError('sign / min')

            elif t == '\x29': # thousand / max
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x * 1000)
                elif is_list(x):
                    self.stack.append(max(x))
                else:
                    raise TypeError('thousand / max')

            elif t == '\x2a': # double / lines
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x * 2)
                elif is_list(x):
                    self.stack.append(split(x, ord('\n')))
                else:
                    raise TypeError('double / line')

            elif t == '\x2b': # half / unlines
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x // 2)
                elif is_list(x):
                    self.stack.append(join(x, ord('\n')))
                else:
                    raise TypeError('half / unlines')

            elif t == '\x2c': # square / words
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(x * x)
                elif is_list(x):
                    self.stack.append(split(x, ord(' ')))
                else:
                    raise TypeError('square / words')

            elif t == '\x2d': # sqrt / unwords
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(int(math.sqrt(x)))
                elif is_list(x):
                    self.stack.append(join(x, ord('\n')))
                else:
                    raise TypeError('sqrt / unwords')

            elif t == '\x2e': # range (0..n-1) / length
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(range(x))
                elif is_list(x):
                    self.stack.append(len(x))
                else:
                    raise TypeError('range / length')

            elif t == '\x2f': # range' (1..n) / sort
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
                        return self.stack.pop()
                    self.stack.append(list(sorted(l, key=f)))
                else:
                    raise TypeError('irange / sort')

            elif t == '\x30': # add / catenate
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

            elif t == '\x31': # subtract / set diff
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

            elif t == '\x32': # multiply / join / times / fold
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

            elif t == '\x33': # divide / group / split / each
                y = self.stack.pop()
                x = self.stack.pop()

                if not is_list(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x // y)
                elif is_list(x) and is_num(y):
                    self.stack.append(group(x, y))
                elif is_list(x) and is_list(y):
                    self.stack.append(split(x, y))
                elif is_list(x) and is_block(y):
                    for i in x:
                        self.stack.append(i)
                        self.evaluate(y)
                else:
                    raise TypeError('divide / group / split / each')

            elif t == '\x34': # modulo / step / split' / map
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

            elif t == '\x35': # and / get / when / filter
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
                elif is_num(x) and is_block(y) and x:
                    self.evaluate(y)
                if is_list(x) and is_block(y):
                    self.eval_filter(y, x)
                else:
                    raise TypeError('and / get / when / filter')

            elif t == '\x36': # or / unless
                y = self.stack.pop()
                x = self.stack.pop()

                if is_block(x) and is_num(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x | y)
                elif is_list(x) and is_list(y):
                    self.stack.append(set_or(x, y))
                elif is_num(x) and is_block(y) and not x:
                    self.evaluate(y)
                else:
                    raise TypeError('bor / unless')

            elif t == '\x37': # xor / concatmap
                y = self.stack.pop()
                x = self.stack.pop()

                if is_block(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(x ^ y)
                elif is_list(x) and is_list(y):
                    self.stack.append(set_xor(x, y))
                elif is_list(x) and is_block(y):
                    self.res = []
                    for i in x:
                        self.stack.append(i)
                        self.evaluate(y)
                        self.res.extend(self.stack.pop())
                    self.stack.append(res)
                else:
                    raise TypeError('xor / concatmap')

            elif t == '\x38': # smallest
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(min(x, y))

            elif t == '\x39': # biggest
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(min(x, y))

            elif t == '\x3a': # clamp
                z = self.stack.pop()
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(min(max(x, y), z))

            elif t == '\x3c': # gcd / take
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

            elif t == '\x3d': # lcm / drop
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

            elif t == '\x3e': # power / index
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

            elif t == '\x3f': # log / member
                y = self.stack.pop()
                x = self.stack.pop()
                
                if is_num(x) and is_list(y):
                    x, y = y, x

                if is_num(x) and is_num(y):
                    self.stack.append(int(math.log(x, y)))
                elif is_list(x) and is_num(y):
                    self.stack.append(1 if y in x else 0)
                else:
                    raise TypeError('log / member')

            elif t == '\x40': # dup
                self.stack.append(self.stack[-1])
            elif t == '\x41': # dup2
                self.stack.append(self.stack[-1])
                self.stack.append(self.stack[-1])
            elif t == '\x42': # swap
                self.stack.append(self.stack.pop(-2))
            elif t == '\x43': # rot
                self.stack.append(self.stack.pop(-3))
            elif t == '\x44': # rrot
                self.stack.append(self.stack.pop(-3))
                self.stack.append(self.stack.pop(-3))
            elif t == '\x45': # over
                self.stack.append(self.stack[-2])
            elif t == '\x46': # nip
                self.stack.pop(-2)
            elif t == '\x47': # tuck
                self.stack.insert(-2, self.stack[-1])
            elif t == '\x48': # 2dup
                self.stack.append(self.stack[-2])
                self.stack.append(self.stack[-2])
            elif t == '\x49': # pick
                n = self.stack.pop()
                self.stack.append(self.stack[-n])
            elif t == '\x4a': # roll
                n = self.stack.pop()
                self.stack.append(self.stack.pop(-n))
            elif t == '\x4b': # get stack
                self.stack.append(self.stack)
            elif t == '\x4c': # leave top only
                self.stack = [self.stack[-1]]

            # 4d 4e 4f are special
            elif t in '\x50\x51': # sprintf, sprintf list
                y = self.stack.pop()
                x = self.stack.pop()

                if t == '\x50': # single argument
                    if is_num(x) and is_list(y):
                        x, y = y, x
                    y = [y]
                
                y = tuple(map(to_ps, y))
                self.stack.append(to_ps(x) % y)

            elif t == '\x52': # show
                x = self.stack.pop()
                self.stack.append(to_gs(show(x)))
            elif t == '\x53': # map show
                x = self.stack.pop()
                self.stack.append(map(to_gs, map(show, x)))
            elif t == '\x54': # show lines
                x = self.stack.pop()
                self.stack.append(to_gs('\n'.join(map(show, x))))
            elif t == '\x55': # show words
                x = self.stack.pop()
                self.stack.append(to_gs(' '.join(map(show, x))))
            elif t in '\x56\x57': # read number/numbers from string
                x = to_ps(self.stack.pop())
                nums = map(int, re.findall(r'-?\d+', x))
                self.stack.append(nums[0] if t == '\x56' else nums)
                # TODO test this
            elif t == '\x58': # show with newline
                x = self.stack.pop()
                self.stack.append(to_gs(show(x) + '\n'))
            elif t == '\x59': # show with space
                x = self.stack.pop()
                self.stack.append(to_gs(show(x) + ' '))
            elif t == '\x5a': # show joined with ', '
                x = self.stack.pop()
                self.stack.append(to_gs(', '.join(map(show, x))))
            elif t == '\x5b': # show 'python style'
                x = self.stack.pop()
                self.stack.append(to_gs(', '.join(map(show, x)).join('[]')))

            # 5c 5d 5e 5f are special
            elif t == '\x60': # logical and
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(x and y)
            elif t == '\x61': # logical or
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(x or y)
            elif t == '\x62': # divides
                y = self.stack.pop()
                x = self.stack.pop()
                self.stack.append(0 if x % y else 1)
            elif t == '\x63': # divmod
                y = self.stack.pop()
                x = self.stack.pop()
                if is_num(y):
                    self.stack.append(x // y)
                    self.stack.append(x % y)
                # TODO: list op?
            elif t == '\x64': # sum / even
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(1 if x % 2 == 0 else 0)
                elif is_list(x):
                    self.stack.append(sum(x))
            elif t == '\x65': # product / odd
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(1 if x % 2 == 1 else 0)
                elif is_list(x):
                    self.stack.append(product(x))
            elif t == '\x66': # fizzbuzz
                fizzbuzz = []
                for i in range(1, 101):
                    s = ("Fizz" if i % 3 == 0 else "") + \
                        ("Buzz" if i % 5 == 0 else "")
                    fizzbuzz.append(s or str(i))
                self.stack.append(to_gs('\n'.join(fizzbuzz)))
            elif t == '\x67': # popcnt
                x = self.stack.pop()
                if is_num(x):
                    x = abs(x)
                    p = 0
                    while x:
                        p += (x & 1)
                        x >>= 1
                    self.stack.append(p)
            elif t in '\x68\x69': # base / binary
                b = 2 if t == '\x69' else self.stack.pop()
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
            elif t == '\x6a': # is-prime
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(int(is_prime(x)))
            elif t == '\x6b': # nth-prime
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(nth_prime(x))
            elif t == '\x6c': # n-primes
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(n_primes(x))
            elif t == '\x6d': # primes-below
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(primes_below(x))
            elif t == '\x6e': # next-prime
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(next_prime(x))
            elif t == '\x6f': # totient
                x = self.stack.pop()
                if is_num(x):
                    self.stack.append(totient(x))


            elif '\xf0' <= t <= '\xf3': # save
                self.regs[ord(t) & 3] = self.stack[-1]
            elif '\xf4' <= t <= '\xf7': # put
                self.regs[ord(t) & 3] = self.stack.pop()
            elif '\xf8' <= t <= '\xfb': # get
                self.stack.append(self.regs[ord(t) & 3])
            elif '\xfc' <= t <= '\xff': # exchange
                temp = self.regs[ord(t) & 3]
                self.regs[ord(t) & 3] = self.stack.pop()
                self.stack.append(temp)

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

if len(sys.argv) <= 1:
    print >> sys.stderr, 'usage: python %s [-d] <code file>' % sys.argv[0]
    sys.exit(1)

if sys.argv[1] == '-d':
    DEBUG = True
    sys.argv.pop(1)

code = open(sys.argv[1], 'rb').read()
stdin = '' if sys.stdin.isatty() else sys.stdin.read()
GS2(code, stdin).run()
