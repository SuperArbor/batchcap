from enum import Enum
import os, sys, tempfile
import json, re
import psutil
import argparse
from subprocess import Popen, PIPE
from loguru import logger
from Tree import *
from traceback import format_exc
from tqdm import tqdm
from datetime import datetime, timedelta
from fractions import Fraction

NL = '\n'
MIN_FONTSIZE = 1
MAX_FONTSIZE = 999
DEFAULT_FONTSIZE = 20
DEFAULT_HEIGHT = 360
FONTCOLOR = 'yellow'
MAX_LOG_LENGTH = 2048
MEMORY_PARA = 6
MIN_FFMPEG_MAIN_VERSION = 5

if os.name == 'nt':
    FONTFILE = 'C:/Windows/Fonts/arial.ttf'
else:
    FONTFILE = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

def debugger_is_active() -> bool:
    """Return if the debugger is currently active"""
    gettrace = getattr(sys, 'gettrace', lambda : None) 
    return gettrace() is not None

class AsyncError(Exception):
    def __init__(self, cmd:str, out, err) -> None:
        self.cmd = cmd
        self.out = out
        self.err = err
    def __repr__(self) -> str:
        return self.cmd + ' error'

class CaptureResult(Enum):
    SUCCEEDED = 0
    PROBE_FAILED = -1
    CAPTURE_ERROR_OCCURED = 1
    CAPTURE_SKIPPED = 2
    CAPTURE_FAILED = -2
    
    def __str__(self) -> str:
        return self.name

def run_async(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, multiple=False):
    '''Call the command(s) in another process.
    multiple: whether there are more than one commands in cmds to be chained by pipes.
    '''
    if multiple:
        process = None
        for cmd in args:
            if process:
                process = Popen(cmd, stdin=process.stdout, stdout=stdout, stderr=stderr)
            else:
                process = Popen(cmd, stdin=stdin, stdout=stdout, stderr=stderr)
    else:
        process = Popen(args, stdin=stdin, stdout=stdout, stderr=stderr)
    
    out, err = process.communicate()
    out, err = out.decode('utf-8'), err.decode('utf-8')
    retcode = process.poll()
    if retcode != 0:
        cmd = 'unknown'
        if isinstance(args, list):
            if len(args) > 0:
                cmd = args[0]
        elif isinstance(args, str):
            cmd = args
        raise AsyncError(cmd, out, err)
    return out, err

def probe_file(file:str):
    '''Returns basic information of a video.'''
    if not os.path.isfile(file):
        raise FileNotFoundError(f"{file}")
    args = ['ffprobe', '-show_format', '-show_streams', '-loglevel', 'error', '-of', 'json', file]
    
    out, err = run_async(args)
    if err:
        logger.error(f'Error occured during probing {file}:{NL}{suppress_log(err)}')
        
    probe = json.loads(out)
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    try:
        avg_frame_rate = Fraction(video_info['avg_frame_rate'])
        frame_rate = float(avg_frame_rate.numerator / avg_frame_rate.denominator)
    except ZeroDivisionError:
        r_frame_rate = Fraction(video_info['r_frame_rate'])
        frame_rate = float(r_frame_rate.numerator / r_frame_rate.denominator)
        
    width, height = int(video_info['width']), int(video_info['height'])
    duration = float(probe['format']['duration'])
    size = float(probe['format']['size'])
    return {'avg_frame_rate': frame_rate, 'width': width, 'height': height, 'duration': duration, 'size': size}

def default_output_rule(file:str):
    '''Defines the format of output screenshots according to the input video.'''
    return f'{file}.cap.png'

def suppress_log(message:str, max_length=MAX_LOG_LENGTH):
    '''Suppress logging output in case the content is too long.'''
    if len(message) <= max_length:
        return message
    else:
        return message[:max_length] + '...'

def escape_chars(text, chars, escape='\\'):
    """Helper function to escape uncomfortable characters."""
    text = str(text)
    chars = list(set(chars))
    if '\\' in chars:
        chars.remove('\\')
        chars.insert(0, '\\')
    for ch in chars:
        text = text.replace(ch, escape + ch)
    return text

