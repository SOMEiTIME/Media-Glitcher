#!/usr/bin/env python3

# Byte level glitch operations. Each one changes a bytearray in place, keeps
# its length, and takes its randomness from the rng it is given. The engine
# passes only the target's bytes, so the header is never touched.

#
# Once every `every` bytes, swaps a chunk of `size` bytes with a chunk
# one to four chunks before it
#
def byte_swap(data, rng, size, every):
    last = len(data) - size
    for window in range(size, last + 1, every):
        a = min(window + rng.randrange(every), last)
        b = a - size * rng.randint(1, 4)
        if b >= 0:
            data[a:a + size], data[b:b + size] = data[b:b + size], data[a:a + size]

#
# Once every `every` bytes, replaces one byte with a random value
#
def byte_corrupt(data, rng, every):
    for window in range(0, len(data), every):
        place = min(window + rng.randrange(every), len(data) - 1)
        data[place] = rng.randrange(256)

#
# Flips a random `rate` fraction of the bits, e.g. 0.0001 flips one bit in
# every ten thousand
#
def bitflip(data, rng, rate):
    bits = len(data) * 8
    for _ in range(round(bits * rate)):
        bit = rng.randrange(bits)
        data[bit // 8] ^= 1 << (bit % 8)

#
# Once every `every` bytes, copies a chunk of `size` bytes over the chunk
# right after it, which smears or stutters the data
#
def repeat(data, rng, size, every):
    last = len(data) - 2 * size
    for window in range(0, last + 1, every):
        a = min(window + rng.randrange(every), last)
        data[a + size:a + 2 * size] = data[a:a + size]
