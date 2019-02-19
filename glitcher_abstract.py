#!/usr/bin/env python2.7



class glitcher(object):
    """Abstract class for glitcher objects to complete"""

    def __init__(self):
        return

    def _generate_fitting_line(self,body,lineA,lineB):
        new_line = ""

        for char in body[lineA]:
            new_line = new_line + char 
        count = 0
        for char in body[lineB]:
            if count >= len(body[lineA])-4:
                new_line = new_line + char
            count = count +1

        return new_line

    def glitch(self,body,interval,flavour): 
        raise NotImplementedError( "Should have implemented this" )


