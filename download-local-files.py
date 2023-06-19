from dvrip import DVRIPCam, SomethingIsWrongWithCamera
from pathlib import Path
import subprocess
from time import sleep, localtime, strftime
import os
import json
import logging

logger = logging.getLogger(__name__)


def init_logger():
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


host_ip = os.environ.get("IP_ADDRESS")
user = os.environ.get("USER")
password = os.environ.get("PASSWORD")

if host_ip == "" or user == "":
    logger.debug("Please provide the username and ip address")
    exit(1)

cam = DVRIPCam(host_ip, user=user, password=password)


def login():
    if cam.login():
        logger.debug(f"Success! Connected to {host_ip}")
    else:
        logger.debug("Failure. Could not connect.")


def generateTargetFilePath(filename, downloadDir, extention=""):
    fileExtention = Path(filename).suffix
    filenameSplit = filename.split("/")
    filenameDisk = f"{filenameSplit[3]}_{filenameSplit[5][:8]}".replace(".", "-")
    targetPathClean = f"{downloadDir}/{filenameDisk}"

    if extention != "":
        return f"{targetPathClean}{extention}"

    return f"{targetPathClean}{fileExtention}"


def convertFile(sourceFile, targetFile):
    if (
        subprocess.run(
            [
                "ffmpeg",
                "-framerate",
                "15",
                "-i",
                sourceFile,
                "-c",
                "copy",
                targetFile,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        != 0
    ):
        logger.debug(f"Error converting video. Check {sourceFile}")

    logger.debug(f"File successfully converted: {targetFile}")
    Path(sourceFile).unlink()
    logger.debug(f"Orginal file successfully deleted: {sourceFile}")


def downloadWithDisconnect(beginTime, endTime, filename, targetPath, sleepTime=2):
    global cam
    # Camera disconnects after a couple of minutes
    while True:
        if (
            cam.download_file(
                beginTime,
                endTime,
                filename,
                targetPath,
                True,
            )
            == None
        ):
            break

        logger.debug(f"Camera disconnected. Retring in {sleepTime} seconds...")
        cam.close()
        cam = DVRIPCam(host_ip, user=user, password=password)
        sleep(sleepTime)
        try:
            login()
        except SomethingIsWrongWithCamera:
            logger.debug(f"Login failed. Retring in {sleepTime} seconds...")
            sleep(sleepTime)


def download_all():
    convertTo = os.environ.get("VIDEO_TARGET_FORMAT")
    downloadDirVideo = os.environ.get("DOWNLOAD_DIR_VIDEO")
    downloadDirPicture = os.environ.get("DOWNLOAD_DIR_PICTURE")
    start = os.environ.get("DOWNLOAD_START_TIME")
    end = os.environ.get("DOWNLOAD_END_TIME")
    blacklistPath = os.environ.get("BLACKLIST_PATH")
    blacklist = []

    Path(blacklistPath).parent.mkdir(parents=True, exist_ok=True)
    if not Path(blacklistPath).exists():
        with open(blacklistPath, "w") as filehandle:
            json.dump(blacklist, filehandle)

    with open(blacklistPath, "r") as filehandle:
        blacklist = json.load(filehandle)

    if convertTo == None or downloadDirVideo == None or start == None or end == None:
        logger.debug("Please provide download settings")
        exit(1)

    login()

    videos = []
    pictures = []
    for i in range(10):
        try:
            videos = cam.list_local_files(start, end, "h264")
            pictures = cam.list_local_files(start, end, "jpg")
            break
        except ConnectionRefusedError:
            logger.debug("Couldnt get file list")

        if i == 9:
            logger.debug("Couldnt get file list after 10 attemps...exiting")
            exit(1)

    Path(downloadDirVideo).mkdir(parents=True, exist_ok=True)
    logger.debug(f"Start downloading videos")

    for file in videos:
        targetFilePath = generateTargetFilePath(file["FileName"], downloadDirVideo)
        targetFilePathConvert = generateTargetFilePath(
            file["FileName"], downloadDirVideo, extention=f"{convertTo}"
        )

        if Path(f"{targetFilePath}").is_file():
            logger.debug(f"File already exists: {targetFilePath}")
            continue

        if Path(f"{targetFilePathConvert}").is_file():
            logger.debug(f"Converted file already exists: {targetFilePathConvert}")
            continue

        if targetFilePath in blacklist or targetFilePathConvert in blacklist:
            logger.debug(
                f"File is on the blacklist: {targetFilePath}, {targetFilePathConvert}"
            )
            continue

        downloadWithDisconnect(
            file["BeginTime"], file["EndTime"], file["FileName"], targetFilePath
        )

        convertFile(targetFilePath, targetFilePathConvert)
    logger.debug(f"Finish downloading videos")

    Path(downloadDirPicture).mkdir(parents=True, exist_ok=True)
    logger.debug(f"Start downloading pictures")
    for file in pictures:
        targetFilePath = generateTargetFilePath(file["FileName"], downloadDirPicture)

        if Path(f"{targetFilePath}").is_file():
            logger.debug(f"File already exists: {targetFilePath}")
            continue

        if targetFilePath in blacklist:
            logger.debug(f"File is on the blacklist: {targetFilePath}")
            continue

        downloadWithDisconnect(
            file["BeginTime"], file["EndTime"], file["FileName"], targetFilePath
        )

    cam.close()
    logger.debug(f"Finish downloading pictures")


def move_cam():
    login()
    direction = os.environ.get("DIRECTION")
    step = os.environ.get("STEP")

    if direction not in [
        "DirectionUp",
        "DirectionDown",
        "DirectionRight",
        "DirectionLeft",
    ]:
        exit("Please provide direction.")

    if step == None:
        step = 5
    else:
        step = int(step)
    cam.ptz_step(direction, step=step)


def main():
    init_logger()
    while True:
        action = os.environ.get("ACTION")
        if action not in ["download", "move"]:
            logger.debug("Please provide an action")
            exit(1)

        for i in range(10):
            try:
                logger.debug("Try login...")
                login()
                break
            except Exception:
                logger.debug("Camera offline")
                cam.close()

            if i == 9:
                exit(1)
            sleep(2)

        if action == "download":
            download_all()

        if action == "move":
            move_cam()

        schedule_time = int(os.environ.get("SCHEDULE"))
        logger.debug(f"Waiting {schedule_time}s for next run...")
        sleep(schedule_time)


if __name__ == "__main__":
    main()

# todo add function to dump file list
