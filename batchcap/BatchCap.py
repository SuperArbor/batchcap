import os, sys, tempfile, json, shutil, argparse, glob
from enum import Enum
from subprocess import Popen, PIPE
from traceback import format_exc
from tqdm import tqdm
from datetime import datetime, timedelta
from fractions import Fraction
from collections.abc import Iterable

import psutil
from .Logger import *

# Global constants
NL = os.linesep
MIN_FONTSIZE = 1
MAX_FONTSIZE = 999
MAX_LOG_LENGTH = 2048           # Maximum length of an entry of logging
MEMORY_PARA = 4                 # Coefficient to decide the capture method to call
MAX_COMMAND_LENGTH = 20000      # Maximum length of the command for the system to run
REQUIRED_FILTERS = {
    "scale",
    "drawtext",
    "format",
    "pad",
    "xstack",
    "tile",
    "select",
    "trim",
}
VIDEO_EXT = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.flv', '.rmvb', '.rm', '.ts', '.m2ts'}
FFMPEG = None
FFPROBE = None

# logger
LOGGER = logging.getLogger("batchcap")
LOGGER.setLevel(logging.DEBUG)
LOGGER.propagate = False
console = logging.StreamHandler(sys.stderr)
console.setFormatter(ConsoleColorFormatter("%(message)s"))
LOGGER.addHandler(console)
log_file = os.path.join(os.path.dirname(__file__), "cap_log.log")
file_fmt = (
    "[%(asctime)s] | %(levelname)-8s | %(name)s:%(lineno)d\n"
    " %(message)s\n"
)
file_h = RotatingFileHandler(
    log_file,
    maxBytes=16 * 1024 * 1024,
    backupCount=10,
    encoding="utf-8",
)
file_h.setFormatter(logging.Formatter(file_fmt))
LOGGER.addHandler(file_h)

# build parser
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs="+",  help='path of directory or file')

    parser.add_argument('-s', '--seek',     type=float,     default=0,          help='time of the first capture')
    parser.add_argument('-g', '--height',   type=int,       default=270,        help='thumbnail height')
    parser.add_argument('-t', '--tile',     type=str,       default='4x4',      help='tile shape (cols x rows)')
    parser.add_argument('-f', '--format',   type=str,       default='png',      help='output format')
    parser.add_argument('-c', '--fontcolor',type=str,       default='white',    help='font color / RGBA')
    parser.add_argument('-n', '--fontratio',type=float,     default=0.08,       help='font size ratio')
    parser.add_argument('-r', '--padratio', type=float,     default=0.01,       help='padding ratio')
    parser.add_argument('-i', '--timestamp',action='store_true',                help='add timestamp on the thumbnail')
    parser.add_argument('-o', '--overwrite',action='store_true',                help='overwrite existing files')
    parser.add_argument('-v', '--verbose',  action='store_true',                help='verbose output')

    return parser

parser = build_parser()

if os.name == 'nt':
    FONTFILE = 'C:/Windows/Fonts/arial.ttf'
else:
    FONTFILE = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

class AsyncError(Exception):
    def __init__(self, cmd, out, err, retcode):
        self.cmd = cmd
        self.out = out
        self.err = err
        self.retcode = retcode
        super().__init__(f"{cmd} exited {retcode}: {err.strip().splitlines()[0]}")
        
    def __repr__(self) -> str:
        return self.cmd + f' exited {self.retcode}'

class CaptureResult(Enum):
    SUCCEEDED = 0
    SKIPPED = 1
    PROBE_FAILED = -1
    CAPTURE_ERROR_OCCURED = -2
    CAPTURE_FAILED = -3
    
    def __str__(self) -> str:
        return self.name

