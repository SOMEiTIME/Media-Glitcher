#!/usr/bin/env python3

# Byte level glitch operations. Each one changes a bytearray in place, never
# touches the first `start` bytes (the protected header), keeps the length the
# same, and takes its randomness from the rng it is given.

#
# Once every `every` bytes, swaps a chunk of `size` bytes with a chunk
# one to four chunks before it
#
def byte_swap(data, start, rng, size, every):
    last = len(data) - size
    for window in range(start + size, last + 1, every):
        a = min(window + rng.randrange(every), last)
        b = a - size * rng.randint(1, 4)
        if b >= start:
            data[a:a + size], data[b:b + size] = data[b:b + size], data[a:a + size]

#
# Once every `every` bytes, replaces one byte with a random value
#
def byte_corrupt(data, start, rng, every):
    for window in range(start, len(data), every):
        place = min(window + rng.randrange(every), len(data) - 1)
        data[place] = rng.randrange(256)

#
# Flips a random `rate` fraction of the bits after the header,
# e.g. 0.0001 flips one bit in every ten thousand
#
def bitflip(data, start, rng, rate):
    bits = (len(data) - start) * 8
    for _ in range(round(bits * rate)):
        bit = rng.randrange(bits)
        data[start + bit // 8] ^= 1 << (bit % 8)

#
# Once every `every` bytes, copies a chunk of `size` bytes over the chunk
# right after it, which smears or stutters the data
#
def repeat(data, start, rng, size, every):
    last = len(data) - 2 * size
    for window in range(start, last + 1, every):
        a = min(window + rng.randrange(every), last)
        data[a + size:a + 2 * size] = data[a:a + size]
