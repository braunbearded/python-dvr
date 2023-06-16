from dvrip import DVRIPCam
from dvrip import SomethingIsWrongWithCamera
from pathlib import Path
import subprocess
from time import sleep
import os

host_ip = os.environ.get("IP_ADDRESS")
user = os.environ.get("USER")
password = os.environ.get("PASSWORD")

if host_ip == "" or user == "":
    print("Please provide the username and ip address")
    exit(1)

cam = DVRIPCam(host_ip, user=user, password=password)


def login():
    if cam.login():
        print(f"Success! Connected to {host_ip}")
    else:
        print("Failure. Could not connect.")


def ptz_step(cmd, step=5):
    # To do a single step the first message will just send a tilt command which last forever
    # the second command will stop the tilt movement
    # that means if second message does not arrive for some reason the camera will be keep moving in that direction forever

    parms_start = {
        "AUX": {"Number": 0, "Status": "On"},
        "Channel": 0,
        "MenuOpts": "Enter",
        "POINT": {"bottom": 0, "left": 0, "right": 0, "top": 0},
        "Pattern": "SetBegin",
        "Preset": 65535,
        "Step": step,
        "Tour": 0,
    }

    cam.set_command("OPPTZControl", {"Command": cmd, "Parameter": parms_start})

    parms_end = {
        "AUX": {"Number": 0, "Status": "On"},
        "Channel": 0,
        "MenuOpts": "Enter",
        "POINT": {"bottom": 0, "left": 0, "right": 0, "top": 0},
        "Pattern": "SetBegin",
        "Preset": -1,
        "Step": step,
        "Tour": 0,
    }

    cam.set_command("OPPTZControl", {"Command": cmd, "Parameter": parms_end})


def list_local_files(startTime, endTime, filetype):
    # 1440 OPFileQuery
    result = []
    data = cam.send(
        1440,
        {
            "Name": "OPFileQuery",
            "OPFileQuery": {
                "BeginTime": startTime,
                "Channel": 0,
                "DriverTypeMask": "0x0000FFFF",
                "EndTime": endTime,
                "Event": "*",
                "StreamType": "0x00000000",
                "Type": filetype,
            },
        },
    )

    if data == None or data["Ret"] != 100:
        print("Could not get files.")
        raise ConnectionRefusedError("Could not get files")

    # When no file can be found for the query OPFileQuery is None
    if data["OPFileQuery"] == None:
        print(f"No files found for this range. Start: {startTime}, End: {endTime}")
        return []

    # OPFileQuery only returns the first 64 items
    # we therefore need to add the results to a list, modify the starttime with the begintime value of the last item we received and query again
    result = data["OPFileQuery"]
    while len(data["OPFileQuery"]) == 64:
        newStartTime = data["OPFileQuery"][-1]["BeginTime"]
        data = cam.send(
            1440,
            {
                "Name": "OPFileQuery",
                "OPFileQuery": {
                    "BeginTime": newStartTime,
                    "Channel": 0,
                    "DriverTypeMask": "0x0000FFFF",
                    "EndTime": endTime,
                    "Event": "*",
                    "StreamType": "0x00000000",
                    "Type": filetype,
                },
            },
        )
        result += data["OPFileQuery"]

    print(f"Found {len(result)} files.")
    return result


def download_file(startTime, endTime, filename, targetFilePath, download=True):
    Path(targetFilePath).parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading: {targetFilePath}")

    cam.send(
        1424,
        {
            "Name": "OPPlayBack",
            "OPPlayBack": {
                "Action": "Claim",
                "Parameter": {
                    "PlayMode": "ByName",
                    "FileName": filename,
                    "StreamType": 0,
                    "Value": 0,
                    "TransMode": "TCP",
                    # Maybe IntelligentPlayBack is needed in some edge case
                    # "IntelligentPlayBackEvent": "",
                    # "IntelligentPlayBackSpeed": 2031619,
                },
                "StartTime": startTime,
                "EndTime": endTime,
            },
        },
    )

    actionStart = "Start"
    if download:
        actionStart = f"Download{actionStart}"

    data = cam.send_download(
        0,
        1420,
        {
            "Name": "OPPlayBack",
            "OPPlayBack": {
                "Action": actionStart,
                "Parameter": {
                    "PlayMode": "ByName",
                    "FileName": filename,
                    "StreamType": 0,
                    "Value": 0,
                    "TransMode": "TCP",
                    # Maybe IntelligentPlayBack is needed in some edge case
                    # "IntelligentPlayBackEvent": "",
                    # "IntelligentPlayBackSpeed": 0,
                },
                "StartTime": startTime,
                "EndTime": endTime,
            },
        },
    )

    try:
        with open(targetFilePath, "wb") as bin_data:
            bin_data.write(data)
    except TypeError as e:
        Path(targetFilePath).unlink(missing_ok=True)
        print(f"An error occured while downloading {targetFilePath}")
        return e

    print(f"File successfully downloaded: {targetFilePath}")

    actionStop = "Stop"
    if download:
        actionStop = f"Download{actionStop}"

    cam.send(
        1420,
        {
            "Name": "OPPlayBack",
            "OPPlayBack": {
                "Action": actionStop,
                "Parameter": {
                    "FileName": filename,
                    "PlayMode": "ByName",
                    "StreamType": 0,
                    "TransMode": "TCP",
                    "Channel": 0,
                    "Value": 0,
                    # Maybe IntelligentPlayBack is needed in some edge case
                    # "IntelligentPlayBackEvent": "",
                    # "IntelligentPlayBackSpeed": 0,
                },
                "StartTime": startTime,
                "EndTime": endTime,
            },
        },
    )
    return None


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
        print(f"Error converting video. Check {sourceFile}")

    print(f"File successfully converted: {targetFile}")
    Path(sourceFile).unlink()
    print(f"Orginal file successfully deleted: {sourceFile}")


