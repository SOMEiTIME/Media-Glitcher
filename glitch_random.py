#!/usr/bin/env python2.7


import random, sys, os


if len(sys.argv) >= 2:
    inputfile = sys.argv[1]
    outputfile = sys.argv[2]
else:
    print("\nUsage:\n     glitch_random.py inputfile outputfile\n")
    exit()

print "inputfile: ", str(sys.argv[1])
print "outputfile: ", str(sys.argv[2]) 


file = open(inputfile,"r") #mess_with.txt is the filename to read
header = []

body = []
for line in file:
    body.append(line)

for num in range(15):

#for num in range(201):
    header.append(body.pop(0))


#loads the whole file into body
#shouldn't we go line by line? Things are very inneficient here
#the advantage of loading the whole file in, is that glitch can run multiple times on one file, increasing the variety of effects

file.close()

newfile = open(outputfile,"w") #the new, mangled version of the file will be called new.txt
                            #this could also be done through the commandline

def generate_fitting_line(body,lineA,lineB):
    new_line = ""

    for char in body[lineA]:
        new_line = new_line + char 
    count = 0
    for char in body[lineB]:
        if count >= len(body[lineA])-4:
            new_line = new_line + char
        count = count +1

    return new_line

#this function is the heart of the program, glitch will cause video distortion effects of length interval
    #it does this via swapping data (to nearby, randomly chosen locations) at roughly (interval) lines apart


def glitch(body,interval,flavour): 

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
                new_line = generate_fitting_line(body,place1,place2);
            else:
                new_line = generate_fitting_line(body,place2,place1);

            body[place1] = new_line[:len(new_line)-4]

            if len(body[place1]) != len(original):
                body[place1] = original

            counter = flavour
        else:
            counter = counter + 1 
    return body 


#every time a swapping happens, the next time, they will be swapped farther apart, increasing visual distortions
def glitch_corrupt(body,interval,flavour): 
    
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
                new_line = generate_fitting_line(body,place1,place2);
            else:
                new_line = generate_fitting_line(body,place2,place1);
                

                body[place1] = new_line[:len(new_line)-4]

                if len(body[place1]) != len(original):
                    body[place1] = original

            counter = 0
            corruption = corruption + 1
        else:
            counter = counter + 1

    return body 




#these settings have gotten good results
#body = glitch(body,200,50)
body = glitch(body,100,3)
#body = glitch(body,150,400)



#body = glitch(body,400,3)

#body = glitch_corrupt(body,400,3)
#body = glitch(body,40,3)


newfile.writelines(header)

newfile.writelines(body)





