#!/usr/bin/env python
# -*- coding: utf-8 -*-
# project   : xyz2wmts.py
# begin     : 2014-09-04
# copyright : (C) 2014 Minoru Akagi
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import math
import os
# Pseudo Mercator tile
R = 6378137
TSIZE1 = R * math.pi

def degreesToMercatorMeters(lon, lat):
  # formula: http://en.wikipedia.org/wiki/Mercator_projection
  x = R * lon * math.pi / 180
  y = R * math.log(math.tan((90 + lat) * math.pi / 360))
  return x, y

def mercatorMetersToDegrees(x, y):
  # formula: http://en.wikipedia.org/wiki/Mercator_projection
  lon = x / R * 180 / math.pi
  lat = 360 / math.pi * math.atan(math.exp(y / R)) - 90
  return lon, lat

def scaleDenominator(zoom):
  c = 2 * TSIZE1
  pixelsize = c / 256 / (2 ** zoom)
  return pixelsize / 0.00028      # scale = 0.00028 / pixelsize

class WMTSLayerDef:
  PARAMS = ["identifier", "title", "abstract", "templateUrl", "zmin", "zmax", "bbox", "format"]

  def __init__(self, identifier, title, abstract, templateUrl, zmin=None, zmax=None, bbox=None, format=None):
    self.identifier = identifier
    self.title = title
    self.templateUrl = templateUrl
    self.abstract = "" if abstract is None else abstract
    self.zmin = 0 if zmin is None else zmin
    self.zmax = 18 if zmax is None else zmax
    self.bbox = bbox
    if format:
      self.format = format
    else:
      ext = templateUrl.split(".")[-1].lower()
      ext2format = {"jpg": "image/jpeg"}
      self.format = ext2format.get(ext, "image/" + ext)

  @classmethod
  def fromList(cls, l):
    p = l + [None] * len(cls.PARAMS)
    return WMTSLayerDef(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7])

  @classmethod
  def fromDict(cls, d):
    p = [None] * len(cls.PARAMS)
    for i, key in enumerate(cls.PARAMS):
      p[i] = d.get(key)
    return WMTSLayerDef.fromList(p)

  @classmethod
  def fromListOrDict(cls, p):
    if isinstance(p, list):
      return WMTSLayerDef.fromList(p)
    elif isinstance(p, dict):
      return WMTSLayerDef.fromDict(p)
    else:
      return None

