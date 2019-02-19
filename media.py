#!/usr/bin/env python2.7

import random

class media(object):
    """Abstract class for glitcher objects to complete"""

    def __init__(self,input_file,output_file):

        self.__header = []
        self.__body = []
        self.__output_file = output_file
        for line in input_file:
            self.__body.append(line)

        for num in range(15):
        #for num in range(201):
            self.__header.append(self.__body.pop(0))

        return

    def __generate_fitting_line(self,lineA,lineB):
        new_line = ""

        for char in self.__body[lineA]:
            new_line = new_line + char 
        count = 0
        for char in self.__body[lineB]:
            if count >= len(self.__body[lineA])-4:
                new_line = new_line + char
            count = count +1

        return new_line


    def glitch_random_swap(self,interval,flavour): 
        counter = 0
        offset_counter = 0
        for num in range(0,len(self.__body)):

            if counter == interval:
                place1 = num
                place2 = num-(1+random.randint(0,2 + flavour % 10)) #introduced randomness here for more organic looking results
                

                len1 = len(self.__body[place1])
                len2 = len(self.__body[place2])
                original = self.__body[place1]
                if len1 < len2:
                    new_line = self.__generate_fitting_line(place1,place2);
                else:
                    new_line = self.__generate_fitting_line(place2,place1);

                self.__body[place1] = new_line[:len(new_line)-4]

                if len(self.__body[place1]) != len(original):
                    self.__body[place1] = original

                counter = flavour
            else:
                counter = counter + 1 
        
        self.print_to_new_file()
        return 

    def glitch_corrupt(self,interval,flavour):     
        corruption = 1
        counter = 0
        for num in range(0,len(self.__body)):

            if counter == interval:


                for i in range(corruption):

                    place1 = num-i
                    place2 = num-(i+1+random.randint(0,5+corruption))
                    len1 = len(self.__body[place1])
                    len2 = len(self.__body[place2])
                    original = self.__body[place1]
                if len1 < len2:
                    new_line =  self.__generate_fitting_line(place1,place2);
                else:
                    new_line =  self.__generate_fitting_line(place2,place1);
                    

                    self.__body[place1] = new_line[:len(new_line)-4]

                    if len(self.__body[place1]) != len(original):
                        self.__body[place1] = original

                counter = 0
                corruption = corruption + 1
            else:
                counter = counter + 1

        self.print_to_new_file()
        return  

    def print_to_new_file(self):
        self.__output_file.writelines(self.__header)
        self.__output_file.writelines(self.__body)

        return
