import logging
import shutil
import subprocess
import time
import uuid
from threading import Thread

import consts

log = logging.getLogger(__name__)


class Recorder:
    def __init__(self, driver, fps=4, prefix=""):
        self._driver = driver
        self._fps = fps
        dir_name = prefix + "_" + str(uuid.uuid1()).split("-")[-1]
        self._screenshots_dir = consts.LOG_DIR / dir_name
        self._screenshots_dir.mkdir()
        log.info(f"Screenshot dir: {self._screenshots_dir}")
        self._thread = Thread(target=self._recorder)
        self._should_stop = False
        self._ffmpeg_exec_path = "ffmpeg"
        self._ffmpeg_exists = True
        self._check_ffmpeg_exists()

    def _check_ffmpeg_exists(self):
        ret_code = subprocess.check_call([self._ffmpeg_exec_path, "-version"])
        if ret_code:
            log.warning("FFmpeg wasn't found")
            self._ffmpeg_exists = False

    def _recorder(self):
        counter = 0
        while True:
            if self._should_stop:
                log.info("Got 'Should stop' signal")
                break
            screenshot_path = self._screenshots_dir / f"{str(counter).zfill(5)}.png"
            self._driver.save_screenshot(str(screenshot_path))
            log.debug(f"Saved screenshot: {screenshot_path}")
            counter += 1
            time.sleep(1 / self._fps)

    def render_video(self, node_name):
        # TODO: use ffmpeg to render LOG messages as subtitles
        title = node_name.replace("/", "_")

        if not self._ffmpeg_exists:
            log.error("Can't render video: ffmpeg wasn't found")
            return

        output_mp4 = consts.LOG_DIR / f"{title}.mp4"
        proc = subprocess.Popen(
            [self._ffmpeg_exec_path,
             "-r", str(self._fps),
             "-f", "image2",
             # "-s", f"{consts.RESOLUTION[0]}x{consts.RESOLUTION[1]}",  # TODO: use actual window size
             "-i", f"{self._screenshots_dir}/%05d.png",
             "-vcodec", "libx264",
             "-pix_fmt", "yuv420p",
             "-y", str(output_mp4),
             ],
        )
        proc.wait()
        log.info(f"Video recorded at: {output_mp4}")
        shutil.rmtree(self._screenshots_dir)
        log.info(f"Screenshot dir removed: {self._screenshots_dir}")

    def start(self):
        self._thread.start()
        log.info(f"Started recorder. FPS: {self._fps}")

    def stop(self):
        time.sleep(2)   # do not interrupt video immediatelly
        self._should_stop = True
        self._thread.join()
