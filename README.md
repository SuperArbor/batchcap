# Manual

A convenient batch capture tool for both Windows and Linux.

## Prerequisites

ffmpeg should be installed.

For windows, [Here](https://ffmpeg.org/download.html) is the download link.

For Linux, simply run

```bash
sudo apt install ffmpeg
```

## Usage

### Arguments

The arguments below are used to specify the input and output behaviors.

*-p / --path*: Path of a folder or path of a video file. It specifies the video(s) to be captured.

*-o / --overwrite*: Whether to overwrite the existing files. This option needs no parameters. To opt out overwriting, just ommit this argument.

*-w / --width*: The width of each captured image (in pixels). Type integer.

*-t / --tile*: Shape of the tile made up from the captured images. Type string with format 'cxr' where c stands for columns and r stands for rows.

*-s / --seek*: Time of the first capture (in seconds). Type float.

### Run the tool

You can choose to run the tool with command or with script. Usually when there is only one video to be captured, running with command is more handy, otherwise running with a script is more convenient.

#### Run with command

Run the following line in powershell (Windows) or bash (Linux).

```powershell
# This command captures screenshot(s) of path_to_folder_or_file (or the videos under the folder).
# The screenshot is made up of 20 captured images with 5 columns and 4 rows.
# The height of each image is 360 pixels (the ratio is remained the same as the video).
# The capture begins at second 10.0 in the video.
# Overwrite existing files with the same file name with the output files.
path_to_python path_to_batchcap.py -p path_to_folder_or_file -s 10 -o -w 360 -t 5x4
```

#### Run with script

To handle a batch of videos, especially those under a specific directory, running with script is recommended. The idea is:

(1) put the script file under the corresponding folder;

(2) run the script.

In Windows, use a powershell script (with extension ".ps1").

```powershell
# Sorts the Pipeline output into several kinds of metadata.
function GetAnsVal {
    param([Parameter(Mandatory=$true, ValueFromPipeline=$true)][System.Object[]][AllowEmptyString()]$Output)
    
    $all = New-Object System.Collections.Generic.List[System.Object]
    $exception = New-Object System.Collections.Generic.List[System.Object]
    $stderr = New-Object System.Collections.Generic.List[System.Object]
    $stdout = New-Object System.Collections.Generic.List[System.Object]
    $Output | ForEach-Object {
        if ($_ -ne $null){
            if ($_.GetType().FullName -ne 'System.Management.Automation.ErrorRecord'){
                if ($null -ne $_.Exception.message){
                    $all.Add($_.Exception.message )
                    $exception.Add($_.Exception.message )
                }
                elseif ($_ -ne $null){
                    $stdout.Add($_)
                }
            } else {
                $all.Add($_.Exception.message)
                $stderr.Add($_.Exception.message)
            }   
         }
    }
    [hashtable]$return = @{}
    $return.Meta0=$all;$return.Meta1=$exception;$return.Meta2=$stderr;$return.Meta3=$stdout
    return $return
}

# Replace the '\r\n' to '\n'
function Replace {
    param([Parameter(Mandatory=$true, ValueFromPipeline=$true)][hashtable]$r)

    $Meta0=""
    foreach ($el in $r.Meta0){
        $Meta0+=$el
    }
    $Meta0=($Meta0 -split "[`r`n]") -join "`n"
    $Meta0=($Meta0 -split "[`n]{2,}") -join "`n"

    return $Meta0
}

# GetAnsVal and Replace make sure powershell output correctly. 
# Replace ForEach-Object {& GetAnsVal $_ | & Replace} with ForEach-Object {"$_"} to see the difference.
& path_to_python path_to_batchcap.py -p $PSScriptRoot -s 10 -o -w 360 -t 5x4 2>&1 | ForEach-Object {& GetAnsVal $_ | & Replace}

pause
```

In Linux, use a bash script (with extension ".sh").

```bash
#!/bin/bash

path_to_python path_to_batchcap.py -p $(dirname "$BASH_SOURCE") -s 10 -o -w 360 -t 5x4
```
