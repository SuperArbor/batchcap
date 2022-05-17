import os, sys
import ffmpeg
import argparse

from loguru import logger
from Tree import *
from traceback import print_exc, format_exc
from io import StringIO
from datetime import datetime, timedelta
import subprocess

def get_video_info(file:str):
    logger.info(f'Getting info from file {file}')
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
    filename, _ = os.path.splitext(input)
    return f'{filename}_cap.png'

def capture_file(file:str, args, output_rule=None):
    if not output_rule:
        output_rule = default_output_rule
    
    info = get_video_info(file)
    total = info['duration'] * info['avg_frame_rate']
    r, c = args.tile.split('x')
    interval = total // (int(r) * int(c))
    size = info['size'] / (1024 * 1024)
        
    output_name = output_rule(file)
    basename = os.path.basename(output_name)
    if not args.overwrite:
        if os.path.exists(output_name):
            logger.info(f'{output_name} already exists and overwrite is set to false. Skipping this.')
            return 
        
    try:
        begin = datetime.now()
        logger.info(f"Begin handling {file}. Size: {size:.2f} MB.")
        (ffmpeg
            .input(file, ss=args.seek)
            .filter('select', f'not(mod(n, {interval}))')
            .filter('scale', args.width, -1)
            .filter('tile', args.tile)
            .output(output_name, vframes=1, **{'loglevel': 'error'})
            .overwrite_output()
            .run(capture_stdout=True))
        end = datetime.now()
        logger.info(f'Finished handling {file}. Time elapsed: {end-begin}.')

        return basename
    except Exception:
        logger.error(format_exc())
        return None

def capture(path:str, args, output_rule=None):
    begin = datetime.now()
    logger.info(f"Start task at {begin}.")
    if os.path.isdir(path):
        output = capture_dir(path, args, output_rule)
    else:
        output = capture_file(path, args, output_rule)
    end = datetime.now()
    logger.info(f"End task. Total time elapsed: {end-begin}")
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
            if(capture_file(filename, args, output_rule)):
                tree.touch(output_rule(file))
        else:
            continue
    return tree

def is_video(file:str) -> bool:
    return file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.flv', '.rmvb'))

if __name__ == '__main__':
    logger.add(os.path.join(os.path.dirname(__file__), 'cap_log.log'),
        rotation='16MB',
        encoding='utf-8',
        enqueue=True,
        retention='10 days')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory', type=str, help='Path of directory or file.', required=False)
    parser.add_argument('-o', '--overwrite', action='store_true', help='Whether or not overwrite existing files.')
    parser.add_argument('-s', '--seek', type=float, default=0, help='Time of the first capture.')
    parser.add_argument('-w', '--width', type=int, default=360, help='Width of each image.')
    parser.add_argument('-t', '--tile', type=str, default='3x5', help='Tile shaple of the screen shots.')
    args = parser.parse_args()
    logger.info(f'Current arguments: {args}')
    
    if not args.directory:
        args.directory = subprocess.check_output(['powershell.exe', '$PWD.Path'], stderr=subprocess.STDOUT).decode('utf-8').strip()
        logger.info(f'Set directory as: {args.directory}')
        
    output = capture(args.directory, args=args)
    buff = StringIO(str(output))
    count = 0
    while True:
        line = buff.readline()
        if line.startswith('-'):
            count += 1
        else:
            break
        
    logger.info(f'\nCaptured: {count}\n{output}')
    
    
    