#!/usr/bin/env python3

import argparse
import os
import sys
import datetime
import dateutil
import dateutil.parser
import json
import ffmpeg
import cv2
import numpy as np

import colorparse
import rgbadraw
import argutil
import version

args = None

ROT_TABLE = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    -90: cv2.ROTATE_90_COUNTERCLOCKWISE,
}

def make_lut(gamma):
    lut = np.zeros((256, 1), dtype=np.uint8)
    for i in range(256):
        lut[i][0] = 255 * (float(i) / 255)**(1.0 / gamma)
    return lut

def parse_timedelta(time_str):
    h, m, s = map(float, time_str.split(":"))
    return datetime.timedelta(hours=h, minutes=m, seconds=s)

def make_digest_movie(detection_result_file,
                      marker_color, marker_thickness,
                      timestamp_color, timestamp_font_scale, gamma, cue):
    lut = make_lut(gamma)
    cue_ms = int(cue * 1000)
    basename = os.path.basename(detection_result_file)
    output_filename = os.path.join(args.output_directory,
                                   os.path.splitext(basename)[0] + '.mp4')
    if not args.pipe:
        print("detection result: " + detection_result_file)
        print("output: " + output_filename)
    
    detections = []
    with open(detection_result_file) as f:
        detections = json.load(f)

    if len(detections) == 0:
        if not args.pipe:
            print("no meteor detected. skip.")
        return
    
    detections.sort(key=lambda x:x['frame'])
    
    # result と動画が1対1対応すると仮定
    video_file = detections[0]['file']
    if not args.pipe:
        print("video:" + video_file)
    video_info = ffmpeg.probe(video_file)
    creation_time = video_info['streams'][0]['tags']['creation_time']
    cap = cv2.VideoCapture(video_file)
    writer = None
    if not args.pipe:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = cap.get(cv2.CAP_PROP_FPS)
        size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        writer = cv2.VideoWriter(output_filename, fourcc, fps, size)

    timelines = []
    prev_start = None
    prev_end = None
    detects = []
    for detect in detections:
        delta = parse_timedelta(detect['time'])
        start = delta - datetime.timedelta(seconds=args.margin_before)
        end = delta + datetime.timedelta(seconds=args.margin_after)
        # print("[" + str(start) + " - " + str(end) + "] : " + str(delta))
        if prev_start is None:
            prev_start = start
            prev_end = end
            detects = [detect]
        elif end < prev_start or prev_end < start:
            timelines.append({
                "start": prev_start,
                "end": prev_end,
                "detects" : detects
            })
            prev_start = start
            prev_end = end
            detects = [detect]
        else:
            prev_start = min(prev_start, start)
            prev_end = max(prev_end, end)
            detects.append(detect)
    if prev_start is not None:
        timelines.append({
            "start": prev_start,
            "end": prev_end,
            "detects" : detects
        })

    # write video
    rec = False
    for tl in timelines:
        detects = tl['detects']
        if not args.pipe:
            print(str(tl['start']) + " - " +
                  str(tl['end']) + " : detects=" + str(len(detects)))
        while True:
            ret, img = cap.read()
            if not ret:
                break
            
            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
            time = datetime.timedelta(milliseconds=timestamp)
            if not rec and tl['start'] < time:
                rec = True
                cue_start = timestamp
            if rec:
                if gamma is not 0:
                    img = cv2.LUT(img, lut)
                for d in detects:
                    if str(time) == d['time']:
                        def draw_marker(img, color):
                            for line in d['lines']:
                                x1, y1, x2, y2 = line[0]
                                cv2.rectangle(img, (x1, y1), (x2, y2),
                                              color, marker_thickness)
                        if (marker_color):
                            img = rgbadraw.draw(img, marker_color, draw_marker)
                if args.rotation != 0:
                    img = cv2.rotate(img, ROT_TABLE[args.rotation])
                # タイムゾーンを考慮しないカメラ用の補正(JST固定)
                ct_str = creation_time.replace('Z', '+09:00')
                t = dateutil.parser.parse(ct_str) + time
                def draw_timestamp(img, color):
                    text = str(t)
                    (w, h), b = cv2.getTextSize(text,
                                                cv2.FONT_HERSHEY_COMPLEX,
                                                timestamp_font_scale, 1)
                    cv2.putText(img, text=str(t), org=(2,2+h),
                                fontFace=cv2.FONT_HERSHEY_COMPLEX,
                                fontScale=timestamp_font_scale,
                                color=color, lineType=cv2.LINE_AA)
                    if cue_ms > 0 and (cue_start + cue_ms) > timestamp:
                        cv2.line(img, pt1=(2,6+h), pt2=(2+w,6+h), color=color,
                                 thickness=2, lineType=cv2.LINE_4)
                        
                if (timestamp_color):
                    img = rgbadraw.draw(img, timestamp_color, draw_timestamp)
                if args.pipe:
                    sys.stdout.buffer.write(img.tobytes())
                else:
                    writer.write(img)
                
            if tl['end'] < time:
                rec = False
                break
    if not args.pipe:
        writer.release()
    cap.release()

