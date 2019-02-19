#!/usr/bin/env python2.7
from glitcher_abstract import glitcher
import random, sys, os


class corrupt_glitcher(glitcher):

    def glitch(self,body,interval,flavour):     
        corruption = 1
        counter = 0
        for num in range(0,len(body)):

            if counter == interval:


                for i in range(corruption):

                    place1 = num-i
                    place2 = num-(i+1+random.randint(0,5+corruption))
                    len1 = len(body[place1])
                    len2 = len(body[place2])
                    original = body[place1]
                if len1 < len2:
                    new_line =  super(corrupt_glitcher,self)._generate_fitting_line(body,place1,place2);
                else:
                    new_line =  super(corrupt_glitcher,self)._generate_fitting_line(body,place2,place1);
                    

                    body[place1] = new_line[:len(new_line)-4]

                    if len(body[place1]) != len(original):
                        body[place1] = original

                counter = 0
                corruption = corruption + 1
            else:
                counter = counter + 1

        return body 
