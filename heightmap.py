import struct
import numpy as np
import scipy.ndimage
import scipy.ndimage.filters
import requests
import zipfile
import gzip
import shutil
import io
import sys
import os
import os.path
import matplotlib.pyplot as plt
import png
import math
from collections import namedtuple
import shapefile
from rasterio.features import rasterize
from affine import Affine

imsize = 3601
hisize = 1081
sealevel = 40
height_scale = 64

water_url = "https://dds.cr.usgs.gov/srtm/version2_1/SWBD/SWBD%s/%s%se.zip"
land_url = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{y}/{y}{x}.hgt.gz"

BBox = namedtuple('BBox', ['top', 'bottom', 'left', 'right'])
Paths = namedtuple('Paths', ['land_url', 'land_name', 'water_url', 'water_name'])

def transformation(lat, lon):
    return Affine.translation(lon, lat) * Affine.scale(1/imsize, -1/imsize)

def as_array(name):
    filename = name + ".hgt"

    a = np.zeros([imsize, imsize])#, np.int16)

    void_fill = 0;
    with open(filename, "rb") as f:
        for x in range(imsize):
            for y in range(imsize):
                buf = f.read(2)  # read two bytes and convert them:
                val = struct.unpack('>h', buf)  # ">h" is a signed two byte integer
                if val[0] != -32768:
                    a[x,y] = val[0]
                    void_fill = val[0]
                else:
                    a[x,y] = void_fill
    return a

def download_zip(url):
    print("Downloading", url)
    r = requests.get(url)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    z.extractall()

def download_gzip(url):
    print("Downloading", url)
    r = requests.get(url)
    fname = os.path.split(url)[1]
    ufname = os.path.splitext(fname)[0]
    with gzip.open(io.BytesIO(r.content), 'rb') as f_in, open(ufname, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

def normalise(a):
    a = a + sealevel
    a = a * height_scale
    width = hisize/a.shape[1]
    height = hisize/a.shape[0]
    a = scipy.ndimage.zoom(a, [height, width])
    a = scipy.ndimage.filters.gaussian_filter(a, 2)
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
        strlat = "S%02d" % -math.floor(lat)

    if lon > 0:
        strlon = "E%03d" % math.floor(lon)
        wurl = water_url % ('east', strlon.lower(), strlat.lower())
    else:
        strlon = "W%03d" % -math.floor(lon)
        wurl = water_url % ('west', strlon.lower(), strlat.lower())

    water_name = "%s%se" % (strlon.lower(), strlat.lower())
    lurl = land_url.format(y=strlat, x=strlon)
    land_name = "%s%s" % (strlat, strlon)

    return Paths(lurl, land_name, wurl, water_name)

def bounds(lat, lon, km=18):
    """A Cities: Skylines map is 18km
    one arc second is rougly 30m at the equator
    there are 3600 arc seconds to a degree
    so 108000 meter in a degree
    so 0.1666 degree in 18km"""
    height = km*1000/(30*60*60)
    width = height/math.cos(math.radians(lat))
    return BBox(lat + height/2, lat - height/2,
                lon - width/2, lon + width/2)

def adjust_water(lat, lon, tile, shp, seabed):
    sf = shapefile.Reader(shp)
    a = transformation(lat, lon)

    image = rasterize(sf.shapes(), out=tile, default_value=seabed, transform=a)
    return image

def get_bounds(bbox):
    tiles = {}
    for lat in [bbox.top, bbox.bottom]:
        for lon in [bbox.left, bbox.right]:
            paths = lookup(lat, lon)
            tiles[(math.floor(lat), math.floor(lon))] = paths
    
    data = {}
    for coord, paths in tiles.items():
        if not os.path.isfile(paths.land_name + '.hgt'):
            download_gzip(paths.land_url)

        if not os.path.isfile(paths.water_name + '.shp'):
            download_zip(paths.water_url)

        a = as_array(paths.land_name)
        adjust_water(coord[0]+1, coord[1], a, paths.water_name, -20)
        data[coord] = a

    coords = sorted(data.keys())
    if len(coords) == 1:
        a = data[coords[0]]
    elif len(coords) == 2:
        c1, c2 = coords
        if c1[0] == c2[0]:
            a = np.concatenate([data[c1], data[c2]], axis=1)
        else:
            a = np.concatenate([data[c2], data[c1]], axis=0)
    else:
        c1, c2, c3, c4 = coords
        b = np.concatenate([data[c1], data[c2]], axis=1)
        c = np.concatenate([data[c3], data[c4]], axis=1)
        a = np.concatenate([c, b], axis=0)

    #coord is bottom-left position
    maxlat = max([c[0] for c in coords])
    minlon = min([c[1] for c in coords])
    root = (maxlat+1, minlon)
    aff = transformation(*root)
    top_left = ~aff*(bbox.left, bbox.top)
    bottom_right = ~aff*(bbox.right, bbox.bottom)
    print(top_left, bottom_right)
    a = a[int(top_left[1]):int(bottom_right[1]), int(top_left[0]):int(bottom_right[0])]
    return a

if __name__ == "__main__":
    lat, lon = [float(l) for l in sys.argv[2:]]
    bbox = bounds(lat, lon)
    print(bbox)
    a = get_bounds(bbox)
    a = normalise(a)

    im = plt.imshow(a, cmap='gray')
    #im.axes.add_patch(patches.Rectangle([bbox.left, bbox.top], 200, 200, fill=False))
    plt.show()
    write_png(sys.argv[1], a)
