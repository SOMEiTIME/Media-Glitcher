#!/usr/bin/env python2.7
from glitcher_abstract import glitcher
import random, sys, os

class default_glitcher(glitcher):

    def glitch(self,body,interval,flavour): 
        counter = 0
        offset_counter = 0
        for num in range(0,len(body)):

            if counter == interval:
                place1 = num
                place2 = num-(1+random.randint(0,2 + flavour % 10)) #introduced randomness here for more organic looking results
                

                len1 = len(body[place1])
                len2 = len(body[place2])
                original = body[place1]
                if len1 < len2:
                    new_line = super(default_glitcher,self)._generate_fitting_line(body,place1,place2);
                else:
                    new_line = super(default_glitcher,self)._generate_fitting_line(body,place2,place1);

                body[place1] = new_line[:len(new_line)-4]

                if len(body[place1]) != len(original):
                    body[place1] = original

                counter = flavour
            else:
                counter = counter + 1 
        return body 


