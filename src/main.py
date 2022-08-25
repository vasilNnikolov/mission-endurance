import sys
import os
import argparse
import geopandas as gpd
from point_and_shoot import point, shoot
from superimpose import superimpose
from image_analysis import identify_crop

def main():
    """
    pass the location of the tif file relative to the main dir(~/mission-endurance/)
    """
    parser = argparse.ArgumentParser(description="Prepare .tif image for ML model")
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    image_location = args.image

    pointing_location = (0, 0)
    point.point(pointing_location)
    bands = (4, 3, 2, 8)
    image = shoot.take_picture_from_file(image_location, bands)

    shapefile_filename = os.path.join("/", "home", "vasil", "mission-endurance", "data", "farm_shapefiles.zip")
    data = gpd.read_file(shapefile_filename)

    filtered_image = superimpose.filter_image(image, data)
    ndvi = identify_crop.ndvi_of_field(filtered_image) 
    print(ndvi)

if __name__ == "__main__":
    main()
