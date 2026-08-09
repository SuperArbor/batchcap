# Manual

A convenient batch capture tool for both Windows and Linux. Below is an example.

![SAMPLE](https://user-images.githubusercontent.com/11332363/174342053-e868a9a1-8eb3-4e3b-8d6e-4e753c095fb6.png)

## Prerequisites

FFmpeg with the following filters should be installed. Also make sure FFmpeg and FFprobe directories are in the PATH.
```
scale, drawtext, format, pad, xstack, tile, select, trim
``` 
You can download the latest build from https://github.com/GyanD/codexffmpeg/releases/latest on Windows or https://github.com/BtbN/FFmpeg-Builds/releases/latest on Linux.

## Install as tool with UV

```pwsh
cd batchcap
uv tool install -e .
```

## Usage

```pwsh
batchcap [-h] [-s SEEK] [-g HEIGHT] [-t TILE] [-o] [-i] [-f FORMAT] [-c FONTCOLOR] [-n FONTRATIO] [-r PADRATIO] [-v] path [path ...]
```

The argument `path` specifies the video(s) to be captured, or a directory that includes multiple video files. Wildcard is supported, such as:

```
batchcap *.mp4 folder/*.mkv
```

### Options

The Options below are used to specify the input and output behaviors.

*-g / --height* (type: integer, default: 270): The height of each captured image (in pixels).

*-t / --tile* (type: string, default value: "4x4"): Shape of the tile made up from the captured images with format "cxr" where c stands for columns and r stands for rows. "1x1" is not allowed.

*-s / --seek* (type: float, default: 0): time of the first capture (in seconds).

*-i / --timestamp* (store true): whether or not show present timestamp on captures.

*-o / --overwrite* (store true): whether or not overwrite the existing files.

*-f / --format* (type: str, default: "png"): output format. Should be one of the image file extensions, i.e. png, bmp, jpg and so forth.

*-c / --fontcolor* (type: str, default: "white"): font color of the timestamp. For example, "red" or "0#00000000".

*-r / --padratio* (type: float, default: 0.01): ratio of padding against short edge of each image.

*-n / --fontratio* (type: float, default: 0.08): ratio of font size against short edge of each image.

*-v / --verbose* (store true): verbose level for ffmpeg command output.

#### Run with command

Run the following line.

```pwsh
# -s 1      the capture begins at second 1.0 in the video.
# -i        embed timestamp on the captures.
# -c yellow timestamp font color is yellow.
# -n 0.08   timestamp font size is 0.08 * min(width, height).
# -g 270    the height of each image is 270 pixels (the ratio is remained the same as the source video).
# -r 0.01   padding is to be set as 0.01 * min(width, height), where width and height are the width and heigth of a frame of image.
# -t 4x4    the screenshot is made up of 16 captured images with 4 columns and 4 rows.
# -o        overwrite existing files with the same file name with the output files.
# -f png    output png format picture.
# -v        verbose level for ffmpeg command output.
batchcap -s 1 -i -c yellow -n 0.08 -g 270 -r 0.01 -t 4x4 -o -f png path
```

#### Run with script

To handle a batch of videos, especially those under a specific directory, running with the scripts under the scripts folder is recommended.

(1) Put the script file under the folder of the videos;

(2) Edit the script file to specify the arguments;

(3) Run the script.
