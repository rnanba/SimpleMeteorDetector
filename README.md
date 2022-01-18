# Simple Meteor Detector v0.1

## 概要

写真または動画から流星を検出するツールです。@tail-feather さんの「OpenCVの直線検知で流星群画像を仕分け」( https://gist.github.com/tail-feather/d32d9ec125ba28c4a65b28fb74d7d00f ) をベースに改造したものです。

検出結果は JSON ファイルに出力します。動画から検出した場合、このファイルを利用して流星が流れた部分を集めたダイジェスト動画を生成できます。

## 動作環境

Python 3 と OpenCV が動く環境で動作します。
以下の環境で動作確認をしています。

- Ubuntu 20.04 LTS
- Anaconda 4.11
  - Python 3.7
  - OpenCV 3.4
  - FFMPEG 4.0

## 使い方の概要

### 写真の場合

1. 撮影した写真(JPEG)をディレクトリにコピーします。
   - 各写真は恒星の動きが十分小さく点に写っている必要があります。
2. 流星が写っている写真を一つ見つけるか、あるいは撮影した写真を全て比較明合成した画像を用意します。
3. detector_tuner.py で 2 の画像を処理して結果画像を確認します。
4. 結果画像に不満があればコマンドライン引数でパラメータを調整して 3 を繰り返します。
5. detect_meteor.py に 4 で調整したパラメータと 1 のディレクトリを指定して流星を検出します
6. コンソール出力または結果ファイルに書かれたファイル名を見て流星が写っている写真を選びます。

### 動画の場合

1. lighten_only_composite.py で撮影した動画の全フレームを比較明合成した画像を得ます。
   - 赤道儀で追尾撮影、または撮影時間が短く、恒星の動きが十分小さい場合です。
   - 恒星の動きが大きい場合は 2, 3 では流星の写っている部分をキャプチャーした画像を使います。
2. detector_tuner.py で 1 の画像を処理して結果画像を確認します。
3. 結果画像に不満があればコマンドライン引数でパラメータを調整して 2 を繰り返します。
4. detect_meteor.py に 3 で調整したパラメータと動画をを指定して流星を検出します。
5. make_digest_movie.py で結果ファイルを処理して流星が流れている部分だけを抜き出したダイジェスト動画を生成します。

## 各コマンドの使い方

### lighten_only_composite.py

動画の全フレームの比較明合成を行うためのコマンドです。

```
python lighten_only_composite.py input_video_file output_image_file
```

| 引数                  | 説明                                                  |
|-----------------------|-------------------------------------------------------|
| *input_video_file*	| 撮影した動画ファイルです。				|
| *output_image_file*	| 比較明合成の結果の出力先のファイルです。		|

*output_image_file* のファイル形式は拡張子に合わせた形式になります。

### detector_tuner.py

流星の写った画像を使って流星検出とマーク描画を試すためのコマンドです。

```
python detector_tuner.py input_image_file
```

| 引数                  | 説明                                                  |
|-----------------------|-------------------------------------------------------|
| *input_image_file*	| 流星の写った画像ファイルです。		        |

`input_image_file` には流星の写った画像ファイルを指定します。赤道儀で追尾撮影した動画の場合は lighten_only_composite.py の出力を使うとよいでしょう。

detector_tuner.py が正常に終了すると、コンソールに JSON 形式のパラメータを出力します(`--output-config-file` オプションを指定した場合はオプションで指定されたファイルに出力します)。また、以下のファイルを出力します。

| 出力ファイル          | 説明                                                  |
|-----------------------|-------------------------------------------------------|
| *入力画像のファイル名(拡張子なし)*_detect.png | 入力画像に検出した流星を囲むマーカーを描画した画像です。|
| *入力画像のファイル名(拡張子なし)*_threshold.png | 入力画像を二値化した画像です。|
| *入力画像のファイル名(拡張子なし)*_detect_threshold.png | 入力画像を二値化した画像に検出した流星を囲むマーカーを描画した画像です。|

二値化や検出基準のパラメータ、マーカーの描画パラメータなどはコマンドラインオプションで指定します。コマンドラインオプションには以下のものがあります。

| オプション            | 説明                                                  |
|-----------------------|-------------------------------------------------------|
| `--background-threshold` *BACKGROUND_THRESHOLD* | 流星検出の前処理で画像を二値化する際の輝度の閾値です。0から255の整数値を指定します。省略すると自動的に検出した背景レベルを適用します。|
| `--min-line-length` *MIN_LINE_LENGTH* | 流星として検知する直線の最低の長さです。単位はピクセルです。|
| `--max-line-gap` *MAX_LINE_GAP* | 流星の直線が途切れている場合に許容する隙間の長さです。単位はピクセルです。|
| `--marker-color` *MARKER_COLOR* | マカーカーの色を指定します。色の書式は「(*R*,*G*,*B*)」または「(*R*,*G*,*B*,*A*)」形式で、*R*,*G*,*B*,*A* には0から255の整数値を指定します。*A* はアルファチャンネルの値で、255で不透明、0で透明、その間の値は半透明になります。|
| `--marker-thickness` *MARKER_THICKNESS* | マーカーの線の太さを指定します。単位はピクセルです。|
| `--output-config-file` *OUTPUT_CONFIG_FILE* | 適用されたパラメータ値の出力先のJSONファイルのファイル名を指定します。このオプションを指定するとコンソールにはパラメータ値は出力しません。出力されたファイルは detect_meteor.py 用の設定ファイルとして使用できます。|

使用するカメラやレンズ、撮影条件等によって適切なパラメータは大きく変わります。detect_meteor.py で指定するパラメータ値を、このコマンドで先に調整することで、試行錯誤する時間を節約できます。

## detect_meteor.py

ディレクトリにまとめた撮影画像、または撮影動画から流星を検出します。

```
python detect_meteor.py input_directory_or_movie
```

| 引数                  | 説明                                                  |
|-----------------------|-------------------------------------------------------|
| *input_directory_or_movie* | 撮影画像をまとめたディレクトリ、または撮影動画のファイルです。複数指定すると順次処理します。 |

| 出力ファイル          | 説明                                                  |
|-----------------------|-------------------------------------------------------|
| result_*ディレクトリ名または動画ファイル名*.json | 検出結果を出力したファイルです。検出したファイル、検出位置(座標と、動画の場合は再生時間)、撮影時刻が含まれます。|
| meteorsnap_*画像ファイル名*.png | 流星が検出された画像を二値化したものにマーカーを描画した画像です(画像ディレクトリを指定した場合)。|
| meteorsnap_*動画ファイル名*_*再生時間*.png | 流星が検出されたフレームを前処理した画像にマーカーを描画した画像です(動画を指定した場合)。*再生時間* は検出されたフレームの動画の先頭からの位置を「*h*_*m*_*s*」形式(*s* は小数を含む)で表したものです。フレームの前処理は連続した複数のフレーム(デフォルトは5フレーム)を比較明合成し、二値化するものです。|

| オプション            | 説明                                                  |
|-----------------------|-------------------------------------------------------|
| `--area-threshold` *AREA_THRESHOLD* | 建物や雲などの輪郭線を除外するために、除外対象となる領域の割合を 0〜1.0 の実数で指定します。指定した割合を越えた面積を持つ領域は流星検出の対象から除外されます。 |
| `--background-threshold` *BACKGROUND_THRESHOLD* | 流星検出の前処理で画像を二値化する際の輝度の閾値です。0から255の整数値を指定します。省略すると自動的に検出した背景レベルを適用します。|
| `--min-line-length` *MIN_LINE_LENGTH* | 流星として検知する直線の最低の長さです。単位はピクセルです。|
| `--max-line-gap` *MAX_LINE_GAP* | 流星の直線が途切れている場合に許容する隙間の長さです。単位はピクセルです。|
| `--stack-frames` *STACK_FRAMES* | 動画から検出する際に前処理で連続何フレームを比較明合成するかを指定します。デフォルト値は 5 です。 |
| `--marker-color` *MARKER_COLOR* | マカーカーの色を指定します。色の書式は「(*R*,*G*,*B*)」または「(*R*,*G*,*B*,*A*)」形式で、*R*,*G*,*B*,*A* には0から255の整数値を指定します。*A* はアルファチャンネルの値で、255で不透明、0で透明、その間の値は半透明になります。|
| `--marker-thickness` *MARKER_THICKNESS* | マーカーの線の太さを指定します。単位はピクセルです。|
| `--config-file` *CONFIG_FILE* | 検出設定ファイルを指定します。detector_tuner.py を使用した場合は、その出力を保存した JSON ファイルを指定します。|
| `--output-directory` *OUTPUT_DIRECTORY* | 出力ファイルの保存先ディレクトリを指定します。デフォルト値はカレントディレクトリです。 |

## make_digest_movie.py

TBD

## ライセンス

本ソフトウェアのライセンス条件は [LICENCE](/LICENCE) を参照してください。

本ソフトウェアは @tail-feather さんが公開している [detect_meteor.py](https://gist.github.com/tail-feather/d32d9ec125ba28c4a65b28fb74d7d00f)を改変したものです。detect_meteor.py のライセンス条件は以下の通りです。

```
BSD 3-Clause License

Copyright (c) 2021, AstroArts Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE US
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
