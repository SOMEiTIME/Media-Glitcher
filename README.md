# project-video-glitch
for python2.7

##  Usage
```
python2.7 media_glitcher.py input_file_name output_file_name
```

In media_glitcher.py there are a couple of sections to adjust:

 * The header_length variable may be adjusted as desired, 15 is good for video, images may be fine with 0 

 * Glitch operations can be adjusted, changed, or removed


## Recommended Settings
These settings have gotten good results on their own and together:
```Python 
    media_to_work_on.glitch_random_swap(200, 50)
    media_to_work_on.glitch_random_swap(100, 3)
    media_to_work_on.glitch_corrupt(200, 30)
    media_to_work_on.glitch_corrupt(400, 3)
    media_to_work_on.glitch_random_swap(40, 3)
```
