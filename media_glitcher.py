#!/usr/bin/env python2.7

# Main method and customisation area for running the media class and glitching media

import sys, os
from media import media


if len(sys.argv) >= 2:
    input_file = sys.argv[1]
    output_file = sys.argv[2]
else:
    print("\nUsage:\n     media_glitcher.py inputfile outputfile\n")
    exit()

print "Input File: ", str(sys.argv[1])
print "Output File: ", str(sys.argv[2]) 


file = open(input_file,"r") 
new_file = open(output_file,"w")

header_length = 15 #the length of the header in number of lines, messing with the headers will just break the media
media_to_work_on = media(file,new_file,header_length)

#can add or take away glitch operations in this section

#these settings have gotten good results
#media_to_work_on.glitch_random_swap(200,50)
#media_to_work_on.glitch_random_swap(100,3)
#media_to_work_on.glitch_corrupt(200,30)
#media_to_work_on.glitch_corrupt(400,3)
#media_to_work_on.glitch_random_swap(6,0)
#media_to_work_on.glitch_random_swap(300,1)

#media_to_work_on.glitch_corrupt(300,5)
media_to_work_on.glitch_random_swap(88,0)
media_to_work_on.glitch_random_swap(142,0)


#end of the glitch operations section

media_to_work_on.print_to_new_file()

file.close()
new_file.close()



