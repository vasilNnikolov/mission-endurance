import cv2
import matplotlib.pyplot as plt
import numpy as np

from sat_image import SatImage


class Keypoints:
    def __init__(self, from_hash=False, **kwargs):
        """
        Pass either shape, kpts and desc from orb.detectAndCompute, or with from_hash=True, the hashed object
        """
        if not from_hash:
            attributes = ["shape", "kpts", "desc"]
            if not all(kw in kwargs for kw in attributes):
                print("pass shape, kpts and desk as named arguments to Keypoints")
                exit(1)
            else:
                self.shape, self.kpts, self.desc = [kwargs[at] for at in attributes]
        else:
            if not "hash_object" in kwargs:
                print("pass shape, kpts and desk as named arguments to Keypoints")
                exit(1)
            else:
                hash_object = kwargs["hash_object"]

                self.kpts = tuple(
                    [
                        cv2.KeyPoint(
                            x=hash_keypoint[0][0],
                            y=hash_keypoint[0][1],
                            size=hash_keypoint[1],
                            angle=hash_keypoint[2],
                            response=hash_keypoint[3],
                            octave=hash_keypoint[4],
                            class_id=hash_keypoint[5],
                        )
                        for hash_keypoint in hash_object[0]
                    ]
                )
                self.desc = np.array(
                    [hash_keypoint[6] for hash_keypoint in hash_object[0]]
                )
                self.shape = hash_object[1]

    def hashable(self):
        """
        returns hash_object
        """
        return (
            [
                (
                    keypoint.pt,
                    keypoint.size,
                    keypoint.angle,
                    keypoint.response,
                    keypoint.octave,
                    keypoint.class_id,
                    description,
                )
                for keypoint, description in zip(self.kpts, self.desc)
            ],
            self.shape,
        )

    def scale_up(self, scale_up_factor):
        new_kpts = []
        for kp in self.kpts:
            new_kp = kp
            new_x = kp.pt[0] * scale_up_factor[1]
            new_y = kp.pt[1] * scale_up_factor[0]
            new_kp.pt = (new_x, new_y)
            new_kpts.append(new_kp)

        self.kpts = tuple(new_kpts)
        self.shape = (
            self.shape[0] * scale_up_factor[1],
            self.shape[0] * scale_up_factor[1],
        )
        return self


def compute_transform_from_keypoints(
    sat_keypoints: Keypoints,
    ground_keypoints: Keypoints,
):
    """
    computes and returns the affine transformation (homography) which maps the sat_keypoints to ground_keypoints, as well as a boolean whether it was successful.
    Returns: (homography, align_was_successful)
    """
    # match the features
    kpsA, descA = sat_keypoints.kpts, sat_keypoints.desc
    kpsB, descB = ground_keypoints.kpts, ground_keypoints.desc
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(descA, descB, None)

    matches = sorted(matches, key=lambda x: x.distance)
    # keep only the top matches
    keep = int(len(matches) * 0.8)
    matches = matches[:keep]
    n_matches = len(matches)
    print(f"Found {n_matches} good matches")

    p1 = np.zeros((n_matches, 2))
    p2 = np.zeros((n_matches, 2))

    for i in range(len(matches)):
        p1[i, :] = kpsA[matches[i].queryIdx].pt
        p2[i, :] = kpsB[matches[i].trainIdx].pt

    homography, _ = cv2.findHomography(p1, p2, cv2.RANSAC)

    stretch_matrix = homography[:2, :2]
    main_diagonal = stretch_matrix[0, 0] * stretch_matrix[1, 1]
    rev_diagonal = stretch_matrix[0, 1] * stretch_matrix[1, 0]
    determinant = main_diagonal - rev_diagonal
    if abs(np.dot(stretch_matrix[:, 0], stretch_matrix[:, 1]) / determinant > 0.2):
        print("ALERT!!!!!!!!!!")
        print("correlation of images failed")
        return homography, False

    return (homography, True)


def get_keypoints(coastline: SatImage, scale_factor=(10, 10)) -> Keypoints:
    """
    first scales down the image height by scale_factor[0] and the width by scale_factor[1], computest the scaled down keypoints, scales them back up and returns them.
    """
    coastline_data = coastline.data
    height, width = coastline_data.shape[:2]

    # resize image to size where it should work
    new_shape = (int(height / scale_factor[0]), int(width / scale_factor[1]))
    smaller_image = cv2.resize(coastline_data.astype(np.uint8) * 255, new_shape)
    max_features = 400
    orb = cv2.ORB_create(max_features)

    (kpsA, descsA) = orb.detectAndCompute(smaller_image, None)

    return Keypoints(shape=new_shape, kpts=kpsA, desc=descsA).scale_up(scale_factor)