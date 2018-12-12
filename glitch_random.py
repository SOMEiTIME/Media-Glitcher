#glitcher

import random, sys, os


if len(sys.argv) >= 2:
	inputfile = sys.argv[1]
	outputfile = sys.argv[2]
else:
	print("\nUsage:\n     glitch_random.py inputfile outputfile\n")
	exit()



file = open(inputfile,"rb") #mess_with.txt is the filename to read
								#it'd be great if this could be done via the commandline, without converting to .txt

header = []
for num in range(0,200): #read past the header lines, stored for later
	header.append(file.readline(num))



#loads the whole file into body
#shouldn't we go line by line? Things are very inneficient here
#the advantage of loading the whole file in, is that glitch can run multiple times on one file, increasing the variety of effects
body = file.read(os.stat(sys.argv[1]).st_size-20); #how much to not mess with?
#for num in range(201): #further removes some part from the body (the ending of the file shouldn't be messed with either)
	#body.pop(0)

file.close()

newfile = open(outputfile,"wb") #the new, mangled version of the file will be called new.txt
							#this could also be done through the commandline

#need to change these string based operations into byte based operations
#this function is the heart of the program, glitch will cause video distortion effects of length interval
	#it does this via swapping data for a certain length
def glitch(body,interval,offset): 

	counter = 0
	for num in range(0,len(body)):

		if counter == interval:
			place1 = num
			place2 = num-(1+random.randint(0,20)) #introduced randomness here for more organic looking results
			

			len1 = len(body[place1])
			len2 = len(body[place2])
			original = body[place1]
			newstring = ""
			if len1 < len2:
				for char in body[place1]:
					newstring = newstring + char 
				count = 0
				for char in body[place2]:
					if count >= len(body[place1])-4:
						newstring = newstring + char
					count = count +1
			else:
				for char in body[place2]:
					newstring = newstring + char
				count = 0
				for char in body[place1]:
					if count >= len(body[place2])-4:
						newstring = newstring + char
					count = count +1
			

			body[place1] = newstring[:len(newstring)-4]

			if len(body[place1]) != len(original):
				body[place1] = original

			counter = 0
		else:
			counter = counter + 1 
	return body 



#these settings have gotten good results
body = glitch(body,2000,4)
body = glitch(body,200,50)
body = glitch(body,25,13)
#body = glitch(body,23,49)



for i in range(2): #an easy way to reglitch multiple times 
	body = glitch(body,1049-i,1)

newfile.writelines(header)

newfile.write(body)





