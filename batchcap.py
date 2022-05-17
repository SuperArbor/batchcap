import os, sys
import ffmpeg
import argparse

from loguru import logger
from Tree import *
from traceback import format_exc
from tqdm import tqdm
from datetime import datetime

def get_video_info(file:str):
    '''Returns basic information of a video.'''
    probe = ffmpeg.probe(file)
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    avg_frame_rate = video_info['avg_frame_rate']
    if '/' in avg_frame_rate:
        a, b = avg_frame_rate.split('/')
        avg_frame_rate = float(a) / float(b)
    else:
        avg_frame_rate = float(avg_frame_rate)
    duration = float(probe['format']['duration'])
    size = float(probe['format']['size'])
    return {'avg_frame_rate': avg_frame_rate, 'duration': duration, 'size': size}

def default_output_rule(input:str):
    '''Defines the format of output screenshots according to the input video.'''
    filename, _ = os.path.splitext(input)
    return f'{filename}_cap.png'

def capture_file(file:str, args, output_rule=None):
    '''Captures a video according to arguments.'''
    if not output_rule:
        output_rule = default_output_rule
    
    try:
        info = get_video_info(file)
        total = info['duration'] * info['avg_frame_rate']
        c, r = args.tile.split('x')
        interval = total // (int(r) * int(c))
        size = info['size'] / (1024 * 1024)
            
        output_name = output_rule(file)
        if not args.overwrite:
            if os.path.exists(output_name):
                logger.info(f'{output_name} already exists and overwrite is set to false. Skipping this.')
                return None
    except Exception:
        logger.error(format_exc())
        logger.info(f'Failed to get info of {file}.')
        return None
        
    try:
        begin = datetime.now()
        logger.info(f"Begin capturing {file}. Size: {size:.2f} MB.")
        (ffmpeg
            .input(file, ss=args.seek)
            .filter('select', f'not(mod(n, {interval}))')
            .filter('scale', args.width, -1)
            .filter('tile', args.tile)
            # **{'loglevel': 'error'} is for less output
            .output(output_name, vframes=1, **{'loglevel': 'error'})
            .overwrite_output()
            .run(capture_stdout=True))
        end = datetime.now()
        logger.info(f'Finished capturing {file}. Time elapsed: {end-begin}.')
        return output_name
    except Exception:
        logger.error(format_exc())
        logger.info(f'Failed to capture {file}. Time elapsed: {end-begin}.')
        return None

def capture(path:str, args, output_rule=None):
    begin = datetime.now()
    
    logger.info(f"Start task at {begin}.")
    if os.path.isdir(path):
        tree_input = inspect_dir(path)
        nodes = tree_input.walk(lambda n: (not n.is_dir()) and is_video(n.id))
        paths = [node.abs_id for node in nodes]
        logger.info("Jobs to be done:\n" + '\n'.join(paths))
        output = []
        for path in tqdm(paths):
            res = capture_file(path, args, output_rule)
            if res:
                output.append(res)
    else:
        output = capture_file(path, args, output_rule)
        
    end = datetime.now()
    logger.info(f"End task. Total time elapsed: {end-begin}")
    return output

def inspect_dir(dir:str, tree:NodeDir=None) -> NodeDir:
    if tree == None:
        tree = NodeDir(dir, None)
        
    for file in os.listdir(dir):
        filename = dir + SEP + file
        if os.path.isdir(filename):
            tree.mkdir(file)
            inspect_dir(filename, tree[file])
        elif is_video(file): 
            tree.touch(file)
            
    return tree

def sort_tree(tree:NodeDir):
    '''Remove unneeded branches in the tree.'''
    
    nodes = tree.walk()
    resort = False
    for node in nodes:
        if node.is_leaf():
            if node.is_dir():
                resort = True
                node.pop()
    if resort:
        sort_tree(tree)

def is_video(file:str) -> bool:
    return file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.flv', '.rmvb'))

if __name__ == '__main__':
    logger.add(os.path.join(os.path.dirname(__file__), 'cap_log.log'),
        rotation='16MB',
        encoding='utf-8',
        enqueue=True,
        retention='10 days')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--path', type=str, help='Path of directory or file.', required=False)
    parser.add_argument('-o', '--overwrite', action='store_true', help='Whether or not overwrite existing files.')
    parser.add_argument('-s', '--seek', type=float, default=0, help='Time of the first capture.')
    parser.add_argument('-w', '--width', type=int, default=360, help='Width of each image.')
    parser.add_argument('-t', '--tile', type=str, default='3x5', help='Tile shaple of the screen shots.')
    args = parser.parse_args()
    logger.info(f'Current arguments: {args}')
    
    if not args.path:
        logger.error(f"Path is not specified.")
        sys.exit(1)
    
    if not os.path.exists(args.path):
        logger.error(f"Path {args.path} does not exsist.")
        sys.exit(1)
    
    args.path = args.path.replace('\\', SEP)
    output = capture(args.path, args=args)
    count = 1
    if isinstance(output, list):
        count = len(output)
        output = '\n'.join(output)
        
    logger.info(f'\nCaptured: {count}\n{output}')
    
    
    