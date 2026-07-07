"""
CZI mosaic → MIP OME-TIFF
Reads a tiled Zeiss CZI (mosaic), stitches tiles, max-projects over Z,
and writes a single CYX OME-TIFF with correct pixel size metadata.

Usage:
  conda run -n braian python3 /home/jflab/Analysis/czi_mip.py
"""

import aicspylibczi
import numpy as np
import tifffile
import xml.etree.ElementTree as ET

F_IN  = "/home/jflab/Analysis/Automated Cell Counting/M3 Hippocampus 20x 062026.czi"
F_OUT = "/home/jflab/Analysis/Automated Cell Counting/M3_20x_MIP.ome.tiff"
PIXEL_SIZE_UM = 0.69   # µm/px at 20x/0.8, zoom 0.6

# ── 1. Open and inspect ──────────────────────────────────────────────────────
print("Opening CZI...")
czi = aicspylibczi.CziFile(F_IN)
dims = czi.get_dims_shape()
print(f"  Dims shape : {dims}")
print(f"  Is mosaic  : {czi.is_mosaic()}")

# Pull C and Z counts from dims dict (list of dicts for multi-scene)
dim0 = dims[0] if isinstance(dims, list) else dims
n_c = dim0.get('C', (0, 1))[1]
n_z = dim0.get('Z', (0, 1))[1]
n_s = dim0.get('S', (0, 1))[1]
print(f"  Scenes={n_s}  Channels={n_c}  Z-planes={n_z}")

# ── 2. Read mosaic per channel, max-project over Z ───────────────────────────
# read_mosaic stitches all tiles for a given C/Z/S and returns (1, Y, X)
# Process one Z-plane at a time to keep memory low

print("Generating MIP (this will take a few minutes for a full-section mosaic)...")
mip_channels = []

for c in range(n_c):
    print(f"  Channel {c}/{n_c-1}: reading {n_z} z-planes...", flush=True)
    stack = []
    for z in range(n_z):
        plane = czi.read_mosaic(C=c, Z=z, scale_factor=1.0)
        stack.append(plane.squeeze())   # remove all size-1 dims → (Y, X)
        print(f"    z={z} shape={plane.shape} dtype={plane.dtype}", flush=True)
    mip_c = np.max(stack, axis=0)   # (Y, X)
    mip_channels.append(mip_c)
    print(f"  Channel {c} MIP done. Shape: {mip_c.shape}", flush=True)

mip = np.stack(mip_channels, axis=0)   # (C, Y, X)
print(f"Final MIP shape: {mip.shape}  dtype: {mip.dtype}")

# ── 3. Build minimal OME-XML with pixel size ─────────────────────────────────
C, Y, X = mip.shape
ome_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06
       http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
  <Image ID="Image:0" Name="M3_20x_MIP">
    <Pixels ID="Pixels:0"
            Type="uint16"
            DimensionOrder="XYZCT"
            SizeX="{X}" SizeY="{Y}" SizeZ="1" SizeC="{C}" SizeT="1"
            PhysicalSizeX="{PIXEL_SIZE_UM}" PhysicalSizeXUnit="µm"
            PhysicalSizeY="{PIXEL_SIZE_UM}" PhysicalSizeYUnit="µm">
      <Channel ID="Channel:0:0" Name="DAPI"     SamplesPerPixel="1"/>
      <Channel ID="Channel:0:1" Name="Fos-EGFP" SamplesPerPixel="1"/>
      <Channel ID="Channel:0:2" Name="TdTom-Cy3" SamplesPerPixel="1"/>
      <TiffData/>
    </Pixels>
  </Image>
</OME>"""

# ── 4. Write OME-TIFF ─────────────────────────────────────────────────────────
print(f"Writing {F_OUT} ...")
tifffile.imwrite(
    F_OUT,
    mip,
    photometric="minisblack",
    metadata=None,
    description=ome_xml.encode(),
)
print("Done.")
print(f"Output: {F_OUT}")
