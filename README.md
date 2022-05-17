# Manual

A convenient batch capture tool. Currently it only supports Windows.

## prerequisite

ffmpeg should be installed. [Here](https://ffmpeg.org/download.html) is the link.

## Usage

### Arguments

*-p / --path*: Path of a folder or path of a video file. It specifies the video(s) to be captured.

*-o / --overwrite*: Whether to overwrite the existing files. This option needs no parameters. To opt out overwriting, just ommit this argument.

*-w / --width*: The width of each captured image.

*-t / --tile*: Shape of the tile made up from the captured images.

*-s / --seek*: Time of the first capture.

### Run the tool

You can choose to run the tool with command or with script.

#### Run with command

Run the following line in shell.

```powershell
# This command captures screenshot(s) of path_to_folder_or_file (or the videos under the folder). The screenshot is made up of 20 captured images with shape 5x4. The height of each image is 360 pixels (the ratio is remained the same as the video).
path_to_python path_to_batchcap.py -d path_to_folder_or_file -s 10 -o -w 360 -t 5x4
```

#### Run with script

(1) Input the command above in a powershell script file (with extension ".ps1").

```powershell
# Gets the directory of the script
$Path=$PWD.Path
$PathInfo=[System.Uri]$Path

if($PathInfo.IsUnc){
    # pushd is for UNC drive. This command pushes the current directory of the batch file to a virtual drive.
    pushd $Path
    
    # If -d is ommited. The program uses the directory of the current batch file as working directory.
    & path_to_python path_to_batchcap.py -s 10 -o -w 360 -t 5x4 

    # Remember to pop the virtual drive before exiting.
    popd
}
else {
    # $Path is Local Path
    & path_to_python path_to_batchcap.py -s 10 -o -w 360 -t 5x4 
}
pause
```

(2) Copy the batch file to the directory of videos.

(3) Run the batch file by double click the script file.
