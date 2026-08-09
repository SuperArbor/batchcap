# Manual

A convenient batch capture tool for both Windows and Linux. Below is an example.

![SAMPLE](https://user-images.githubusercontent.com/11332363/174342053-e868a9a1-8eb3-4e3b-8d6e-4e753c095fb6.png)

## Prerequisites

FFmpeg 4 or higher version should be installed. As far as I know, FFmpeg 3 lacks some APIs, causing the tool to fail. You can download the latest build from https://github.com/GyanD/codexffmpeg/releases/latest.

## Install as tool with UV

```pwsh
cd BatchCap
uv tool install -e .
```

## Usage

### Arguments

The arguments below are used to specify the input and output behaviors.

*-p / --path* (type: string, default: directory of BatchCap.py): **Absolute** path of a folder or a file. It specifies the video(s) to be captured.

*-g / --height* (type: integer, default: 270): The height of each captured image (in pixels).

*-t / --tile* (type: string, default value: "4x4"): Shape of the tile made up from the captured images with format "cxr" where c stands for columns and r stands for rows. "1x1" is not allowed.

*-s / --seek* (type: float, default: 0): Time of the first capture (in seconds).

*-i / --timestamp* (store true): Whether or not show present timestamp on captures. This option needs no parameters. To opt out overwriting, just omit this argument.

*-o / --overwrite* (store true): Whether or not overwrite the existing files. This option needs no parameters. To opt out overwriting, just omit this argument.

*-f / --format* (type: str, default: "png"): Output format. Should be one of the image file extensions, i.e. png, bmp, jpg and so forth.

*-c / --fontcolor* (type: str, default: "white"): Font color of the timestamp. For example, "red" or "0#00000000".

*-r / --padratio* (type: float, default: 0.01): Ratio of padding against short edge of each image.

*-n / --fontratio* (type: float, default: 0.08): Ratio of font size against short edge of each image.

*-v / --verbose* (store true): Verbose level for ffmpeg command output.

#### Run with command

Run the following line.

```pwsh
# -p path   Captures screenshot(s) of file named path (or the videos under the folder named path).
# -s 1      The capture begins at second 1.0 in the video.
# -i        Embed timestamp on the captures.
# -c yellow timestamp font color is yellow.
# -n 0.08   timestamp font size is 0.08 * min(width, height).
# -g 270    The height of each image is 270 pixels (the ratio is remained the same as the source video).
# -r 0.01   padding is to be set as 0.01 * min(width, height), where width and height are the width and heigth of a frame of image.
# -t 4x4    The screenshot is made up of 16 captured images with 4 columns and 4 rows.
# -o        Overwrite existing files with the same file name with the output files.
# -f png    Output png format picture.
# -v        Verbose level for ffmpeg command output.
batchcap -p <path_or_directory> -s 1 -i -c yellow -n 0.08 -g 270 -r 0.01 -t 4x4 -o -f png
```

#### Run with script

To handle a batch of videos, especially those under a specific directory, running with the scripts under the scripts folder is recommended. The idea is:

(1) Put the script file under the folder of the videos;

(2) Edit the script file to specify the arguments;

(3) Run the script.
