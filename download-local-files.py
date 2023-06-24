from pathlib import Path
from time import sleep
import os
import json
import logging
from collections import namedtuple
from solarcam import SolarCam


# def download_all(self):
#     blacklist = []
#
#     Path(blacklistPath).parent.mkdir(parents=True, exist_ok=True)
#     if not Path(blacklistPath).exists():
#         with open(blacklistPath, "w") as filehandle:
#             json.dump(blacklist, filehandle)
#
#     with open(blacklistPath, "r") as filehandle:
#         blacklist = json.load(filehandle)
#
#     if (
#         convertTo == None
#         or downloadDirVideo == None
#         or start == None
#         or end == None
#     ):
#         logger.debug("Please provide download settings")
#         exit(1)
#
#     login()
#
#     videos = []
#     pictures = []
#     for i in range(10):
#         try:
#             videos = cam.list_local_files(start, end, "h264")
#             break
#         except ConnectionRefusedError:
#             logger.debug("Couldnt get file list")
#
#         if i == 9:
#             logger.debug("Couldnt get file list after 10 attemps...exiting")
#             exit(1)
#
#     Path(downloadDirPicture).mkdir(parents=True, exist_ok=True)
#     logger.debug(f"Start downloading pictures")
#     for file in pictures:
#         targetFilePath = generateTargetFilePath(
#             file["FileName"], downloadDirPicture
#         )
#
#         if Path(f"{targetFilePath}").is_file():
#             logger.debug(f"File already exists: {targetFilePath}")
#             continue
#
#         if targetFilePath in blacklist:
#             logger.debug(f"File is on the blacklist: {targetFilePath}")
#             continue
#
#         downloadWithDisconnect(
#             file["BeginTime"], file["EndTime"], file["FileName"], targetFilePath
#         )
#
#     cam.close()
#     logger.debug(f"Finish downloading pictures")


def init_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


def load_config():
    def config_decoder(config_dict):
        return namedtuple("X", config_dict.keys())(*config_dict.values())

    config_path = os.environ.get("CONFIG_PATH")
    if Path(config_path).exists():
        with open(config_path, "r") as file:
            return json.loads(file.read(), object_hook=config_decoder)

    return {
        "host_ip": os.environ.get("IP_ADDRESS"),
        "user": os.environ.get("USER"),
        "password": os.environ.get("PASSWORD"),
        "target_filetype_video": os.environ.get("target_filetype_video"),
        "download_dir_video": os.environ.get("DOWNLOAD_DIR_VIDEO"),
        "download_dir_picture": os.environ.get("DOWNLOAD_DIR_PICTURE"),
        "start": os.environ.get("START"),
        "end": os.environ.get("END"),
        "blacklist_path": os.environ.get("BLACKLIST_PATH"),
        "cooldown": int(os.environ.get("COOLDOWN")),
    }


def main():
    logger = init_logger()
    config = load_config()
    start = config.start
    end = config.end
    cooldown = config.cooldown

    blacklist = None
    if Path(config.blacklist_path).exists():
        with open(config.blacklist_path, "r") as filehandle:
            blacklist = json.load(filehandle)

    while True:
        solarCam = SolarCam(config.host_ip, config.user, config.password, logger)

        try:
            solarCam.login()

            battery = solarCam.get_battery()
            logger.debug(f"Current battery status: {battery}")
            storage = solarCam.get_storage()[0]
            logger.debug(f"Current storage status: {storage}")

            sleep(5)  # sleep some seconds so camera can get ready

            pics = solarCam.get_local_files(start, end, "jpg")
            if pics:
                Path(config.download_dir_picture).parent.mkdir(
                    parents=True, exist_ok=True
                )
                solarCam.save_files(
                    config.download_dir_picture, pics, blacklist=blacklist
                )

            videos = solarCam.get_local_files(start, end, "h264")
            if videos:
                Path(config.download_dir_video).parent.mkdir(
                    parents=True, exist_ok=True
                )
                solarCam.save_files(
                    config.download_dir_video,
                    videos,
                    blacklist=blacklist,
                    target_filetype=config.target_filetype_video,
                )

            solarCam.logout()
        except ConnectionRefusedError:
            logger.debug(f"Connection could not be established or got disconnected")
        except TypeError as e:
            print(e)
            logger.debug(f"Error while downloading a file")
        except KeyError:
            logger.debug(f"Error while getting the file list")
        logger.debug(f"Sleeping for {cooldown} seconds...")
        sleep(cooldown)


if __name__ == "__main__":
    main()

# todo add function to dump file list
# todo add flask api for moving cam
# todo show current stream
# todo show battery on webinterface and write it to mqtt topic
# todo change camera name
# todo update camera clock
