import os, sys
import ffmpeg
import argparse

from logger import initialize
from loguru import logger
from Tree import *
from traceback import print_exc, format_exc
import json

def get_video_info(file:str):
    probe = ffmpeg.probe(file)
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    avg_frame_rate = video_info['avg_frame_rate']
    if '/' in avg_frame_rate:
        a, b = avg_frame_rate.split('/')
        avg_frame_rate = float(a) / float(b)
    else:
        avg_frame_rate = float(avg_frame_rate)
    duration = float(probe['format']['duration'])
    return {'avg_frame_rate': avg_frame_rate, 'duration': duration}

def default_output_rule(input:str):
    filename, _ = os.path.splitext(input)
    return f'{filename}_cap.png'

def capture_file(file:str, args, output_rule=None):
    if not output_rule:
        output_rule = default_output_rule
    
    info = get_video_info(file)
    total = info['duration'] * info['avg_frame_rate']
    r, c = args.tile.split('x')
    interval = total // (int(r) * int(c))
        
    output_name = output_rule(file)
    basename = os.path.basename(output_name)
    if not args.overwrite:
        if os.path.exists(output_name):
            return basename
        
    try:
        (ffmpeg
            .input(file)
            .filter('select', f'not(mod(n, {interval}))')
            .filter('scale', args.width, -1)
            .filter('tile', args.tile)
            .output(output_name, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True))

        return basename
    except Exception:
        logger.error(format_exc())
        return None

def capture(path:str, args, output_rule=None):
    if os.path.isdir(path):
        output = capture_dir(path, args, output_rule)
    else:
        output = capture_file(path, args, output_rule)
    return output
    
def capture_dir(dir:str, args, output_rule=None, tree=None):
    if not output_rule:
        output_rule = default_output_rule
        
    if tree == None:
        tree = NodeDir(dir, None)
        
    for file in os.listdir(dir):
        filename = os.path.abspath(os.path.join(dir, file))
        if os.path.isdir(filename):
            tree.mkdir(file)
            capture_dir(filename, args, output_rule, tree[file])
        elif is_video(file): 
            tree.touch(output_rule(file))
            capture_file(filename, args, output_rule)
        else:
            continue
    return tree

def is_video(file:str) -> bool:
    return file.endswith(('mp4', 'mkv', 'avi'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # parser.add_argument('-d', '--directory', default=os.path.dirname(__file__))
    parser.add_argument('-d', '--directory', default=r"C:\Users\snrih\Desktop\test")
    parser.add_argument('-o', '--overwrite', default=True)
    parser.add_argument('-w', '--width', default=360)
    parser.add_argument('-t', '--tile', default='3x5')
    args = parser.parse_args()
    
    if args.directory:
        output = capture(args.directory, args=args)
    else:
        print('Input a valid file or directory for parameter.')  
    
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    config_log = json.load(open(config_path, mode='r'))
    initialize(config_log)
    
    logger.info(f'\n{output}')
    
    
    