import json;
import numpy as np;
from skimage.color import rgb2lab;

# Finding the nearest colour in a palette for a given pixel
# Using lab rather than rgb to mimic human perception
class BlockPalette:
    def __init__ (self, palette_json_path):
        items = json.load(open(palette_json_path, "r"))
        self.names = [n for n, _ in items]
        rgb = np.array([c for _, c in items], dtype = np.float32) / 255.0 # extracts RGB values and normalizes to [0,1] range
        self.lab = rgb2lab(rgb.reshape(-1,1,1,3)).reshape(-1,3) #lab for euclidean distance
    
    def nearest(self, rgb):
        rgb = np.clip(np.asarray(rgb, dtype = np.float32)/255.0,0,1) # takes rgb input colour and ensures its in [0,1] range format
        lab = rgb2lab(rgb.reshape(1,1,3)).reshape(3) #convert single voxel colour to lab
        d = np.sum((self.lab - lab) ** 2, axis = 1) #compute squared euclidean distance between this LAB colour and the block's LAB colour
        return self.names[int(np.argmin(d))] # Return shortest distance
    
    # can improve this by adding transparency -> brightness -> glass etc.