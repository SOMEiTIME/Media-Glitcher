#!/usr/bin/env python3

import random

#
# Line mode: takes a file's lines, glitches them, and returns the new file as
# text. The quirks below are how this mode has always worked, so they're kept
#
class media:
    #
    # lines are the file's lines; the first header_length are left alone.
    # rng is the random module or a seeded random.Random
    #
    def __init__(self, lines, header_length, rng=random):
        lines = list(lines)
        self.__header = lines[:header_length]
        self.__body = lines[header_length:]
        self.__rng = rng

    #
    # Overwrites the line at place1 with the line at place2 followed by part of
    # the old line, to keep its length. If the result's length differs (e.g.
    # place2's line is longer), the line is left alone
    #
    def __swap_at(self, place1, place2):
        line1, line2 = self.__body[place1], self.__body[place2]
        short, long = (line1, line2) if len(line1) < len(line2) else (line2, line1)
        new_line = short + long[max(0, len(short) - 4):]
        new_line = new_line[:len(new_line) - 4]
        if len(new_line) == len(line1):
            self.__body[place1] = new_line

    #
    # Once every interval lines, swaps a line with one 1 to 3 + flavour % 10
    # lines before it. After the first swap the gap is interval - flavour + 1,
    # so a flavour above interval swaps only once
    #
    def glitch_random_swap(self, interval, flavour):
        counter = 0
        for num in range(len(self.__body)):
            if counter == interval:
                self.__swap_at(num, num - (1 + self.__rng.randint(0, 2 + flavour % 10)))
                counter = flavour
            else:
                counter += 1

    #
    # Once every interval + 1 lines, swaps that line and the ones before it,
    # corruption lines in all, each with one 1 to 6 + corruption lines back.
    # corruption starts at 1 and grows each time. flavour is unused
    #
    def glitch_corrupt(self, interval, flavour):
        corruption = 1
        counter = 0
        for num in range(len(self.__body)):
            if counter == interval:
                for i in range(corruption):
                    self.__swap_at(num - i, num - (i + 1 + self.__rng.randint(0, 5 + corruption)))
                counter = 0
                corruption += 1
            else:
                counter += 1

    #
    # Returns the glitched file as text
    #
    def text(self):
        return "".join(self.__header + self.__body)
