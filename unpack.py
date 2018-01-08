import struct
import numpy as np
import scipy.ndimage
import scipy.ndimage.filters
import requests
import zipfile
import io
import sys
import os
import matplotlib.pyplot as plt
import png
import math

imsize = 1201
hisize = 1081
sealevel = 43
height_scale = 64

def as_array(name):
    filename = name + ".hgt"

    a = np.zeros([imsize, imsize])#, np.int16)

    with open(filename, "rb") as f:
        for x in range(imsize):
            for y in range(imsize):
                buf = f.read(2)  # read two bytes and convert them:
                val = struct.unpack('>h', buf)  # ">h" is a signed two byte integer
                if val[0] != -32768:
                    a[x,y] = val[0]
    return a

def download(name):
    if not os.path.isfile(name + '.hgt'):
        print("Downloading")
        url = "https://dds.cr.usgs.gov/srtm/version2_1/SRTM3/Eurasia/%s.hgt.zip" % name
        r = requests.get(url)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall()

def normalise(a):
    latitude = 52
    ratio = math.sin(math.radians(latitude))
    width = hisize/imsize*2
    height = width/ratio
    a[a==0] = -10 # make sea below sea-level
    raised = a + sealevel
    scaled = raised * height_scale
    zoomed = scipy.ndimage.zoom(scaled, [height, width])
    blurred = scipy.ndimage.filters.gaussian_filter(zoomed, 1)
    clipped = np.clip(blurred, 0, 65535)
    return (clipped[:hisize,:hisize],
            clipped[hisize+1:2*hisize,:hisize],
            clipped[:hisize,hisize+1:2*hisize],
	    clipped[hisize+1:2*hisize,hisize+1:2*hisize])
    	   

def write_png(name, a):
    pngWriter = png.Writer(a.shape[1], a.shape[0],
                           greyscale=True,
                           alpha=False,
                           bitdepth=16)
    with open(name + '.png', 'wb') as pngfile:
        pngWriter.write(pngfile, a)

if __name__ == "__main__":
    name = sys.argv[1]
    download(name)
    a = as_array(name)
    an = normalise(a)

    #plt.imshow(a, cmap='gray')
    #plt.show()
    for i, a in enumerate(an):
	    write_png(name+str(i), a)
