#glitcher


from random import *


file = open("mess_with.txt","r")

header = []
for num in range(0,200):
	header.append(file.readline(num))

random.seed()
body = []
#for num in range(201,3000000): #1000000
	#body.append(file.readline(num))
for line in file:
	body.append(line)
print "done reading in file"
for num in range(201):
	body.pop(0)



file.close()

newfile = open("new.txt","w")


def glitch(body,interval,offset): 

	counter = 0
	for num in range(0,len(body)):

		if counter == (interval + random.randint(-25,100)):




			place1 = num
			place2 = num-1
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
			#else:
				#print body[num]
			#body[num-2] = body[num-5]
			#body[num-3] = body[num-1]
			#print body[num]
			#print len(body[num])
			#print len1

			#assert len(body[num]) == len(body[num-1])
			counter = 0
		else:
			counter = counter + 1
	return body 


body = glitch(body,2000,4)

for i in range(3):
	body = glitch(body,10000-i,1)

newfile.writelines(header)

newfile.writelines(body)





