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
from collections import namedtuple
import shapefile
from rasterio.features import rasterize
from rasterio.transform import Affine

imsize = 1201
hisize = 1081
sealevel = 40
height_scale = 64

water_url = "https://dds.cr.usgs.gov/srtm/version2_1/SWBD/SWBD%s/%s%se.zip"
land_url = "https://dds.cr.usgs.gov/srtm/version2_1/SRTM3/Eurasia/%s%s.hgt.zip"

BBox = namedtuple('BBox', ['top', 'bottom', 'left', 'right'])
Paths = namedtuple('Paths', ['land_url', 'land_name', 'water_url', 'water_name'])

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

def download(url):
    #if not os.path.isfile(name + '.hgt'):
    print("Downloading", url)
    r = requests.get(url)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    z.extractall()

def normalise(a):
    width = hisize/a.shape[1]
    height = hisize/a.shape[0]
    #a[a==0] = -10 # make sea below sea-level
    a = a + sealevel
    a = a * height_scale
    a = scipy.ndimage.zoom(a, [height, width])
    #a = scipy.ndimage.filters.gaussian_filter(a, 1)
    a = np.clip(a, 0, 65535)
    return a
    	   

def write_png(name, a):
    pngWriter = png.Writer(a.shape[1], a.shape[0],
                           greyscale=True,
                           alpha=False,
                           bitdepth=16)
    with open(name + '.png', 'wb') as pngfile:
        pngWriter.write(pngfile, a)

def lookup(lat, lon):
    if lat > 0:
        strlat = "N%02d" % math.floor(lat)
    else:
        strlat = "S%02d" % math.floor(-lat)

    if lon > 0:
        strlon = "E%03d" % math.floor(lon)
        wurl = water_url % ('east', strlon.lower(), strlat.lower())
    else:
        strlon = "W%03d" % math.floor(-lon)
        wurl = water_url % ('west', strlon.lower(), strlat.lower())

    water_name = "%s%se" % (strlon.lower(), strlat.lower())
    lurl = land_url % (strlat, strlon)
    land_name = "%s%s" % (strlat, strlon)

    return Paths(lurl, land_name, wurl, water_name)

def bounds(lat, lon, km=18):
    """A Cities: Skylines map is 18km
    one arc second is rougly 30m at the equator
    one SRTM cell is 3 arc second
    one cell is 90m
    200 cells is 18 km"""
    height = 100/18*km # from center
    width = height/math.cos(math.radians(lat))
    x = (lon % 1) * 1200
    y = (1 - lat % 1) * 1200
    return BBox(y - height, y + height,
            x - width, x + width)


def adjust_water(lat, lon, tile, shp, seabed):
    sf = shapefile.Reader(shp)
    a = Affine.translation(lon, lat) * Affine.scale(1/1200., -1/1200.)

    image = rasterize(sf.shapes(), out=tile, default_value=seabed, transform=a)
    return image

if __name__ == "__main__":
    lat, lon = [float(l) for l in sys.argv[1:]]
    bbox = bounds(lat, lon)
    print(bbox)
    paths = lookup(lat, lon)
    if not os.path.isfile(paths.land_name + '.hgt'):
        download(paths.land_url)

    if not os.path.isfile(paths.water_name + '.shp'):
        download(paths.water_url)

    a = as_array(paths.land_name)
    adjust_water(math.ceil(lat), math.floor(lon), a, paths.water_name, -20)
    a = a[int(bbox.top):int(bbox.bottom), int(bbox.left):int(bbox.right)]
    a = normalise(a)

    im = plt.imshow(a, cmap='gray')
    #im.axes.add_patch(patches.Rectangle([bbox.left, bbox.top], 200, 200, fill=False))
    plt.show()
    write_png(paths.land_name, a)
