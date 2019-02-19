
# project-video-glitch
for python2.7

##  Usage
```
python2.7 media_glitcher.py input_file_name output_file_name
```

In media_glitcher.py there are a couple of areas to play around with
  The header_length variable may be adjusted as desired, 15 is good for images and video 
  *Glitch operations can be adjusted, changed, or removed


## Recommended Settings
These settings have gotten good results on their own and together:
```Python 
    media_to_work_on.glitch_random_swap(body,200,50)
    media_to_work_on.glitch_random_swap(body,100,3)
    media_to_work_on.glitch_corrupt(body,200,30)
    media_to_work_on.glitch_corrupt(body,400,3)
    media_to_work_on.glitch_random_swap(body,40,3)

```
