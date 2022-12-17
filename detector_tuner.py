#!/usr/bin/env python3
import argparse
import os
import sys
import math
import json
import cv2
import numpy
import typing

import colorparse
import rgbadraw
import argutil

T = typing.TypeVar("T")
def clamp(v: T, min_v: T, max_v: T) -> T:
    """
    clamp関数
    入力値を`[min_v, max_v]`の範囲に収める
    :param T v: 入力値
    :param T min_v: 最小値
    :param T max_v: 最大値
    :return: `[min_v, max_v]`内に収めた値
    """
    return min(max_v, max(v, min_v))

def detect_area(img: numpy.array, threshold: float = 0.0001,
                value_threshold: int = 127) -> typing.List[numpy.array]:
    """
    閾値を超える面積を持つ輪郭の検出
    :param numpy.array img: 入力画像
    :param float threshold: 閾値（画像全体の何%を`(0, 1]`で指定）
    :param int value_threshold: ピクセル値の閾値を `(0-255)`で指定）
    :return: 閾値を超えた面積の領域リスト
    """
    height, width = img.shape
    img_area = width * height
    ret, thr = cv2.threshold(img, value_threshold, 255,
                             cv2.ADAPTIVE_THRESH_MEAN_C)
    _, contours, hierarchy = cv2.findContours(thr, 1, 2)
    contours = [cnt for cnt in contours if (cv2.contourArea(cnt) / img_area) > threshold]
    return contours

def fill_area(img: numpy.array, contours: typing.List[numpy.array], buffer_ratio: float = 0.01, color: typing.Optional[float] = None) -> numpy.array:
    """
    領域の外接矩形で塗りつぶす
    :param numpy.array img: 入力画像
    :param contours: 領域リスト
    :param float buffer_ratio: バッファ率 (e.g. 6000 * 0.01 => 60px)
    :param float color: 塗りつぶしの色（未指定の場合は入力画像の中央値で塗りつぶす）
    :return: 塗りつぶし後の画像
    """
    height, width = img.shape
    x_buffer = int(width * buffer_ratio)
    y_buffer = int(height * buffer_ratio)
    # detect fill color
    if color is None:
        color = numpy.median(img)
    # fill bounding rect
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        left = clamp(x - x_buffer, 0, width)
        top = clamp(y - y_buffer, 0, height)
        right = clamp(x + w + x_buffer, 0, width)
        bottom = clamp(y + h + y_buffer, 0, height)
        pts = numpy.asarray([
            [left, top],
            [left, bottom],
            [right, bottom],
            [right, top],
        ])
        img = cv2.fillPoly(img, pts=[pts], color=(color,))
    return img

def get_background_level(img):
    height, width = img.shape[:2]
    div = 5
    tile_height = int(height / div)
    tile_width = int(width / div)
    means = []
    medians = []
    for ty in range(div):
        y = int(tile_height * ty)
        for tx in range(div):
            x = int(tile_width * tx)
            tile = img[y : y + tile_height, x : x + tile_height]
            means.append(img.mean())            
            medians.append(numpy.median(numpy.array(tile).flatten()))
            
    return max(medians), max(means)

def auto_threshold(img):
    median, mean = get_background_level(img)
    thr_median = 255
    thr_mean = 255
    while True:
        m = int(median)
        # print("median = " + str(median))
        _, thr_img = cv2.threshold(img, m, 255, cv2.ADAPTIVE_THRESH_MEAN_C)
        thr_median, thr_mean = get_background_level(thr_img)
        # print("thr_mean = " + str(thr_mean))
        if thr_mean <= 1.0:
            break
        median += 1
    return thr_img, m

def detect_lines(img, background_threshold,
                 min_line_length, max_line_gap, hough_threshold):
    thr_img = None
    if background_threshold is None:
        thr_img, background_threshold = auto_threshold(img)
    else:
        _, thr_img = cv2.threshold(img, background_threshold, 255,
                                   cv2.ADAPTIVE_THRESH_MEAN_C)
    
    lines = cv2.HoughLinesP(thr_img, rho=1, theta=math.pi/180,
                            threshold=hough_threshold,
                            minLineLength=min_line_length,
                            maxLineGap=max_line_gap)
    return lines, thr_img, background_threshold

