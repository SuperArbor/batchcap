# Manual

## prerequisite

ffmpeg should be installed. [Here](https://ffmpeg.org/download.html) is the link.

## Usage

### Arguments

*-d / --directory*: Directory of a folder or path of a video file. It specifies the video(s) to be captured.

*-o / --overwrite*: Whether to overwrite the existing files.

*-w / --width*: The width of each captured image.

*-t / --tile*: Shape of the tile made up from the captured images.

*-s / --seek*: Time of the first capture.

### Run the tool

You can choose to run the tool with command or with script.

#### Run with command

Run the following line in shell.

```powershell
directory_to_python directory_to_batchcap.py -d directory_to_folder_or_file" -o true -w 360 -t 3x3
```

#### Run with script

(1) Input the command above in a batch file.

(2) Copy the batch file to the directory of videos.

(3) Run the batch file.
