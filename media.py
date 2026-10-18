#!/usr/bin/env python3

import random

#
# This class takes the lines of a file,
# then perform glitching operations as desired,
# and then can return the new file as text
#
class media:
    #
    # Initializer method
    # Requires the file's lines, the length of the header of the format,
    # and a random number generator (the random module, or a seeded random.Random)
    #
    def __init__(self, lines, header_length, rng=random):
        self.__header = []
        self.__body = []
        self.__rng = rng
        for line in lines:
            self.__body.append(line)
        for num in range(header_length):
            self.__header.append(self.__body.pop(0))
        return
    #
    # Helper method for the glitch methods
    # Formats lineA to have the length of lineB
    #
    def __generate_fitting_line(self, lineA, lineB):
        new_line = ""
        for char in self.__body[lineA]:
            new_line = new_line + char 
        count = 0
        for char in self.__body[lineB]:
            if count >= len(self.__body[lineA]) - 4:
                new_line = new_line + char
            count = count +1
        return new_line

    #
    # Helper method for the glitch methods
    # copies the line at place1 to place2, or from the line at place2 to place1
    #
    def __swap_at(self, place1, place2):
        len1 = len(self.__body[place1])
        len2 = len(self.__body[place2])
        original = self.__body[place1]
        if len1 < len2:
            new_line = self.__generate_fitting_line(place1, place2);
        else:
            new_line = self.__generate_fitting_line(place2, place1);
        self.__body[place1] = new_line[:len(new_line) - 4]
        if len(self.__body[place1]) != len(original):
            self.__body[place1] = original

        return

    # 
    # Swaps lines randomnly, shortening those lines as needed. 
    # Flavor introduces more distance (in lines) between the two swapped lines
    #
    #
    def glitch_random_swap(self, interval, flavour): 
        counter = 0
        offset_counter = 0
        for num in range(0, len(self.__body)):
            if counter == interval:
                place1 = num
                place2 = num-(1+self.__rng.randint(0, 2 + flavour % 10)) #introduced randomness here for more organic looking results
                self.__swap_at(place1,place2)
                counter = flavour
            else:
                counter = counter + 1 
        return 

    #
    # Swaps lines random width apart, as it goes on, the width between swapped lines
    #   will get worse and the process is repeated more times (increasing the glitching affect)
    #
    def glitch_corrupt(self, interval, flavour):     
        corruption = 1
        counter = 0
        for num in range(0,len(self.__body)):
            if counter == interval:
                for i in range(corruption):
                    place1 = num-i
                    place2 = num-(i+1+self.__rng.randint(0, 5 + corruption))
                    self.__swap_at(place1,place2)    
                counter = 0
                corruption = corruption + 1
            else:
                counter = counter + 1
        return  

    #
    # Returns the glitched version of the file as text
    #
    def text(self):
        return "".join(self.__header + self.__body)