def main(argv):
    parser = argparse.ArgumentParser(description=version.version_string(__file__))
    parser.add_argument("detection_result_file", nargs='+')
    parser.add_argument("--margin-before", type=float, default=2.0)
    parser.add_argument("--margin-after", type=float, default=2.0)
    parser.add_argument("--marker-color", default="(0,255,0)",
                        help="'(B,G,R)' or '(B,G,R,A)' format.")
    parser.add_argument("--marker-thickness", type=int, default=1)
    parser.add_argument("--timestamp-color", default="(160,160,160)",
                        help="'(B,G,R)' or '(B,G,R,A)' format.")
    parser.add_argument("--timestamp-font-scale", type=float, default=1.0)
    parser.add_argument("--disable-marker", action="store_true")
    parser.add_argument("--disable-timestamp", action="store_true")
    parser.add_argument("--config-file", default=None)
    parser.add_argument("--output-directory", default='.')
    parser.add_argument("--pipe", action="store_true")
    parser.add_argument("--gamma", type=float, default='1')
    parser.add_argument("--cue", type=float, default=0)
    parser.add_argument("--rotation", type=int, default=0)
    global args
    args = parser.parse_args(argv[1:])

    if args.config_file:
        new_args = argutil.merge_config(parser, argv, args.config_file,
                                        ('--disable-marker',
                                         '--disable-timestamp',
                                         '--pipe'))
        if new_args is not None:
            args = new_args
    
    marker_color = None
    if not args.disable_marker:
        try:
            marker_color = colorparse.parse(args.marker_color)
        except (colorparse.ColorFormatError, colorparse.ColorValueError) as err:
            print("ERROR: " + err.message, file=sys.stderr)
            return -1

    timestamp_color = None
    if not args.disable_timestamp:
        try:
            timestamp_color = colorparse.parse(args.timestamp_color)
        except (colorparse.ColorFormatError, colorparse.ColorValueError) as err:
            print("ERROR: " + err.message, file=sys.stderr)
            return -1
    
    if not os.path.exists(args.output_directory) and not args.pipe:
        try:
            os.mkdir(args.output_directory)
        except Exception as err:
            print("ERROR: " + err.message, file=sys.stderr)
            return -1

    if not (args.rotation == 0 or args.rotation == 90 or
            args.rotation == 180 or args.rotation == 270 or args.rotation == -90):
            print("ERROR: invalid --rotation arg: specify 0 or 90 or 180 or 270 or -90.")
            return -1

    for detection_result_file in args.detection_result_file:
        make_digest_movie(detection_result_file,
                          marker_color, args.marker_thickness,
                          timestamp_color, args.timestamp_font_scale,
                          args.gamma, args.cue)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