def capture_file_once(file:str, args, capture_info:dict):
    '''Captures a video according to arguments.
    
    It is done by generating a command and use subprocess to run it. 
    The command will be something like:
    
    ['ffmpeg', 
        '-ss', '10.0', '-i', 'video.mkv', 
        '-ss', '133.86', '-i', 'video.mkv', 
        '-filter_complex', 
            '[0:v:0]scale=-1:360[a0];[a0]drawtext=fontcolor=yellow:fontfile=C\\\\:/Windows/Fonts/arial.ttf:fontsize=20:text=0\\\\:00\\\\:10:x=text_h:y=text_h[v0];
            [1:v:0]scale=-1:360[a1];[a1]drawtext=fontcolor=yellow:fontfile=C\\\\:/Windows/Fonts/arial.ttf:fontsize=20:text=0\\\\:02\\\\:13.860000:x=text_h:y=text_h[v1];
            [v0][v1]xstack=inputs=2:layout=0_0.0|360_0.0[c]', 
        '-map', '[c]', 
        '-frames:v', '1', 
        '-loglevel', 'error', 
        'video_cap.png', 
        '-y']
    
    Some of the arguments, like the 'text=0\\\\:00\\\\:10' is calculated in the code.
    
    Another way to do this is:
    
    ['ffmpeg',
        '-i', 'video.mkv', 
        '-filter_complex', 
            '[0]select=not(mod(n - 0\, 308.0)) * not(lt(n\, 0))[s0];[s0]scale=-1:360[s1];[s1]tile=5x4[s2]',
        '-map', [s2],
        '-frames:v', '1', 
        '-loglevel', 'error', 
        'video_cap.png',
        '-y']
    
    Though looking much easier, the second way is computationally expensive.
    '''
    try:
        output_name = capture_info['output_name']
        seek = capture_info['seek']
        interval = capture_info['interval']
        width, height = capture_info['width'], capture_info['height']
        c, r = capture_info['columns'], capture_info['rows']
        
        # Generating command
        cmd = ['ffmpeg']
        for i in range(c * r):
            cmd.extend(['-ss', f'{seek + i*interval}', '-i', file])
        
        cmd.append('-filter_complex')
        if args.timestamp:
            fontfile = escape_chars(FONTFILE, r"\' =:", r'\\')
            fontsize = min(max(DEFAULT_FONTSIZE * height // DEFAULT_HEIGHT, MIN_FONTSIZE), MAX_FONTSIZE)
            def get_timestamp(t):
                h, m, s = str(timedelta(seconds=t)).split(':')
                t = f'{h}:{m}:{float(s):.3f}'
                return escape_chars(t, r"\'=:", r'\\')
            cmd.append (
                        ''.join([f'[{i}:v:0]scale=-1:{args.height}[a{i}];[a{i}]drawtext=fontcolor={FONTCOLOR}:fontfile={fontfile}:fontsize={fontsize}:text={get_timestamp(seek + i*interval)}:x=text_h:y=text_h[v{i}];' for i in range(c * r)]) 
                        + ''.join([f'[v{i}]' for i in range(c * r)])
                        + f'xstack=inputs={c * r}:layout='
                        + '|'.join([f'{i * width}_{j * height}' for j in range(r) for i in range(c)])
                        + '[c]')
        else:
            cmd.append (
                        ''.join([f'[{i}:v:0]scale=-1:{args.height}[v{i}];' for i in range(c * r)]) 
                        + ''.join([f'[v{i}]' for i in range(c * r)])
                        + f'xstack=inputs={c * r}:layout='
                        + '|'.join([f'{i * width}_{j * height}' for j in range(r) for i in range(c)])
                        + '[c]')
            
        cmd.extend(['-map', '[c]'])
        cmd.extend(['-frames:v', '1'])
        cmd.extend(['-loglevel', 'error'])
        if args.overwrite:
            cmd.extend([output_name, '-y'])
        else:
            cmd.extend([output_name])
        
        _, err = run_async(cmd)
        if err:
            logger.error(f'Error occured during capturing {file}:{NL}{suppress_log(err)}')
            return CaptureResult.CAPTURE_ERROR_OCCURED
        else:
            logger.info(f'Succeeded in capturing {file}.')
            return CaptureResult.SUCCEEDED
    except Exception:
        logger.error(suppress_log(format_exc()))
        logger.info(f'Failed to capture {file}.')
        return CaptureResult.CAPTURE_FAILED

def capture_file_in_sequence(file:str, args, capture_info:dict):
    '''Captures a video according to arguments.
    To avoid memory shortage or when the command generated in capture_file_once is too long, 
    the task is accomplished by splitting the command to several sub commands.
    '''
    try:
        try:
            # Generating command
            output_name = capture_info['output_name']
            seek = capture_info['seek']
            interval = capture_info['interval']
            width, height = capture_info['width'], capture_info['height']
            c, r = capture_info['columns'], capture_info['rows']
            
            tmp_files = []
            tmp_dir = tempfile.gettempdir()
            # Generating images
            for i in range(c * r):
                captured = os.path.join(tmp_dir, f'{os.path.basename(output_name)}_{i}').replace('\\', SEP)
                cmd = ['ffmpeg', 
                        '-ss', f'{seek + i*interval}', '-i', file, 
                        '-filter_complex', f'[0:v:0]scale=-1:{args.height}[c]', 
                        '-map', '[c]', 
                        '-frames:v', '1', 
                        '-loglevel', 'error', 
                        '-f', 'image2', 
                        captured, '-y']
                if args.overwrite:
                    cmd.append('-y')
                _, err = run_async(cmd)
                tmp_files.append(captured)
        except Exception as e:
            [os.remove(f) for f in tmp_files]
            raise e
        
        try:
             # Generating stacking command
            cmd = ['ffmpeg']
            for i in range(c * r):
                cmd.extend(['-f', 'image2', '-i', tmp_files[i]])
            cmd.append('-filter_complex')
            if args.timestamp:
                fontfile = escape_chars(FONTFILE, r"\' =:", r'\\')
                fontsize = min(max(DEFAULT_FONTSIZE * height // DEFAULT_HEIGHT, MIN_FONTSIZE), MAX_FONTSIZE)
                def get_timestamp(t):
                    h, m, s = str(timedelta(seconds=t)).split(':')
                    t = f'{h}:{m}:{float(s):.3f}'
                    return escape_chars(t, r"\'=:", r'\\')
                cmd.append (
                            ''.join([f'[{i}]drawtext=fontcolor={FONTCOLOR}:fontfile={fontfile}:fontsize={fontsize}:text={get_timestamp(seek + i*interval)}:x=text_h:y=text_h[v{i}];' for i in range(c * r)]) 
                            + ''.join([f'[v{i}]' for i in range(c * r)])
                            + f'xstack=inputs={c * r}:layout='
                            + '|'.join([f'{i * width}_{j * height}' for j in range(r) for i in range(c)])
                            + '[c]')
            else:
                cmd.append (
                            ''.join([f'[{i}]' for i in range(c * r)])
                            + f'xstack=inputs={c * r}:layout='
                            + '|'.join([f'{i * width}_{j * height}' for j in range(r) for i in range(c)])
                            + '[c]')
                
            cmd.extend(['-map', '[c]'])
            cmd.extend(['-loglevel', 'error'])
            if args.overwrite:
                cmd.extend([output_name, '-y'])
            else:
                cmd.extend([output_name])
            
            # Run stacking command
            _, err = run_async(cmd)
            
            if err:
                logger.error(f'Error occured during capturing {file}:{NL}{suppress_log(err)}')
                return CaptureResult.CAPTURE_ERROR_OCCURED
            else:
                logger.info(f'Succeeded in capturing {file}.')
                return CaptureResult.SUCCEEDED
        except Exception as e:
            raise e
        finally:
            [os.remove(f) for f in tmp_files]
    except Exception:
        logger.error(suppress_log(format_exc()))
        logger.info(f'Failed to capture {file}.')
        return CaptureResult.CAPTURE_FAILED

def capture_file_in_sequence_(file:str, args, capture_info:dict):
    '''Good idea but there are several problems.
    To avoid memory shortage or when the command generated in capture_file_once is too long, 
    the task is accomplished by splitting the command to several sub commands.
    '''
    def generate_inputs(f:str, c:int, r:int, i:int):
        '''f: input file; c: columns; r: rows; i: index'''
        if i == 0:
            inputs = ['-ss', f'{seek + i*interval}', '-i', f]
        else:
            # -ss in the following commands make the task fail
            inputs = ['-ss', f'{seek + i*interval}', '-i', f, '-i', '-']
            
        return inputs
        
    def generate_filter(c:int, r:int, w:int, h:int, ts:bool, i:int):
        '''c: columns; r: rows; w: width; h: height; ts: timestamp; i: index'''
        if ts:
            fontfile = escape_chars(FONTFILE, r"\' =:", r'\\')
            fontsize = min(max(DEFAULT_FONTSIZE * h // DEFAULT_HEIGHT, MIN_FONTSIZE), MAX_FONTSIZE)
            def get_timestamp(t):
                h, m, s = str(timedelta(seconds=t)).split(':')
                t = f'{h}:{m}:{float(s):.3f}'
                return escape_chars(t, r"\'=:", r'\\')
        filter = ['-filter_complex']
        
        if i == 0:
            if ts:
                filter.append(f'[0:v:0]scale=-1:{h}[a];[a]drawtext=fontcolor={FONTCOLOR}:fontfile={fontfile}:fontsize={fontsize}:text={get_timestamp(seek + i*interval)}:x=text_h:y=text_h[v];[v]pad=iw*{c}:ih*{r}:0:0[c]')
            else:
                filter.append(f'[0:v:0]scale=-1:{h}[v];[v]pad=iw*{c}:ih*{r}:0:0[c]')
        else:
            if ts:
                filter.append(f'[0:v:0]scale=-1:{h}[a];[a]drawtext=fontcolor={FONTCOLOR}:fontfile={fontfile}:fontsize={fontsize}:text={get_timestamp(seek + i*interval)}:x=text_h:y=text_h[v];[1][v]overlay={i%c * w}:{i//c * h}[c]')
            else:
                filter.append(f'[0:v:0]scale=-1:{h}[v];[1][v]overlay={i%c * w}:{i//c * h}[c]')
            
        return filter
    
    def generate_output(o:str, c:int, r:int, ow:bool, i:int):
        '''o: output file; c: columns; r: rows; ow: overwrite; i: index'''
        if i != c * r - 1:
            output = ['-f', 'image2pipe', '-']
        else:
            output = ['-f', 'image2', o]
            if ow:
                output.append('-y')
        return output
            
    try:
        # Generating first command
        output_name = capture_info['output_name']
        seek = capture_info['seek']
        interval = capture_info['interval']
        width, height = capture_info['width'], capture_info['height']
        columns, rows = capture_info['columns'], capture_info['rows']
        
        cmds = []
        for i in range(0, columns * rows):
            cmd = ['ffmpeg']
            cmd.extend(generate_inputs(file, columns, rows, i)) 
            cmd.extend(generate_filter(columns, rows, width, height, args.timestamp, i))
            cmd.extend(['-map', '[c]', '-frames:v', '1', '-loglevel', 'error'])
            cmd.extend(generate_output(output_name, columns, rows, args.overwrite, i))
            cmds.append(cmd)
        
        # Run commands
        _, err = run_async(cmds, multiple=True)
        
        if err:
            logger.error(f'Error occured during capturing {file}:{NL}{suppress_log(err)}')
            return CaptureResult.CAPTURE_ERROR_OCCURED
        else:
            logger.info(f'Succeeded in capturing {file}.')
            return CaptureResult.SUCCEEDED
    except Exception:
        logger.error(suppress_log(format_exc()))
        logger.info(f'Failed to capture {file}.')
        return CaptureResult.CAPTURE_FAILED

def capture_file(file:str, args, output_rule=None):
    '''Probe and capture a file.'''
    if not os.path.isfile(file):
        logger.error(f'Specified file {file} does not exist.')
        return file, CaptureResult.PROBE_FAILED
    
    if not output_rule:
        output_rule = default_output_rule
    # Check if a file with the same name to the output exists.
    output_name = output_rule(file)
    if not args.overwrite:
        if os.path.exists(output_name):
            logger.info(f'{output_name} already exists and overwrite is set to false. Skipping this.')
            return file, CaptureResult.CAPTURE_SKIPPED
    
    begin = datetime.now()
    try:
        # Probe file info.
        logger.info(f'Probing file {file}...')
        info = probe_file(file)
        
        duration = info['duration']
        seek = args.seek
        c, r = args.tile.split('x')
        c, r = int(c), int(r)
        interval = (duration - seek) / (c * r)
        size = info['size'] / (1024 * 1024)
        width, height = info['width'] * args.height / info['height'], args.height
        
        if duration < seek:
            raise ValueError(f'Invalid argument "-s/--seek". Total duration {duration} less than specified seek value {args.seek}.')
        
        info_txt = f"size: {size:.2f} MB, duration: {timedelta(seconds=info['duration'])}, ratio: { info['width']} x {info['height']}, average frame rate: {info['avg_frame_rate']:.3f}"
    except Exception:
        logger.error(suppress_log(format_exc()))
        logger.info(f'Failed to probe {file}.')
        return file, CaptureResult.PROBE_FAILED
    
    logger.info(f'Begin capturing {file} ({info_txt})...')
    capture_info = {'seek': seek, 'output_name': output_name, 'interval': interval, 'columns':c, 'rows':r, 'width': width, 'height': height}
    available_memory = psutil.virtual_memory().available / (1024 * 1024)
    
    # Select a method according to the file size and the current available memory
    if available_memory * MEMORY_PARA  > (size * c * r):
        logger.info(f'Capturing {file} in one command.')
        result = capture_file_once(file, args, capture_info)
    else:
        logger.info(f'Capturing {file} in splitted commands.')
        result = capture_file_in_sequence(file, args, capture_info)
    logger.info(f'Time elapsed: {datetime.now()-begin}.')
    return file, result

def capture(file:str, args, output_rule=None):
    begin = datetime.now()
    
    logger.info(f'Start task at {begin}.')
    if os.path.isdir(file):
        tree_input = inspect_dir(file)
        nodes = tree_input.walk(lambda n: (not n.is_dir()) and is_video(n.id))
        paths = [node.abs_id for node in nodes]
        if not paths:
            logger.warning(f'No files to be captured.')
            return
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

def check_ffmpeg():
    cmd = ['ffmpeg', '-version']
    try:
        out, _ = run_async(cmd)
        search = re.search(r'ffmpeg version (\d.\d.\d)', out, re.I | re.M)
        if search:
            version = search.group(1)
            main_version = int(version.split('.')[0])
            return main_version >= MIN_FFMPEG_MAIN_VERSION, version
        else:
            return False, 'unknown'
    except:
        return False, 'uninstalled'

if __name__ == '__main__':
    valid, version = check_ffmpeg()
    if valid:
        logger.info(f'ffmpeg {version} available.')
    else:
        logger.error(f'Not able to find a valid ffmpeg. ffmpeg with minimal version {MIN_FFMPEG_MAIN_VERSION} is required. The ffmpeg installed is {version}.')
        sys.exit(1)
    
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
    parser.add_argument('-p', '--path',     type=str,   default=os.path.dirname(__file__),  help='Path of directory or file.')
    parser.add_argument('-s', '--seek',     type=float, default=0,                          help='Time of the first capture.')
    parser.add_argument('-g', '--height',   type=int,   default=270,                        help='Height of each image in the capture.')
    parser.add_argument('-t', '--tile',     type=str,   default='5x4',                      help='Tile shaple of the screen shots.')
    parser.add_argument('-o', '--overwrite',action='store_true',                            help='Whether or not overwrite existing files.')
    parser.add_argument('-i', '--timestamp',action='store_true',                            help='Whether or not show present timestamp on captures.')
    
    args = parser.parse_args()
    logger.info(f'Current arguments: {args}')
    
    try:
        if not os.path.exists(args.path):
            logger.error(f'Invalid argument "-p/--path". Path {args.path} does not exsist.')
            sys.exit(1)
        if args.height < 0:
            logger.error(f'Invalid argument "-g/--height". Height {args.height} invalid.')
            sys.exit(1)
        if args.seek < 0:
            logger.error(f'Invalid argument "-s/--seek". Seek {args.seek} invalid.')
            sys.exit(1)
        c, r = args.tile.split('x')
        c, r = int(c), int(r)
        if c < 1 or r < 1:
            logger.error(f'Invalid argument "-t/--tile". Tile {args.tile} invalid.')
            sys.exit(1)
        if debugger_is_active():
            args.overwrite = True
            args.timestamp = True
    except Exception:
        logger.error(f'Failed to parse arguments.')
        sys.exit(1)
    
    args.path = args.path.replace('\\', SEP)
    output = list(capture(args.path, args=args))
    if output:
        count_succeeded = 0
        count_failed = 0
        count_skipped = 0
        count_error = 0
        for file, result in output:
            if result == CaptureResult.SUCCEEDED:
                count_succeeded += 1
            elif result == CaptureResult.CAPTURE_SKIPPED:
                count_skipped += 1
            elif result == CaptureResult.CAPTURE_ERROR_OCCURED:
                count_error += 1
            else:
                count_failed += 1
            
        logger.info(f'Succeeded: {count_succeeded}{NL}' 
                    + f'Skipped: {count_skipped}{NL}' 
                    + f'Completed with error: {count_error}{NL}' 
                    + f'Failed: {count_failed}')
        
        logger.info(NL.join([f'{result}:\t{file}' for file, result in output]))
    
    
    