import cv2 as cv
import numpy as np
import random
import os


script_dir = os.path.dirname(__file__)


def load_png(relative_path):
    load_img = cv.imread(os.path.join(script_dir, relative_path), cv.IMREAD_UNCHANGED)
    return load_img


cookie = load_png(r"Recources\cookie.png")
jar_left = load_png(r"Recources\jar_left.png")
jar_middle = load_png(r"Recources\jar_middle.png")
jar_right = load_png(r"Recources\jar_right.png")
lid = load_png(r"Recources\lid.png")
g_cookie = load_png(r"Recources\cookiegold.png")
jar_empty = load_png(r"Recources\JarEmpty.png")


def save_img(name, img):
    cv.imwrite(name, img)


def alpha_blit(front, back, ox=0, oy=0):
    """

    :param front: foreground image (has to be smaller)
    :param back: background image (has to be larger)
    :param ox: x offset
    :param oy: y offset
    :return:
    """

    back_area = back[oy: oy + front.shape[0], ox: ox + front.shape[1]]

    back_colours = back_area[:, :, :3]
    front_colours = front[:, :, :3]

    back_alpha = back_area[:, :, 3][:, :, np.newaxis] / 255
    front_alpha = front[:, :, 3][:, :, np.newaxis] / 255

    # print(back_colours.shape, front_colours.shape, back_alpha.shape, front_alpha.shape)

    back[oy: oy + front.shape[0], ox: ox + front.shape[1], :3] = (front_colours * front_alpha + back_colours * back_alpha * (1 - front_alpha)) / (front_alpha + back_alpha * (1 - front_alpha))
    np.nan_to_num(back, 0)
    back[oy: oy + front.shape[0], ox: ox + front.shape[1], 3] = (front_alpha[:, :, 0] + back_alpha[:, :, 0] * (1 - front_alpha[:, :, 0])) * 255


def build_cookie_jar(cookies, golden):
    offset_left_min = 0
    offset_left_max = 8
    offset_bottom = 14
    offset_cookies = 26
    n_cookies = 10

    if golden:
        cookies += 1

        cstep = 1 / cookies
        changse = cstep

    # return an empty jar if there are no cookies:
    if not cookies:
        return jar_empty

    sections = []
    for i in range(cookies):
        # new row starts
        if not i % n_cookies:
            sections.append(np.zeros(jar_middle.shape).astype(np.uint8))

        b_cookie = cookie
        if golden:
            if changse > random.random():
                b_cookie = g_cookie
                golden = False
            changse += cstep

        alpha_blit(b_cookie, sections[-1], random.randint(offset_left_min, offset_left_max), jar_middle.shape[0] - cookie.shape[0] - offset_bottom - offset_cookies * (i % n_cookies))

    # overlay jars
    for s in sections:
        alpha_blit(jar_middle, s)

    # stack everything:
    img = np.hstack([jar_left] + sections + [jar_right])

    # add lid:
    alpha_blit(lid, img, int(img.shape[1] // 2 - lid.shape[1] // 2), 10)
    return img


if __name__ == "__main__":
    img = build_cookie_jar(5)
    cv.imshow("test", img)
    cv.imwrite("test.png", img, [cv.IMWRITE_PNG_COMPRESSION, 9])
    cv.waitKey(0)

