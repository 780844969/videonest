"""Use the bundled imageio-ffmpeg binary locally; production may supply FFmpeg directly."""
import os
import shutil
from pathlib import Path
import imageio_ffmpeg

root=Path(__file__).resolve().parents[1]/'tools'
root.mkdir(exist_ok=True)
target=root/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')
shutil.copyfile(imageio_ffmpeg.get_ffmpeg_exe(),target)
target.chmod(0o755)
print(f'FFmpeg ready: {target}')