def downloadWithDisconnect(beginTime, endTime, filename, targetPath, sleepTime=2):
    global cam
    # Camera disconnects after a couple of minutes
    while True:
        if (
            download_file(
                beginTime,
                endTime,
                filename,
                targetPath,
                True,
            )
            == None
        ):
            break

        print(f"Camera disconnected. Retring in {sleepTime} seconds...")
        cam.close()
        cam = DVRIPCam(host_ip, user=user, password=password)
        sleep(sleepTime)
        try:
            login()
        except SomethingIsWrongWithCamera:
            print(f"Login failed. Retring in {sleepTime} seconds...")
            sleep(sleepTime)


def download_all():
    convertTo = os.environ.get("MOVIE_TARGET_FORMAT")
    downloadDir = os.environ.get("DOWNLOAD_DIR")
    start = os.environ.get("DOWNLOAD_START_TIME")
    end = os.environ.get("DOWNLOAD_END_TIME")

    if convertTo == None or downloadDir == None or start == None or end == None:
        print("Please provide the username and ip address")
        exit(1)

    login()

    videos = list_local_files(start, end, "h264")
    pictures = list_local_files(start, end, "jpg")

    Path(downloadDir).mkdir(parents=True, exist_ok=True)

    for file in videos:
        targetFilePath = generateTargetFilePath(file["FileName"], downloadDir)
        targetFilePathConvert = generateTargetFilePath(
            file["FileName"], downloadDir, extention=f"{convertTo}"
        )

        if Path(f"{targetFilePath}").is_file():
            print(f"File already exists: {targetFilePath}")
            continue

        if Path(f"{targetFilePathConvert}").is_file():
            print(f"Converted file already exists: {targetFilePathConvert}")
            continue

        downloadWithDisconnect(
            file["BeginTime"], file["EndTime"], file["FileName"], targetFilePath
        )

        convertFile(targetFilePath, targetFilePathConvert)

    for file in pictures:
        targetFilePath = generateTargetFilePath(file["FileName"], downloadDir)

        if Path(f"{targetFilePath}").is_file():
            print(f"File already exists: {targetFilePath}")
            continue

        downloadWithDisconnect(
            file["BeginTime"], file["EndTime"], file["FileName"], targetFilePath
        )

    cam.close()


def move_cam():
    login()
    direction = os.environ.get("DIRECTION")
    speed = os.environ.get("SPEED")

    if direction not in [
        "DirectionUp",
        "DirectionDown",
        "DirectionRight",
        "DirectionLeft",
    ]:
        exit("Please provide direction.")

    if speed == None:
        speed = 5
    else:
        speed = int(speed)
    ptz_step("DirectionUp", step=speed)


def main():
    action = os.environ.get("ACTION")
    if action not in ["download", "move"]:
        print("Please provide an action")
        exit(1)

    for i in range(10):
        try:
            print("Try login")
            login()
            break
        except Exception:
            print("Camera offline")
            cam.close()

        if i == 9:
            exit(1)
        sleep(2)

    if action == "download":
        download_all()

    if action == "move":
        move_cam()


if __name__ == "__main__":
    main()

#    cam.send(
#        1040,
#        {
#            "fVideo.Volume": [
#                {"AudioMode": "Single", "LeftVolume": 0, "RightVolume": 0}
#            ],
#            "Name": "fVideo.Volume",
#        },
#    )
