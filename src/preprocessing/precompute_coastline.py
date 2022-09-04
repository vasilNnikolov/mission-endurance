import cv2
import dill as pickle
import numpy as np
from processing import compute_coastline, correlate_images
from time_and_shoot.sat_image import SatImage

from preprocessing import cloud_mask


def precompute_coastline():
    base_image = cv2.imread("./monkedir/stacked_rgb.tiff")

    cloud_filter = cloud_mask.cloud_mask(SatImage(image=base_image))

    final_image_data = compute_coastline.compute_coastline(SatImage(image=base_image))
    final_image_data = final_image_data.data.astype(np.uint8) * 255
    # TODO create a better compression for the computed coastline
    cv2.imwrite("./monkedir/precomputed_coastline_rgb_sat.tiff", final_image_data)


def precompute_coastline_keypoints():
    base_image = cv2.imread("./monkedir/stacked_rgb.tiff")

    cloud_filter = cloud_mask.cloud_mask(SatImage(image=base_image))

    final_image_data = compute_coastline.compute_coastline(SatImage(image=base_image))
    kpts, desc = correlate_images.get_ksts_decriptors(final_image_data)
    with open("./monkedir/precomputed_keypoingts.pkl", "wb") as file:
        pickle.dump((kpts, desc), file)


def load_precomputed_coastline(filename) -> SatImage:
    return SatImage(image=cv2.cvtColor(cv2.imread(filename) * 255, cv2.COLOR_BGR2GRAY))


def load_precomputed_keypoints(filename):
    with open("./monkedir/precomputed_keypoingts.pkl", "rb") as file:
        (kpts, desc) = pickle.load(file)
    return (kpts, desc)


