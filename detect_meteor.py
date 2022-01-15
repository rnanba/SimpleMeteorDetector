#!/usr/bin/env python3

import argparse
import math
import os
import sys
import typing
import datetime
import json

import cv2
import numpy
import ffmpeg
from PIL import Image
import PIL.ExifTags as ExifTags
from tqdm import tqdm

import colorparse
import rgbadraw
import argutil

args = None

def load_gray(filepath: str) -> numpy.array:
    """
    グレイスケール画像読み込み
    :param str filepath: 入力ファイルパス
    :return: グレイスケール画像データ
    """
    filepath = str(filepath)
    img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
    return img


def detect_lines(img: numpy.array) -> typing.List[numpy.array]:
    """
    直線検出
    :param numpy.array img: 入力画像（グレイスケール）
    :return: 検出直線リスト, 輪郭画像
    """
    ret, thr = cv2.threshold(img, args.background_threshold, 255,
                             cv2.ADAPTIVE_THRESH_MEAN_C)
    lines = cv2.HoughLinesP(thr, rho=1, theta=math.pi/180, threshold=0,
                            minLineLength=args.min_line_length,
                            maxLineGap=args.max_line_gap)
    return lines, thr


def detect_area(img: numpy.array, threshold: float = 0.0001) -> typing.List[numpy.array]:
    """
    閾値を超える面積を持つ輪郭の検出
    :param numpy.array img: 入力画像
    :param float threshold: 閾値（画像全体の何%を`(0, 1]`で指定）
    :return: 閾値を超えた面積の領域リスト
    """
    height, width = img.shape
    img_area = width * height
    ret, thr = cv2.threshold(img, 127, 255, cv2.ADAPTIVE_THRESH_MEAN_C)
    _, contours, hierarchy = cv2.findContours(thr, 1, 2)
    contours = [cnt for cnt in contours if (cv2.contourArea(cnt) / img_area) > threshold]
    return contours


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


def line_length(line: numpy.array) -> float:
    """
    直線の長さの算出
    `cv2.HoughLinesP()`の返り値は`[ [ [start_x, start_y, end_x, end_y] ], ... ]`形式になっている
    :param line: `[ [start_x, start_y, end_x, end_y] ]`であること
    :return: 直線の長さ
    """
    assert len(line) == 1
    sx, sy, ex, ey = line[0]
    dx = ex - sx
    dy = ey - sy
    return math.sqrt(dx * dx + dy * dy)


def detect_meteor(img: numpy.array, area_threshold: float, line_threshold: float) -> typing.Optional[typing.Tuple[str, typing.List[numpy.array]]]:
    """
    流星の検出
    :param numpy.array img: 入力画像
    :param float area_threshold: 面積のある領域検知用閾値（`detect_area()`関数`threshold`参照）
    :param float line_threshold: 検出した直線を流星と判定する最小の長さ
    :return: (画像ファイルパス, 検出した直線) or None, 輪郭画像 or None
    """
    if area_threshold > 0.0:
        area_contours = detect_area(img, area_threshold)
        if area_contours:
            img = fill_area(img, area_contours)
    lines, timg = detect_lines(img)
    if lines is not None:
        length = max([line_length(x) for x in lines])
        if length > line_threshold:
            return lines, timg
    return None, None

class VideoFrames:
    def __init__(self, video_file, stack_size):
        video_info = ffmpeg.probe(video_file)
        self.video_creation_time = video_info['streams'][0]['tags']['creation_time']
        self.cap = cv2.VideoCapture(video_file)
        self.video_file = video_file
        self.stack_size = stack_size
        self.timestamps = []

    def __iter__(self):
        return VideoFrameIterator(self)

    def add_timestamp(self):
        self.timestamps.append(self.cap.get(cv2.CAP_PROP_POS_MSEC))

    def timedelta(self, i):
        return datetime.timedelta(milliseconds=self.timestamps[i])

    def creation_time(self, i):
        return self.video_creation_time
        
    def filepath(self, i):
        return str(self.video_file)

    def length(self):
        return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

class VideoFrameIterator:
    def __init__(self, vf):
        self.vf = vf
        self.cap = vf.cap
        self.frames = [None] * vf.stack_size
        self.frame_count = 0
        self.pos = 0
        self.eof = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.eof:
            raise StopIteration
        
        if self.frame_count == 0:
            for i in range(0, len(self.frames)):
                result, frame = self.cap.read()
                if result:
                    self.frame_count += 1
                    self.vf.add_timestamp()
                    self.frames[i] = frame
                else:
                    self.eof = True
        else:
            result, frame = self.cap.read()
            if result:
                self.frame_count += 1
                self.vf.add_timestamp()
                self.frames[self.pos] = frame
                self.pos += 1
                if (self.pos >= len(self.frames)):
                    self.pos = 0
            else:
                self.eof = True
                raise StopIteration
        
        return self._stack_frames()

    def _stack_frames(self):
        result = None
        for f in self.frames:
            if f is None:
                break
            if result is None:
                result = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
            else:
                # グレースケール画像に変換
                f = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
                # 比較明合成
                result = numpy.maximum(f, result)
        return result

