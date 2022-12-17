#!/usr/bin/env python3

import argparse
import os
import sys
import cv2
import numpy

import version

def main(argv):
    parser = argparse.ArgumentParser(description=version.version_string(__file__))
    parser.add_argument("video_file")
    parser.add_argument("output_file")
    args = parser.parse_args(argv[1:])
    
    cap = cv2.VideoCapture(args.video_file)
    result = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        else:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            if result is None:
                result = frame
            else:
                result = numpy.maximum(frame, result)
    cv2.imwrite(args.output_file, result)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