def draw_markers(src_img, lines, marker_color, marker_thickness):
    dest_img = None
    if len(src_img.shape) == 2:
        dest_img = cv2.cvtColor(src_img, cv2.COLOR_GRAY2RGB)
    else:
        dest_img = src_img.copy()

    def draw(img, rgb):
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.rectangle(img, (x1, y1), (x2, y2), rgb, marker_thickness)
        
    return rgbadraw.draw(dest_img, marker_color, draw)

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("image_file")
    parser.add_argument("--background-threshold", default='auto',
                        help="0-255 value or 'auto'.")
    parser.add_argument("--area-threshold", type=float, default=0.0)
    parser.add_argument("--area-value-threshold", type=int, default=127)
    parser.add_argument("--min-line-length", type=float, default=24)
    parser.add_argument("--max-line-gap", type=float, default=6)
    parser.add_argument("--hough-threshold", type=int, default=0)
    parser.add_argument("--marker-color", default="(0,255,0)",
                        help="'(R,G,B)' or '(R,G,B,A)' format.")
    parser.add_argument("--marker-thickness", type=int, default=1)
    parser.add_argument("--input-config-file", default=None)
    parser.add_argument("--output-config-file", default=None)

    args = parser.parse_args(argv[1:])
    
    if args.input_config_file:
        new_args = argutil.merge_config(parser, argv, args.input_config_file)
        if new_args is not None:
            args = new_args
    
    src_img = cv2.imread(args.image_file)
    
    background_threshold = None
    if args.background_threshold != 'auto':
        try:
            background_threshold = float(args.background_threshold)
        except ValueError:
            print("ERROR: invalid background_threshold.", file=sys.stderr)
            return 1
    min_line_length = args.min_line_length
    max_line_gap = args.max_line_gap
    hough_threshold = args.hough_threshold
    area_threshold = args.area_threshold
    area_value_threshold = args.area_value_threshold

    img = cv2.cvtColor(src_img, cv2.COLOR_RGB2GRAY)
    if area_threshold > 0.0:
        area_contours = detect_area(img, area_threshold, area_value_threshold)
        if area_contours:
            img = fill_area(img, area_contours)
    lines, thr_img, background_threshold = detect_lines(img,
                                                        background_threshold,
                                                        min_line_length,
                                                        max_line_gap,
                                                        hough_threshold)

    marker_color = None
    try:
        marker_color = colorparse.parse(args.marker_color)
    except (colorparse.ColorFormatError, colorparse.ColorValueError) as err:
        print("ERROR: " + err.message, file=sys.stderr)
        return -1
        
    marker_thickness = args.marker_thickness
    detect = draw_markers(src_img, lines, marker_color, marker_thickness)
    thr_detect = draw_markers(thr_img, lines, marker_color, marker_thickness)
    
    base = os.path.splitext(os.path.basename(args.image_file))[0]
    cv2.imwrite(base + "_detect.png" , detect)
    cv2.imwrite(base + "_detect_threshold.png", thr_detect)
    cv2.imwrite(base + "_threshold.png", thr_img)

    config = {
        'background-threshold' : int(background_threshold),
        'min-line-length' : min_line_length,
        'max-line-gap' : max_line_gap,
        'hough-threshold' : hough_threshold,
        'area-threshold' : area_threshold,
        'area-value-threshold' : area_value_threshold,
        'marker-color' : str(marker_color),
        'marker-thickness' : int(marker_thickness)
    }
    if args.output_config_file == '-' or args.output_config_file is None:
        print(json.dumps(config, indent=2))
    elif args.output_config_file is not None:
        with open(args.output_config_file, mode='w') as f:
            json.dump(config, f, indent=2)

    return 0
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