def run_async(
    args,
    stdin=PIPE, stdout=PIPE, stderr=PIPE,
    multiple=False,
    verbose=False,) -> tuple[int, str, str]:
    """
    return: (retcode, stdout, stderr)
    """

    last_proc = None

    if multiple:
        prev = stdin
        for i, cmd in enumerate(args):
            if verbose:
                LOGGER.info(f'Running command: {" ".join(cmd)}')
            last_proc = Popen(
                cmd,
                stdin=prev,
                stdout=PIPE if i != len(args)-1 else stdout,
                stderr=stderr,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            prev = last_proc.stdout
    else:
        if verbose:
            LOGGER.info(f'Running command: {args}')
        last_proc = Popen(
            args,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

    out, err = last_proc.communicate()
    retcode = last_proc.returncode

    if retcode != 0:
        cmd_name = args[0][0] if multiple else args[0]
        raise AsyncError(cmd_name, out, err, retcode)

    return retcode, out, err

def probe_file(file:str, args) -> dict:
    '''Returns basic information of a video.'''
    cmd = [FFPROBE, '-show_format', '-show_streams', '-loglevel', 'error', '-of', 'json', file]
    
    _, out, err = run_async(cmd, verbose=args.verbose)
    if err:
        LOGGER.error(f'Error occured during probing {file}:{NL}{suppress_log(err)}')
        
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

def suppress_log(message:str, max_length=MAX_LOG_LENGTH) -> str:
    '''Suppress logging output in case the content is too long.'''
    if len(message) <= max_length:
        return message
    else:
        return message[:max_length] + '...'

def escape_chars(text, chars, escape='\\') -> str:
    """Helper function to escape uncomfortable characters."""
    text = str(text)
    chars = list(set(chars))
    if '\\' in chars:
        chars.remove('\\')
        chars.insert(0, '\\')
    for ch in chars:
        text = text.replace(ch, escape + ch)
    return text

def capture_file_once_cmd(file:str, args, capture_info:dict) -> list:
    r'''Get the command to capture a video according to arguments.
    
    It is done by generating a command and use subprocess to run it. 
    The command will be something like:
    
    ['ffmpeg', 
        '-ss', '10.0', '-i', 'video.mkv', 
        '-ss', '133.86', '-i', 'video.mkv', 
        '-filter_complex', 
            '[0:v:0]scale=-1:270[a0];[a0]drawtext=fontcolor=yellow:fontfile=C\\\\:/Windows/Fonts/arial.ttf:fontsize=20:text=0\\\\:00\\\\:10:x=text_h:y=text_h[v0];
            [1:v:0]scale=-1:270[a1];[a1]drawtext=fontcolor=yellow:fontfile=C\\\\:/Windows/Fonts/arial.ttf:fontsize=20:text=0\\\\:02\\\\:13.860000:x=text_h:y=text_h[v1];
            [v0][v1]xstack=inputs=2:layout=0_0.0|270_0.0[c]', 
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
            '[0]select=not(mod(n - 0\, 308.0)) * not(lt(n\, 0))[s0];[s0]scale=-1:270[s1];[s1]tile=4x4[s2]',
        '-map', [s2],
        '-frames:v', '1', 
        '-loglevel', 'error', 
        'video_cap.png',
        '-y']
    
    Though looking much easier, the second way is computationally expensive.
    '''
    output_name = capture_info['output_name']
    seek = capture_info['seek']
    interval = capture_info['interval']
    width, height = capture_info['width'], capture_info['height']
    c, r = capture_info['columns'], capture_info['rows']
    pad = capture_info['pad']
    fontsize = capture_info['fontsize']
    
    # Generating command
    cmd = [FFMPEG]
    for i in range(c * r):
        cmd.extend(['-ss', f'{seek + i*interval}', '-i', file])
    
    cmd.append('-filter_complex')
    if args.timestamp:
        fontfile = escape_chars(FONTFILE, r"\' =:", r'\\')
        def get_timestamp(t):
            h, m, s = str(timedelta(seconds=t)).split(':')
            t = f'{h}:{m}:{float(s):.3f}'
            return escape_chars(t, r"\'=:", r'\\')
        cmd.append (
                    ''.join([f'[{i}:v:0]scale=-1:{args.height}[a{i}];\
                                [a{i}]drawtext=fontcolor={args.fontcolor}:fontfile={fontfile}:fontsize={fontsize}:text={get_timestamp(seek + i*interval)}:x=text_h:y=text_h[b{i}];\
                                [b{i}]format=rgba[c{i}];[c{i}]pad=iw+2*{pad}:ih+2*{pad}:{pad}:{pad}:color=#00000000[v{i}];' for i in range(c * r)]) 
                    + ''.join([f'[v{i}]' for i in range(c * r)])
                    + f'xstack=inputs={c * r}:layout='
                    + '|'.join([f'{i * (width + pad * 2)}_{j * (height + pad * 2)}' for j in range(r) for i in range(c)])
                    + '[c]')
    else:
        cmd.append (
                    ''.join([f'[{i}:v:0]scale=-1:{args.height}[b{i}];\
                            [b{i}]format=rgba[c{i}];[c{i}]pad=iw+2*{pad}:ih+2*{pad}:{pad}:{pad}:color=#00000000[v{i}];' for i in range(c * r)]) 
                    + ''.join([f'[v{i}]' for i in range(c * r)])
                    + f'xstack=inputs={c * r}:layout='
                    + '|'.join([f'{i * (width + pad * 2)}_{j * (height + pad * 2)}' for j in range(r) for i in range(c)])
                    + '[c]')
        
    cmd.extend(['-map', '[c]'])
    cmd.extend(['-frames:v', '1'])
    cmd.extend(['-loglevel', 'error'])
    if args.overwrite:
        cmd.extend([output_name, '-y'])
    else:
        cmd.extend([output_name])
    return cmd

def capture_file_in_sequence(file:str, args, capture_info:dict) -> CaptureResult:
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
            pad = capture_info['pad']
            fontsize = capture_info['fontsize']

            tmp_files = []
            tmp_dir = tempfile.gettempdir()

            # Generating images
            for i in range(c * r):
                captured = os.path.join(tmp_dir, f'{os.path.basename(output_name)}_{i}')

                cmd = [
                    FFMPEG,
                    '-ss', f'{seek + i * interval}',
                    '-i', file,
                    '-filter_complex', f'[0:v:0]scale=-1:{args.height}[c]',
                    '-map', '[c]',
                    '-frames:v', '1',
                    '-loglevel', 'error',
                    '-c:v', 'png',
                    '-f', 'image2',
                    captured
                ]

                if args.overwrite:
                    cmd.append('-y')

                _, _, err = run_async(cmd, verbose=args.verbose)

                if err:
                    LOGGER.warning(
                        f'Failed to capture frame {i} at '
                        f'{seek + i * interval:.3f}s.{NL}{suppress_log(err)}'
                    )

                # FFmpeg may exit successfully without producing an output frame.
                if not os.path.exists(captured):
                    LOGGER.warning(
                        f'No frame captured at {seek + i * interval:.3f}s, '
                        f'using a transparent placeholder.'
                    )

                    # Generate a transparent RGBA PNG with the same dimensions.
                    placeholder_cmd = [
                        FFMPEG,
                        '-f', 'lavfi',
                        '-i', f'color=c=black@0.0:s={width}x{height}:r=1',
                        '-frames:v', '1',
                        '-vf', 'format=rgba',
                        '-c:v', 'png',
                        '-f', 'image2',
                        captured,
                    ]

                    if args.overwrite:
                        placeholder_cmd.append('-y')

                    run_async(placeholder_cmd, verbose=args.verbose)

                if not os.path.exists(captured):
                    LOGGER.error(
                        f'Failed to create placeholder image: {captured}'
                    )
                    return CaptureResult.CAPTURE_ERROR_OCCURED

                tmp_files.append(captured)

        except Exception as e:
            [os.remove(f) for f in tmp_files if os.path.exists(f)]
            raise e
        
        try:
             # Generating stacking command
            cmd = [FFMPEG]
            for i in range(c * r):
                cmd.extend(['-f', 'image2', '-i', tmp_files[i]])
            cmd.append('-filter_complex')
            if args.timestamp:
                fontfile = escape_chars(FONTFILE, r"\' =:", r'\\')
                def get_timestamp(t):
                    h, m, s = str(timedelta(seconds=t)).split(':')
                    t = f'{h}:{m}:{float(s):.3f}'
                    return escape_chars(t, r"\'=:", r'\\')
                cmd.append (
                            ''.join([f'[{i}]drawtext=fontcolor={args.fontcolor}:fontfile={fontfile}:fontsize={fontsize}:text={get_timestamp(seek + i*interval)}:x=text_h:y=text_h[b{i}];\
                                    [b{i}]format=rgba[c{i}];[c{i}]pad=iw+2*{pad}:ih+2*{pad}:{pad}:{pad}:color=#00000000[v{i}];' for i in range(c * r)]) 
                            + ''.join([f'[v{i}]' for i in range(c * r)])
                            + f'xstack=inputs={c * r}:layout='
                            + '|'.join([f'{i * (width + 2 * pad)}_{j * (height + 2 * pad)}' for j in range(r) for i in range(c)])
                            + '[c]')
            else:
                cmd.append (
                            ''.join([f'[{i}]format=rgba[c{i}];[c{i}]pad=iw+2*{pad}:ih+2*{pad}:{pad}:{pad}:color=#00000000[v{i}];' for i in range(c * r)]) 
                            + ''.join([f'[v{i}]' for i in range(c * r)])
                            + f'xstack=inputs={c * r}:layout='
                            + '|'.join([f'{i * (width + 2 * pad)}_{j * (height + 2 * pad)}' for j in range(r) for i in range(c)])
                            + '[c]')
                
            cmd.extend(['-map', '[c]'])
            cmd.extend(['-loglevel', 'error'])
            if args.overwrite:
                cmd.extend([output_name, '-y'])
            else:
                cmd.extend([output_name])
            
            retcode, _, err = run_async(cmd, verbose=args.verbose)
            
            if retcode != 0:
                if "already exists" in err and not args.overwrite:
                    LOGGER.info("Output exists, skipping. Use -o/--overwrite to overwrite.")
                    return CaptureResult.SKIPPED
                else:
                    LOGGER.error(f'Error occured.{NL}{suppress_log(err)}')
                    return CaptureResult.CAPTURE_ERROR_OCCURED
            else:
                LOGGER.info(f'Succeeded.')
                return CaptureResult.SUCCEEDED
        except Exception as e:
            raise e
        finally:
            [os.remove(f) for f in tmp_files]
    except Exception:
        LOGGER.error(suppress_log(format_exc()))
        LOGGER.info(f'Failed to capture {file}.')
        return CaptureResult.CAPTURE_FAILED

def capture_file(file:str, args) -> tuple[str, CaptureResult]:
    '''Probe and capture a file.
    There are two ways to do that.
    (1) Compile the task into one command and run it once;
    (2) Capture all the images and save them on the disk before joining them in another command.
    
    The first way is more efficient when the file is small and the number of captures (c * r) is 
    small, but it is also more memory consuming. So this method chooses one of them to execute.
    '''
    if not os.path.isfile(file):
        LOGGER.error(f'Specified file {file} does not exist.')
        return file, CaptureResult.PROBE_FAILED
    
    begin = datetime.now()
    try:
        # Probe file info.
        LOGGER.info(f'Probing file {file}...')
        info = probe_file(file, args)
        output_name = get_output_name(file, args.format)
        
        duration = info['duration']
        seek = args.seek
        c, r = args.tile.split('x')
        c, r = int(c), int(r)
        interval = (duration - seek) / (c * r)
        size = info['size'] / (1024 * 1024)
        width, height = int(info['width'] * args.height / info['height']), int(args.height)
        pad = max(int(args.padratio * min(width, height)), 0)
        fontsize = min(max(int(args.fontratio * min(width, height)), MIN_FONTSIZE), MAX_FONTSIZE)
        
        if duration < seek:
            raise ValueError(f'Invalid argument "-s/--seek". Total duration {duration} less than specified seek value {args.seek}.')
        
        info_txt = f"size: {size:.2f} MB, duration: {timedelta(seconds=info['duration'])}, ratio: { info['width']} x {info['height']}, average frame rate: {info['avg_frame_rate']:.3f}"
    except Exception:
        LOGGER.error(suppress_log(format_exc()))
        LOGGER.info(f'Failed to probe {file}.')
        return file, CaptureResult.PROBE_FAILED
    
    LOGGER.info(info_txt)
    capture_info = {
        'seek': seek, 
        'output_name': output_name, 
        'interval': interval, 
        'columns':c, 
        'rows':r, 
        'width': width, 
        'height': height, 
        'pad': pad, 
        'fontsize': fontsize
        }
    available_memory = psutil.virtual_memory().available / (1024 * 1024)
    
    # Select a method according to the file size and the current available memory
    if available_memory * MEMORY_PARA  > (size * c * r):
        LOGGER.info(f'Trying to capture {file} in one command.')
        cmd = capture_file_once_cmd(file, args, capture_info)
        sum = 0
        for c in cmd:
            sum += len(c)
        if sum < MAX_COMMAND_LENGTH:
            try:
                retcode, _, err = run_async(cmd, verbose=args.verbose)
                
                if retcode != 0:
                    if "already exists" in err and not args.overwrite:
                        LOGGER.info("Output exists, skipping. Use -o/--overwrite to overwrite.")
                        return file, CaptureResult.SKIPPED
                    else:
                        LOGGER.error(f'Error occured.{NL}{suppress_log(err)}')
                        return file, CaptureResult.CAPTURE_ERROR_OCCURED
                else:
                    LOGGER.info(f'Succeeded.')
                    return file, CaptureResult.SUCCEEDED
            except Exception:
                LOGGER.error(suppress_log(format_exc()))
                LOGGER.info(f'Failed to capture {file}.')
                result = CaptureResult.CAPTURE_FAILED
        else:
            LOGGER.info(f'Command too long. Switch to sequnce command mode.')
            result = capture_file_in_sequence(file, args, capture_info)
    else:
        LOGGER.info(f'Capturing in splitted commands according to available memory.')
        result = capture_file_in_sequence(file, args, capture_info)
    return file, result

def capture_multi(paths: list[str], args) -> Iterable[tuple[str, CaptureResult]]:
    """Capture multiple files in a directory or a list of files."""
    targets, skpipped = collect_target_files(paths, args)
    n_targets = len(targets)
    n_skipped = len(skpipped)

    LOGGER.info(f'Total files to capture: {n_targets}')
    if n_targets > 0:
        LOGGER.info(f'Target paths:{NL}' + NL.join(targets))
    LOGGER.info(f'Total files skipped: {n_skipped}')
    if n_skipped > 0:
        LOGGER.info(f'Skipped paths:{NL}' + NL.join(skpipped))

    for pth in tqdm(targets, desc="Capturing"):
        yield capture_file(pth, args)

def resolve_paths(patterns:list[str]) -> list[str]:
    paths = []
    for pat in patterns:
        matched = glob.glob(pat) if any(c in pat for c in '*?[') else None
        paths.extend(matched if matched else [pat])
    return [os.path.abspath(p) for p in paths]

def collect_target_files(
        paths: list[str],
        args
    ) -> tuple[list[str], list[str]]:
    """Collect target video files and skipped files."""

    targets = []
    skipped = []

    def process_file(path: str):
        if not is_video(path):
            return

        path = os.path.abspath(path)
        output = get_output_name(path, args.format)

        if args.overwrite or not os.path.exists(output):
            targets.append(path)
        else:
            skipped.append(path)

    def process_path(path: str):
        path = os.path.abspath(path)

        if os.path.isdir(path):
            for cur, _, files in os.walk(path):
                for f in files:
                    process_file(os.path.join(cur, f))

        else:
            process_file(path)

    for p in paths:
        process_path(p)

    return targets, skipped

def is_video(name: str) -> bool:
    return os.path.splitext(name.lower())[1] in VIDEO_EXT

def get_output_name(file:str, format:str) -> str:
    return f'{file}.cap.{format}'

def get_ffmpeg_bin() -> str:
    """return the path of the ffmpeg binary"""
    return shutil.which("ffmpeg")

def get_ffprobe_bin() -> str:
    """return the path of the ffprobe binary"""
    return shutil.which("ffprobe")

def check_ffmpeg_features(ffmpeg_bin: str) -> tuple[bool, str]:
    """
    returns a tuple of (ok, missing_filters) where:
    - ok is True if all required filters are present, False otherwise
    - reason why not ok
    """
    if not ffmpeg_bin:
        return False, "ffmpeg not found in PATH"

    _, out, _ = run_async([ffmpeg_bin, "-version"])
    if "ffmpeg version" not in out.lower():
        return False, "ffmpeg binary broken"

    _, flist, _ = run_async([ffmpeg_bin, "-filters"])

    def has_filter(name) -> bool:
        for line in flist.splitlines():
            cols = line.strip().split()
            if cols and cols[0] == name:
                return True
            if cols and len(cols) > 1 and name in cols[1]:
                return True
        return False

    missing = []
    for f in REQUIRED_FILTERS:
        if not has_filter(f):
            missing.append(f)

    if missing:
        return False, f"Missing filters: {', '.join(missing)}"

    return True, ""


def main():
    global FFMPEG, FFPROBE
    # check FFmpeg and FFprobe
    FFMPEG = get_ffmpeg_bin()
    
    if FFMPEG:
        LOGGER.info(f'Using FFmpeg: {FFMPEG}.')
    else:
        LOGGER.error(f'FFmpeg not found in PATH. Please install FFmpeg and add it to PATH.')
        sys.exit(1)
        
    FFPROBE = get_ffprobe_bin()
    if FFPROBE:
        LOGGER.info(f'Using FFprobe: {FFPROBE}.')
    else:
        LOGGER.error(f'FFprobe not found in PATH. Please install FFmpeg and add it to PATH.')
        sys.exit(1)
        
    valid, reason = check_ffmpeg_features(FFMPEG)
    if valid:
        LOGGER.info(f'FFmpeg features supported.')
    else:
        LOGGER.error(reason)
        sys.exit(1)
    
    # arguments
    args = parser.parse_args()
    LOGGER.info(f'Current arguments: {vars(args)}')
    
    # convert to list
    paths = resolve_paths(args.path)
    args.path = paths
    
    try:
        if args.height < 0:
            LOGGER.error(f'Invalid argument "-g/--height". Height {args.height} invalid.')
            sys.exit(1)
            
        if args.seek < 0:
            LOGGER.error(f'Invalid argument "-s/--seek". Seek {args.seek} invalid.')
            sys.exit(1)
            
        c, r = args.tile.split('x')
        c, r = int(c), int(r)
        if c < 1 or r < 1 or (c == 1 and r == 1):
            LOGGER.error(f'Invalid argument "-t/--tile". Tile {args.tile} invalid.')
            sys.exit(1)
            
        if args.padratio < 0:
            args.padratio = 0.01
            
        if args.fontratio < 0:
            args.fontratio = 0.08
    except Exception:
        LOGGER.error(f'Failed to parse arguments.')
        sys.exit(1)
    
    # task
    begin = datetime.now()
    LOGGER.info(f'Task start at {begin}.')
    
    output = list(capture_multi(args.path, args))
    count_succeeded = sum(r == CaptureResult.SUCCEEDED or r == CaptureResult.SKIPPED for _, r in output)
    count_failed = sum(r == CaptureResult.CAPTURE_FAILED or r == CaptureResult.CAPTURE_ERROR_OCCURED for _, r in output)
    
    LOGGER.info(NL.join([f'{result}:\t{file}' for file, result in output]))
    LOGGER.info(f'Succeeded: {count_succeeded}{NL}' 
                + f'Completed with error: {count_failed}{NL}' 
                + f'Failed: {count_failed}')
    
    end = datetime.now()
    LOGGER.info(f'Task end at {end}. Total time elapsed: {end-begin}.')

if __name__ == "__main__":
    main()
    