def xyz2wmts(settings):
  from xmldocument import MyXMLDocument
  doc = MyXMLDocument()
  E = doc.append

  root = E(None, "Capabilities", {"version": "1.0.0",
                                  "xmlns": "http://www.opengis.net/wmts/1.0",
                                  "xmlns:ows": "http://www.opengis.net/ows/1.1",
                                  "xmlns:xlink": "http://www.w3.org/1999/xlink",
                                  "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                  "xsi:schemaLocation": "http://www.opengis.net/wmts/1.0 http://schemas.opengis.net/wmts/1.0/wmtsGetCapabilities_response.xsd"})

  # ServiceMetadataURL
  E(root, "ServiceMetadataURL", {"xlink:href": settings["metadataURL"]})

  # ows:ServiceIdentification
  service = settings.get("service")
  if service:
    e = E(root, "ows:ServiceIdentification")

    E(e, "ows:ServiceType", text="OGC WMTS")
    E(e, "ows:ServiceTypeVersion", text="1.0.0")
    E(e, "ows:Title", text=service["Title"])

    for lang, abstract in (service.get("Abstract") or {}).items():
      E(e, "ows:Abstract", {"xml:lang": lang}, abstract)

    if service.get("Keywords"):
      e1 = E(e, "ows:Keywords")
      for keyword in service["Keywords"]:
        E(e1, "ows:Keyword", text=keyword)

    if service.get("Fees"):
      E(e, "ows:Fees", text=service["Fees"])
    if service.get("AccessConstraints"):
      E(e, "ows:AccessConstraints", text=service["AccessConstraints"])

  # ows:ServiceProvider
  provider = settings.get("provider")
  if provider:
    e = E(root, "ows:ServiceProvider")
    E(e, "ows:ProviderName", text=provider["Name"])

    if provider.get("SiteURL"):
      E(e, "ows:ProviderSite", {"xlink:href": provider["SiteURL"]})

    """
    e1 = E(e, "ows:ServiceContact")
    E(e1, "ows:IndividualName", text="IndividualName")
    E(e1, "ows:PositionName", text="PositionName")
    #E(e1, "ows:ContactInfo", text="ContactInfo")
    """

  # Contents
  msets = {}
  contents = E(root, "Contents")
  for lyr in map(WMTSLayerDef.fromListOrDict, settings["layers"]):
    # Layer
    layer = E(contents, "Layer")
    E(layer, "ows:Identifier", text=lyr.identifier)
    E(layer, "ows:Title", text=lyr.title)
    if lyr.abstract:
      E(layer, "ows:Abstract", text=lyr.abstract)

    if lyr.bbox:
      xmin, ymin = (lyr.bbox[0], lyr.bbox[1])
      xmax, ymax = (lyr.bbox[2], lyr.bbox[3])
    else:
      xmin = ymin = -TSIZE1
      xmax = ymax = TSIZE1




    e = E(layer, "ows:BoundingBox", {"crs": "urn:ogc:def:crs:EPSG:6.18.3:3857"})
    E(e, "ows:LowerCorner", text="{0} {1}".format(xmin, ymin))
    E(e, "ows:UpperCorner", text="{0} {1}".format(xmax, ymax))

    if lyr.bbox:
      xmin84, ymin84 = mercatorMetersToDegrees(lyr.bbox[0], lyr.bbox[1])
      xmax84, ymax84 = mercatorMetersToDegrees(lyr.bbox[2], lyr.bbox[3])
      e = E(layer, "ows:WGS84BoundingBox", {"crs": "urn:ogc:def:crs:OGC:2:84"})
      E(e, "ows:LowerCorner", text="{0} {1}".format(xmin84, ymin84))
      E(e, "ows:UpperCorner", text="{0} {1}".format(xmax84, ymax84))

    e = E(layer, "Style", {"isDefault": "true"})
    E(e , "ows:Identifier", text="default")

    E(layer, "Format", text=lyr.format)

    # TileMatrixSetLink
    msetId = "z{0}to{1}".format(lyr.zmin, lyr.zmax)
    if not msetId in msets:
      msets[msetId] = (lyr.zmin, lyr.zmax)

    e = E(layer, "TileMatrixSetLink")
    E(e, "TileMatrixSet", text=msetId)
    #E(e, "TileMatrixSetLimits")

    templateUrl = lyr.templateUrl.replace("{z}", "{TileMatrix}").replace("{y}", "{TileRow}").replace("{x}", "{TileCol}")
    E(layer, "ResourceURL", {"format": lyr.format, "resourceType": "tile", "template": templateUrl})

  # TileMatrixSet
  for msetId in msets:
    zmin, zmax = msets[msetId]
    matrixSet = E(contents, "TileMatrixSet")
    E(matrixSet, "ows:Identifier", text=msetId)
    E(matrixSet, "ows:SupportedCRS", text="urn:ogc:def:crs:EPSG:6.18.3:3857")
    for zoom in range(zmin, zmax + 1):
      matrix = E(matrixSet, "TileMatrix")
      E(matrix, "ows:Identifier", text=str(zoom))
      tileSize = settings.get("tile_size", 256)
      matrixSize = 2 ** zoom
      E(matrix, "ScaleDenominator", text="{0:.12f}".format(scaleDenominator(zoom)))
      E(matrix, "TopLeftCorner", text="{0:.8f} {1:.8f}".format(-TSIZE1, TSIZE1))
      E(matrix, "TileWidth", text=str(tileSize))
      E(matrix, "TileHeight", text=str(tileSize))
      E(matrix, "MatrixWidth", text=str(matrixSize))
      E(matrix, "MatrixHeight", text=str(matrixSize))

  return doc


# from collections import OrderedDict
#xmltodict
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re

def mod2dict(mod):
  d ={}
  for attr in dir(mod):
    if attr[0] != "_":
      d[attr] = getattr(mod, attr)
  return d

if __name__ == "__main__":
  import sys

  INDENT = ' ' * 4

  if len(sys.argv) == 1:
    # read settings from settings.py if no command line parameter is specified
    import settings

    xml_output = xyz2wmts(mod2dict(settings)).document().toprettyxml("  ", "\n", "utf-8")
    print (xml_output.decode('utf-8'))

    sys.exit(0)

  
  if len(sys.argv) >= 2:
    # read settings from settings.py if no command line parameter is specified
    import settings
    # read xml file
    xmlfile = sys.argv[1]
    # if xml file ends in html
    if not os.path.exists(xmlfile):
      sys.stderr.write("{} doesn't exist.".format(xmlfile))
      sys.exit(1)

    with open(xmlfile) as f:
        inxml = f.read()
      

    if xmlfile.endswith('.html'):
        # parse html and get javascript section

        # Use BeautifulSoup to parse HTML
        soup = BeautifulSoup(inxml, 'html.parser')

        # Find the script element containing the configuration
        script = soup.find_all('script')[-1].string

        # Extract minZoom, maxZoom, and bounds using regex
        min_zoom = re.search(r'minZoom: (\d+)', script).group(1)
        max_zoom = re.search(r'maxZoom: (\d+)', script).group(1)
        bounds = re.search(r'extent: \[(.*?)\]', script).group(1)
        # tileSize: [512, 512]
        tile_size = re.search(r'tileSize: (\[.*?\])', script).group(1)
        # url: './{z}/{x}/{y}.webp',
        #strip leading .
        url_odix = re.search(r'url: \'(.*?)\'', script).group(1).lstrip('.')


        # debugging requests override below
        # replace webp with png
        # url_odix = url_odix.replace('.webp', '.png')
        # tile_size = tile_size.replace('512', '256')


        # format = "image/webp" if url_odix.endswith('.webp') else 'image/png'

        #terrimap doenst request tiles the standard way of this this set to webp
        format = "image/png"


        # print to std:error

        print(min_zoom, max_zoom, bounds, tile_size,url_odix, file=sys.stderr)

        if len(sys.argv) == 2:
          settings.tile_size = int(tile_size.split(",")[0].strip("[]"))
            
          settings.layers.append([u"osm", u"OpenStreetMap", u"", "http://localhost/wmts/osm/{z}/{x}/{y}.png", 0, 19])
          settingsdict = mod2dict(settings)
          

          settingsdict["layers"][0][4] = int(min_zoom)
          settingsdict["layers"][0][5] = int(max_zoom)
          bounds = [float(x) for x in bounds.split(",")]
          settingsdict["layers"][0].append(bounds)
          settingsdict["layers"][0].append(format)

        else:
          # get url and title form argv
          baseurl = sys.argv[2]
          # slug = sys.argv[3]
          # properties = sys.argv[4]
          # tidyname = sys.argv[5]
          settings.tile_size = int(tile_size.split(",")[0].strip("[]"))

          settings.metadataURL = baseurl + "/WMTSCapabilities.xml"
          slug = sys.argv[3]


          # layers.append([u"srtm3_shaded_relief", u"SRTM3 SHADED RELIEF (JAPAN)", u"The source is SRTM3.",
          #                "http://localhost/wmts/srtm3_shaded_relief/{z}/{x}/{y}.png",
          #                3, 10, [119.9995833, 19.9995833, 154.0004167, 47.0004167]])

          # layer name is hidden, use consistent id for easy reference


          settings.layers.append([u"overlay", u"overlay", u"", baseurl + url_odix, int(min_zoom), int(max_zoom), [float(x) for x in bounds.split(",")], format])
          settingsdict = mod2dict(settings)

        print(settingsdict, file=sys.stderr)

    settingsdict = mod2dict(settings)


    xml_output = xyz2wmts(mod2dict(settings)).document().toprettyxml("  ", "\n", "utf-8")

    print (xml_output.decode('utf-8'))

    print ("\n\n",settings.metadataURL,"\n\n", file=sys.stderr)



    sys.exit(0)
