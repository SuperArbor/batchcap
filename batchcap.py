import os, sys
import ffmpeg
import argparse

def default_output_rule(input:str):
    filename, _ = os.path.splitext(input)
    return f'{filename}_cap.png'

def capture_file(file:str, args, output_rule=None):
    if not output_rule:
        output_rule = default_output_rule
        
    output_name = output_rule(file)
    if not args.overwrite:
        if os.path.exists(output_name):
            return
        
    out, err = (
        ffmpeg
            .input(file)
            .filter('select', 'not(mod(n, 100))')
            .filter('scale', args.width, -1)
            .filter('tile', args.tile)
            .output(output_name, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True)
    )
    return out

def capture_dir(dir:str, args, output_rule=None):
    for file in os.listdir(dir):
        filename = os.path.abspath(os.path.join(dir, file))
        if os.path.isdir(filename):
            capture_dir(filename, args, output_rule)
        elif is_video(file): 
            capture_file(filename, args, output_rule)
        else:
            continue

def is_video(file:str) -> bool:
    return file.endswith(('mp4', 'mkv', 'avi'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory', default=os.path.dirname(__file__))
    parser.add_argument('-f', '--file')
    parser.add_argument('-o', '--overwrite', default=False)
    parser.add_argument('-w', '--width', default=360)
    parser.add_argument('-t', '--tile', default='3x3')
    args = parser.parse_args()
    
    if args.directory:
        capture_dir(args.directory, args=args, output_rule=None)
    elif args.file:
        capture_file(args.file, args=args, output_rule=None)
    else:
        print('Input a valid file or directory for parameter.')  
    