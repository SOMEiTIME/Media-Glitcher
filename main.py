#!/usr/bin/env python2.7
import sys, os


from media import media


if len(sys.argv) >= 2:
    inputfile = sys.argv[1]
    outputfile = sys.argv[2]
else:
    print("\nUsage:\n     glitch_random.py inputfile outputfile\n")
    exit()

print "inputfile: ", str(sys.argv[1])
print "outputfile: ", str(sys.argv[2]) 


file = open(inputfile,"r") #mess_with.txt is the filename to read


#loads the whole file into body
#shouldn't we go line by line? Things are very inneficient here
#the advantage of loading the whole file in, is that glitch can run multiple times on one file, increasing the variety of effects


newfile = open(outputfile,"w") #the new, mangled version of the file will be called new.txt
                            #this could also be done through the commandline

media_to_work_on = media(file,newfile)


#these settings have gotten good results
#body = glitch(body,200,50)
#body = A.glitch(body,100,3)
#body = B.glitch(body,200,30)


media_to_work_on.glitch_corrupt(100,3)
media_to_work_on.glitch_random_swap(200,4)
#body = glitch(body,400,3)

#body = glitch_corrupt(body,400,3) 
#body = glitch(body,40,3)

file.close()
newfile.close()



