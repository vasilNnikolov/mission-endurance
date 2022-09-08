import argparse
import os
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from communications import downlink
from preprocessing import cloud_mask, precompute_coastline
from processing import compute_coastline, correlate_images, crop_field
from processing.correlate_images import Keypoints
from read_config import read_config_files, read_ground_image
from time_and_shoot import shoot
from time_and_shoot.sat_image import SatImage


def preview_ground_image():
    gnd_image = cv2.imread("")

    # already in rgb
    plt.imshow(np.clip(2 * gnd_image.astype(np.uint16), 0, 255))
    plt.show()


def sat_main(scale_factor=(5, 5)):
    """
    the main fn which runs on the satellite. fiedl coords must
    be in the form (x, y), and be in counter-clockwise direction in the coordinate system of the image(x right, y down).
    """
    parser = argparse.ArgumentParser(
        description="Pass the name of the config_folder/pass folder, ex pass_1, and the filename of the keypoints of the ground image, ex config_files/pass_1/ground_keypoints_{scale_factor[0]}_{scale_factor[1]}.pkl"
    )
    parser.add_argument("--pass_folder", required=True)
    parser.add_argument("--ground_keypoints", required=True)
    args = parser.parse_args()
    pass_folder = args.pass_folder

    # ===================camera setup================================
    time_to_take_picture = read_config_files.time_of_photo(pass_folder)

    # ===================satellite image manupulations==================
    sat_image = shoot.take_picture(time_to_take_picture)
    ground_image = SatImage(
        image=cv2.imread(os.path.join(pass_folder, "ground_image.tiff"))
    )
    plt.imshow(ground_image.data)
    plt.suptitle("Ground image")
    plt.show()
    plt.imshow(np.flip(sat_image.data, axis=2))
    plt.suptitle("Satellite image")
    plt.show()
    sat_image.mask = cloud_mask.cloud_mask(sat_image)
    sat_coastline = compute_coastline.compute_coastline(sat_image)
    ground_coastline = compute_coastline.compute_coastline(
        SatImage(image=np.flip(ground_image.data, axis=2))
    )

    coast_fig, ax = plt.subplots(1, 2)
    ax[0].imshow(ground_coastline.data)
    ax[1].imshow(sat_coastline.data)
    ax[0].title.set_text("Ground image")
    ax[1].title.set_text("Satellite image")

    custom_lines = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="white",
            label="Sea",
            markerfacecolor="yellow",
            markersize=15,
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="white",
            label="Land",
            markerfacecolor="purple",
            markersize=15,
        ),
    ]

    ax[0].legend(custom_lines, ["Sea", "Land"])
    ax[1].legend(custom_lines, ["Sea", "Land"])
    plt.show()

    sat_coastline_keypoints = correlate_images.get_keypoints(
        sat_coastline, scale_factor
    )

    sat_output_with_keypoints = cv2.cvtColor(
        sat_coastline.data.astype(np.uint8) * 255, cv2.COLOR_GRAY2RGB
    )
    for kp in sat_coastline_keypoints.kpts[:50]:
        x, y = kp.pt
        cv2.circle(
            sat_output_with_keypoints,
            (int(x), int(y)),
            30,
            color=(255, 0, 0),
            thickness=-1,
        )
    ground_keypoints = read_ground_image.read_ground_keypoints(args.ground_keypoints)

    ground_output_with_keypoints = cv2.cvtColor(
        ground_coastline.data.astype(np.uint8) * 255, cv2.COLOR_GRAY2RGB
    )
    for kp in ground_keypoints.kpts[:50]:
        x, y = kp.pt
        cv2.circle(
            ground_output_with_keypoints,
            (int(x), int(y)),
            30,
            color=(255, 0, 0),
            thickness=-1,
        )

    kpts_fig, ax = plt.subplots(1, 2)
    ax[0].imshow(ground_output_with_keypoints)
    ax[0].title.set_text("Ground coastline")
    ax[1].imshow(sat_output_with_keypoints)
    ax[1].title.set_text("Satellite coastline")

    custom_lines = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="white",
            label="Sea",
            markerfacecolor="white",
            markersize=15,
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="white",
            label="Land",
            markerfacecolor="black",
            markersize=15,
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="white",
            label="Keypoint",
            markerfacecolor="red",
            markersize=15,
        ),
    ]

    ax[0].legend(custom_lines, ["Sea", "Land", "Keypoint"])
    ax[1].legend(custom_lines, ["Sea", "Land", "Keypoint"])
    plt.show()

    # =====================ground image manupulations==================
    field_coords = read_config_files.field_coords(pass_folder)

    print("load precomputed coastline Keypoints")

    # compute and apply homography to the original sat image
    # =====================aligning of the sat image==================
    print("compute homography")
    align_result = correlate_images.compute_transform_from_keypoints(
        sat_coastline_keypoints, ground_keypoints, sat_image, ground_image
    )
    homography, align_was_successful = align_result
    if not align_was_successful:
        print("cannot continue further")
        downlink.send_message_down("ALIGN UNSUCCESSFUL")
        sys.exit("ALIGN UNSUCCESSFUL")

    print("warp sat image to ground image")
    base_h, base_w = ground_keypoints.shape
    print("precomputed coastline h, w: ", base_h, base_w)
    sat_image = SatImage(
        image=cv2.warpPerspective(
            sat_image.data, homography, (base_h, base_w), flags=cv2.INTER_NEAREST
        )
    )

    # =========================beam results back====================
    fig, ax = plt.subplots(1, 2)
    ground_image = read_ground_image.read_ground_image(pass_folder)
    average_color = np.array([0, 0, 0])
    for index, points in enumerate([field_coords, field_coords]):
        # pass aligned image and coordinates to image recognition algorithm
        poly_points = np.flip(points, axis=1)
        polygon = crop_field.Polygon(poly_points)

        only_field = crop_field.select_only_field(sat_image, polygon)
        average_color = np.average(only_field.data, axis=(0, 1))
        print("crop field")

        if index == 0:
            only_field = crop_field.select_only_field(ground_image, polygon)
            ax[index].title.set_text("Field on the ground")

        else:
            only_field = crop_field.select_only_field(sat_image, polygon)
            ax[index].title.set_text("Field on the satellite")

        ax[index].imshow(
            np.clip(
                np.flip(only_field.data, axis=2).astype(np.float16) * 1.5, 0, 255
            ).astype(np.uint8)
        )

    print(average_color)
    sky_lens = (average_color[2] - average_color[1]) / (
        average_color[1] - average_color[0]
    )
    print(f"skylens: {sky_lens}")
    print(f"ndvi: {(2.48 - sky_lens)/4.26}")

    plt.show()


if __name__ == "__main__":
    # preview_ground_image()
    scale_factor = (10, 10)
    # precompute_coastline.precompute_coastline_keypoints(
    #     "config_files/2022-09-08T11_58_04", scale_factor
    # )
    sat_main(scale_factor)
