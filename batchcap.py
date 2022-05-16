import os, sys
import ffmpeg
import argparse

from logger import initialize
from loguru import logger
from Tree import *
from traceback import print_exc, format_exc
import json

def default_output_rule(input:str):
    filename, _ = os.path.splitext(input)
    return f'{filename}_cap.png'

def capture_file(file:str, args, output_rule=None):
    if not output_rule:
        output_rule = default_output_rule
        
    output_name = output_rule(file)
    basename = os.path.basename(output_name)
    if not args.overwrite:
        if os.path.exists(output_name):
            return basename
        
    try:
        (ffmpeg
            .input(file)
            .filter('select', 'not(mod(n, 100))')
            .filter('scale', args.width, -1)
            .filter('tile', args.tile)
            .output(output_name, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True))

        return basename
    except Exception:
        logger.error(format_exc())
        return None

def capture_dir(dir:str, args, output_rule=None):
    tree = _capture_dir(dir, args, output_rule)
    return tree
    
def _capture_dir(dir:str, args, output_rule=None, tree=None):
    if not output_rule:
        output_rule = default_output_rule
        
    if tree == None:
        tree = NodeDir(dir, None)
        
    for file in os.listdir(dir):
        filename = os.path.abspath(os.path.join(dir, file))
        if os.path.isdir(filename):
            tree.mkdir(file)
            _capture_dir(filename, args, output_rule, tree[file])
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
    parser.add_argument('-f', '--file')
    parser.add_argument('-o', '--overwrite', default=True)
    parser.add_argument('-w', '--width', default=360)
    parser.add_argument('-t', '--tile', default='3x3')
    args = parser.parse_args()
    
    if args.directory:
        output = capture_dir(args.directory, args=args)
    elif args.file:
        output = capture_file(args.file, args=args)
    else:
        print('Input a valid file or directory for parameter.')  
    
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    config_log = json.load(open(config_path, mode='r'))
    initialize(config_log)
    
    sys.stdout.writelines(str(output))
    logger.info(f'\n{output}')
    