class PhotoList:
    def __init__(self, dir):
        # 拡張子が`.jpg`の画像リストを作成
        self.image_list = []
        for dirname, _, filenames in os.walk(dir):
            self.image_list.extend([os.path.join(dirname, x) for x in filenames if x.lower().endswith(".jpg") or x.lower().endswith(".jpeg")])
            self.image_list.sort()
        self.start = 0

    def __iter__(self):
        return PhotoListIterator(self)

    def creation_time(self, i):
        TAG_DateTimeOriginal = 36867
        img = Image.open(str(self.image_list[i]))
        exif = img._getexif()
        if exif:
            return exif[TAG_DateTimeOriginal]
        else:
            return None
    
    def timedelta(self, i):
        return None

    def filepath(self, i):
        return str(self.image_list[i])
    
    def length(self):
        return len(self.image_list)

class PhotoListIterator:
    def __init__(self, pl):
        self.image_list = pl.image_list
        self.index = pl.start

    def __iter__(self):
        return self
    
    def __next__(self):
        image = None
        if self.index < len(self.image_list):
            filepath = str(self.image_list[self.index])
            image = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
            self.index += 1
            return image
        else:
            raise StopIteration

def detect_from_dir_or_video(dir_or_video):
    # 流星の写っていると思われる画像を抽出
    image_list = None
    
    if os.path.isdir(dir_or_video):
        print("directory: " + dir_or_video)
        dir = dir_or_video.rstrip("\\/")
        image_list = PhotoList(dir)
    else:
        print("video: " + dir_or_video)
        image_list = VideoFrames(dir_or_video, args.stack_frames)
    
    result = []
    for i, image in enumerate(tqdm(image_list)):
        lines, timg = detect_meteor(image, args.area_threshold, args.line_threshold)
        if lines is not None:
            entry = {}
            entry['file'] = path = image_list.filepath(i)
            timedelta = image_list.timedelta(i)
            entry['time'] = str(timedelta)
            entry['frame'] = i if timedelta else 0
            entry['creation_time'] = creation_time = image_list.creation_time(i)
            entry['lines'] = lines.tolist()
            entry['snapshot'] = ss_file = "meteorsnap_" + os.path.basename(path) + (str(timedelta).replace(':', '_') if timedelta else "") + ".png"
            result.append(entry)
            print("detected: {}{}".format(path, (": "+str(timedelta)) if timedelta else ""))
            cimg = cv2.cvtColor(timg, cv2.COLOR_GRAY2RGB)
            def draw_marker(img, color):
                for line in lines:
                    x1,y1,x2,y2 = line[0]
                    cv2.rectangle(img, (x1,y1), (x2,y2),
                                  color, args.marker_thickness)
            cv2.imwrite(os.path.join(args.output_directory, ss_file),
                        rgbadraw.draw(cimg, args.marker_color, draw_marker))

    result_file = "result_" + os.path.basename(dir_or_video) + ".json"
    with open(os.path.join(args.output_directory, result_file), mode='w') as f:
        json.dump(result, f, indent=2)
        
    print("detected: {}/{}".format(len(result), image_list.length()))
        
def main(argv: typing.List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory_or_video", nargs='+')
    parser.add_argument("--area-threshold", type=float, default=0.0)
    parser.add_argument("--line-threshold", type=float, default=21)
    parser.add_argument("--min-line-length", type=float, default=21)
    parser.add_argument("--max-line-gap", type=float, default=5)
    parser.add_argument("--background-threshold", type=int, default=25)
    parser.add_argument("--stack-frames", type=int, default=5)
    parser.add_argument("--marker-color", default="(0,255,0)",
                        help="'(R,G,B)' or '(R,G,B,A)' format.")
    parser.add_argument("--marker-thickness", type=int, default=1)
    parser.add_argument("--config-file", default=None)
    parser.add_argument("--output-directory", default='.')
    global args
    args = parser.parse_args(argv[1:])

    if args.config_file:
        new_args = argutil.merge_config(parser, argv, args.config_file)
        if new_args is not None:
            args = new_args

    try:
        args.marker_color = colorparse.parse(args.marker_color)
    except (colorparse.ColorFormatError, colorparse.ColorValueError) as err:
        print("ERROR: " + err.message, file=sys.stderr)
        return -1

    if not os.path.exists(args.output_directory):
        try:
            os.mkdir(args.output_directory)
        except Exception as err:
            print("ERROR: " + err.message, file=sys.stderr)
            return -1
    
    for dir_or_video in args.directory_or_video:
        detect_from_dir_or_video(dir_or_video)
        
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
