import os, sys
import ffmpeg
import argparse

from loguru import logger
from Tree import *
from traceback import format_exc
from tqdm import tqdm
from datetime import datetime, timedelta

NL = '\n'
if os.name == 'nt':
    FONTFILE = r'C:\Windows\Fonts\arial.ttf'
else:
    FONTFILE = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

def probe_file(file:str):
    '''Returns basic information of a video.'''
    if not os.path.isfile(file):
        raise FileNotFoundError(f"{file}")
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
    
    if not os.path.isfile(file):
        return file, 'invalid file path' 
    
    if not output_rule:
        output_rule = default_output_rule
    
    try:
        logger.info(f'Probing file {file}.')
        info = probe_file(file)
        total = info['duration'] * info['avg_frame_rate']
        c, r = args.tile.split('x')
        interval = total // (int(r) * int(c))
        size = info['size'] / (1024 * 1024)
            
        output_name = output_rule(file)
        if not args.overwrite:
            if os.path.exists(output_name):
                logger.info(f'{output_name} already exists and overwrite is set to false. Skipping this.')
                return file, 'skipped'
    except Exception:
        logger.error(format_exc())
        logger.info(f'Failed to get info of {file}.')
        return file, 'failed to probe'
        
    try:
        begin = datetime.now()
        info_txt = f"size: {size:.2f} MB, duration: {timedelta(seconds=info['duration'])}"
        logger.info(f'Begin capturing {file}. ({info_txt})')
        out, err = (ffmpeg
            .input(file, ss=args.seek)
            .drawtext(text=None, x='text_h', y='text_h', 
                      fontcolor='white', fontsize=60, fontfile=FONTFILE, 
                      timecode='00:00:00.00', r='30000/1001')
            .filter('select', f'not(mod(n, {interval}))')
            .filter('scale', args.width, -1)
            .filter('tile', args.tile)
            # **{'loglevel': 'error'} is for less output
            .output(output_name, **{'frames:v': 1, 'loglevel': 'error'})
            .overwrite_output()
            .run(capture_stdout=True))
       
        end = datetime.now()
        if err:
            logger.error(f'Error occured during capturing {file}:{NL}{err}')
            return file, 'error occurred'
        else:
            logger.info(f'Succeeded in capturing {file}. Time elapsed: {end-begin}.')
            return file, 'succeeded'
    except Exception:
        logger.error(format_exc())
        logger.info(f'Failed to capture {file}. Time elapsed: {end-begin}.')
        return file, 'failed to capture'

def capture(file:str, args, output_rule=None):
    begin = datetime.now()
    
    logger.info(f'Start task at {begin}.')
    if os.path.isdir(file):
        tree_input = inspect_dir(file)
        nodes = tree_input.walk(lambda n: (not n.is_dir()) and is_video(n.id))
        paths = [node.abs_id for node in nodes]
        logger.info(f'Files to be captured:' + NL + NL.join(paths))
        for file in tqdm(paths):
            yield capture_file(file, args, output_rule)
    else:
        yield capture_file(file, args, output_rule)
        
    end = datetime.now()
    logger.info(f'End task. Total time elapsed: {end-begin}.')

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
    log_file = os.path.join(os.path.dirname(__file__), 'cap_log.log')
    log_format_console = "\n<level>{message}</level>\n"
    log_format_file = (
        "[<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>] | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>\n"
        " <level>{message}</level>\n"
        )
    logger.configure(
        handlers=[
            dict(sink=sys.stderr, format=log_format_console),
            dict(sink=log_file, rotation='16MB', encoding='utf-8', enqueue=True, retention='10 days', format=log_format_file)
        ])
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--path',     type=str,   default=os.path.dirname(__file__), help='Path of directory or file.')
    parser.add_argument('-s', '--seek',     type=float, default=0,      help='Time of the first capture.')
    parser.add_argument('-w', '--width',    type=int,   default=360,    help='Width of each image.')
    parser.add_argument('-t', '--tile',     type=str,   default='5x4',  help='Tile shaple of the screen shots.')
    parser.add_argument('-o', '--overwrite',action='store_true',        help='Whether or not overwrite existing files.')
    args = parser.parse_args()
    logger.info(f'Current arguments: {args}')
    
    if not os.path.exists(args.path):
        logger.error(f'Path {args.path} does not exsist.')
        sys.exit(1)
    
    args.path = args.path.replace('\\', SEP)
    output = list(capture(args.path, args=args))
    count = 0
    for file, result in output:
        if result == 'succeeded':
            count += 1
    output = NL.join([f'{result}:\t{file}' for file, result in output])
    
    logger.info(f'Captured: {count}{NL}{output}')
    
    
    