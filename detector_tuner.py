#!/usr/bin/env python3
import argparse
import os
import sys
import math
import json
import cv2
import numpy

import colorparse
import rgbadraw

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

def detect_lines(src_img, background_threshold, min_line_length, max_line_gap):
    img = cv2.cvtColor(src_img, cv2.COLOR_RGB2GRAY)
    thr_img = None
    if background_threshold is None:
        thr_img, background_threshold = auto_threshold(img)
    else:
        _, thr_img = cv2.threshold(img, background_threshold, 255,
                                   cv2.ADAPTIVE_THRESH_MEAN_C)
    
    lines = cv2.HoughLinesP(thr_img, rho=1, theta=math.pi/180, threshold=0,
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
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.rectangle(img, (x1, y1), (x2, y2), rgb, marker_thickness)
        
    return rgbadraw.draw(dest_img, marker_color, draw)

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("image_file")
    parser.add_argument("--background-threshold", default='auto',
                        help="0-255 value or 'auto'.")
    parser.add_argument("--min-line-length", type=float, default=24)
    parser.add_argument("--max-line-gap", type=float, default=6)
    parser.add_argument("--marker-color", default="(0,255,0)",
                        help="'(R,G,B)' or '(R,G,B,A)' format.")
    parser.add_argument("--marker-thickness", type=int, default=1)
    parser.add_argument("--output-config-file", default=None)

    args = parser.parse_args(argv[1:])

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
    lines, thr_img, background_threshold = detect_lines(src_img,
                                                        background_threshold,
                                                        min_line_length,
                                                        max_line_gap)

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
