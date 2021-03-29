#!/usr/bin/python3
import argparse
import re
import sys
import tkinter
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Union

import gi

import pandas as pd
import pygsheets

from PIL import Image, ImageOps, ImageTk
import pyheif
import time
gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst

# Needed for set_window_handle():
gi.require_version("GstVideo", "1.0")
from gi.repository import GstVideo

SECRET_FILE = "credentials.json"
SECRET_DIRECTORY = str(Path.home()) + "/.google"

Image.MAX_IMAGE_PIXELS = None

# Merge ratingValue and star into a dict. Otherwise they are two dangling items.
ratingvalue = {
    "-": -1,
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "+": 10,
}
star = {
    0: "X",
    1: "",
    2: "☆",
    3: "★",
    4: "★☆",
    5: "★★",
    6: "★★☆",
    7: "★★★",
    8: "★★★☆",
    9: "★★★★",
    10: "★★★★☆",
    11: "★★★★★",
}


class FileType(Enum):
    UNKNOWN = 1
    IMAGE = 2
    VIDEO = 3

    @staticmethod
    def getType(extension: str):
        if extension.lower() in [".jpg", ".png", ".bmp", ".heic"]:
            return FileType.IMAGE
        if extension.lower() in [".mp4", ".mpg", ".avi", ".mov"]:
            return FileType.VIDEO
        return FileType.UNKNOWN


class App:
    def __init__(self, r, f, db):
        self.root = r
        self.filelist = f
        self.db = db

        self.w, self.h = r.winfo_width(), r.winfo_height()
        self.input_image = None
        self.image = None
        self.canvas_image = None
        self.video_player = None
        self.keywordOutput = []

        # Let's keep all class variables here in one place.
        self.canvas = tkinter.Canvas(
            self.root,
            width=self.w,
            height=self.h,
            highlightthickness=0,
            background="black",
        )
        self.canvas_visible = True
        self.filename_label = tkinter.Label(
            self.root, font=("Arial", self.w // 80), bg="gray"
        )
        self.filename_visible = False
        self.metadataFrame = tkinter.Frame(self.root, bg="black")
        self.video_frame = tkinter.Frame(self.root, bg="black")
        self.rating = tkinter.Label(
            self.metadataFrame,
            font=("Arial", self.w // 80),
            bg="black",
            fg="yellow",
            anchor=tkinter.E,
        )

        self.keywordText = tkinter.StringVar()
        self.keywordEntry = tkinter.Entry(
            self.root,
            font=("Arial", self.w // 80),
            bg="black",
            fg="white",
            insertbackground="white",
            textvariable=self.keywordText,
        )

        self.__createWidgets()
        self.__bindRootEvents()
        self.__updateDisplay()

        self.keywordDictionary = list(db.initialKeywords) if self.db else []
        self.detect_pressed_filled = False

    def __bindRootEvents(self) -> None:
        self.root.bind("<Escape>", self.__exitCB)
        self.root.bind("<Right>", self.__nextCB)
        self.root.bind("<Left>", self.__prevCB)
        self.root.bind("<p>", self.__togglePlayCB)
        self.root.bind("<r>", self.__restartCB)
        self.root.bind("<t>", self.__toggleFilenameCB)
        if self.db:
            self.root.bind("<s>", self.__saveDBCB)
            self.root.bind("0", self.__setRatingCB)
            self.root.bind("1", self.__setRatingCB)
            self.root.bind("2", self.__setRatingCB)
            self.root.bind("3", self.__setRatingCB)
            self.root.bind("4", self.__setRatingCB)
            self.root.bind("5", self.__setRatingCB)
            self.root.bind("6", self.__setRatingCB)
            self.root.bind("7", self.__setRatingCB)
            self.root.bind("8", self.__setRatingCB)
            self.root.bind("9", self.__setRatingCB)
            self.root.bind("-", self.__setRatingCB)
            self.root.bind("+", self.__setRatingCB)
            self.root.bind("#", self.__showKeywordEntryCB)
            self.root.bind("!", self.__showKeywordEntryCB)
            self.root.bind("@", self.__showKeywordEntryCB)

    def __createWidgets(self) -> None:

        self.canvas.place(relx=0, rely=0, anchor=tkinter.NW, relwidth=1, relheight=1)
        self.metadataFrame.place(relx=1, rely=0, anchor=tkinter.NE)

        if self.db:
            self.rating.pack(fill="x")

        self.keywordEntry.bind("<Return>", self.__keywordEntryAcceptCB)
        self.keywordEntry.bind("<Escape>", self.__keywordEntryCancelCB)
        self.keywordEntry.bind("<KeyRelease>", self.__keywordEntryKeyreleaseCB)
        self.keywordEntry.bind("<Key>", self.__keywordEntryKeypressCB)

    def __setFrameHandle(self, _bus, message, frame_id) -> None:
        if (
            message.get_structure() is not None
            and message.get_structure().get_name() == "prepare-window-handle"
        ):
            video_frame = message.src
            video_frame.set_property("force-aspect-ratio", True)
            video_frame.set_window_handle(frame_id)

    def __setVideo(self, filename) -> None:
        self.__setvideoframe()
        file_abs_path = Path(filename).absolute().as_uri()
        if self.video_player is None:
            self.video_player=Gst.parse_launch('playbin uri='+file_abs_path+' video-sink= "videoflip method=automatic ! autovideosink"')
            self.video_player.set_state(Gst.State.PLAYING)
            self.bus = self.video_player.get_bus()
            self.bus.enable_sync_message_emission()
            self.bus.connect(
                "sync-message::element", self.__setFrameHandle, self.frame_id
            )
        else:
            self.video_player.set_state(Gst.State.NULL)
            self.video_player.set_property("uri", file_abs_path)
            self.video_player.set_state(Gst.State.PLAYING)

    def __setvideoframe(self):
        if self.canvas_visible:
            self.video_frame.place(
                relx=0, rely=0, anchor=tkinter.NW, relwidth=1, relheight=1
            )
            self.frame_id = self.video_frame.winfo_id()
            self.canvas.place_forget()
            self.canvas_visible = False

    def __resize_image(self, input_image):
        imgWidth, imgHeight = input_image.size
        if imgWidth > self.w or imgHeight > self.h:
            ratio = min(self.w / imgWidth, self.h / imgHeight)
            imgWidth = int(imgWidth * ratio)
            imgHeight = int(imgHeight * ratio)
            return input_image.resize((imgWidth, imgHeight), Image.ANTIALIAS)

        return input_image

    def __setImage(self, filename) -> None:
        try:
            extension = Path(filename).suffix.lower()
            if extension == ".heic":
                heif_file = pyheif.read(filename)
                input_image = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                )
                scaled_image = self.__resize_image(input_image)
                self.image = ImageTk.PhotoImage(scaled_image)
            else:
                input_image = Image.open(filename)
                input_image = ImageOps.exif_transpose(input_image)
                scaled_image = self.__resize_image(input_image)
                self.image = ImageTk.PhotoImage(scaled_image)
        except Exception as e:
            print("error loading image:" + filename)
            print(e)

    def __showImage(self) -> None:
        if not self.canvas_visible:
            if self.video_player is not None:
                self.video_player.set_state(Gst.State.PAUSED)
            self.canvas.place(
                relx=0, rely=0, anchor=tkinter.NW, relwidth=1, relheight=1
            )
            self.video_frame.place_forget()
            self.canvas_visible = True
        if self.canvas_image is None:
            self.canvas_image = self.canvas.create_image(
                self.w / 2, self.h / 2, image=self.image
            )
        else:
            self.canvas.itemconfig(self.canvas_image, image=self.image)

    def __updateDisplay(self) -> None:
        filename = str(self.filelist.current().name)
        self.filename_label["text"] = filename
        if not self.root.attributes("-fullscreen"):
            self.root.title(filename)

        if self.db:
            df = self.db.photo_df
            if filename in df.index:
                numstars = self.__get_stars(filename, df)
                self.__setKeywordOutput(df.at[filename, "keywords"])
                print("Filename: " + filename)
                print("Stars: " + str(numstars))
                print("Keywords: " + df.loc[filename]["keywords"])
            else:
                self.rating["text"] = star[1]
                self.__setKeywordOutput("")

        if self.filelist.currentType() == FileType.IMAGE:
            self.__setImage(filename)
            self.__showImage()
        elif self.filelist.currentType() == FileType.VIDEO:
            self.__setVideo(filename)

    def __get_stars(self, filename, df):
        numstars = int(df.loc[filename]["rating"])
        if (numstars >= -1) and (numstars <= 10):
            self.rating["text"] = star[numstars + 1]
        return numstars

    def __toggleFilenameCB(self, event=None) -> None:
        if self.__is_relevant_event(event):
            if self.filename_visible:
                self.filename_label.place_forget()
                self.filename_visible = False
            else:
                self.filename_label.place(relx=0.5, rely=0, anchor=tkinter.N)
                self.filename_visible = True

    def __togglePlayCB(self, event=None) -> None:
        if (
            self.__is_relevant_event(event)
            and self.filelist.currentType() == FileType.VIDEO
        ):
            (_ret, temp_state, _p_state) = self.video_player.get_state(
                timeout=Gst.SECOND
            )
            if temp_state == Gst.State.PLAYING:
                self.video_player.set_state(Gst.State.PAUSED)
            elif temp_state == Gst.State.PAUSED:
                self.video_player.set_state(Gst.State.PLAYING)

    def __is_relevant_event(self, event):
        return event.widget == self.root

    def __restartCB(self, event=None) -> None:
        if (
            self.__is_relevant_event(event)
            and self.filelist.currentType() == FileType.VIDEO
        ):
            self.video_player.set_state(Gst.State.NULL)
            self.video_player.set_state(Gst.State.PLAYING)

    def __nextCB(self, event=None) -> None:
        if self.__is_relevant_event(event):
            self.filelist.next_file()
            self.__updateDisplay()

    def __prevCB(self, event=None) -> None:
        if self.__is_relevant_event(event):
            self.filelist.prev_file()
            self.__updateDisplay()

    def __exitCB(self, event=None) -> None:
        if self.__is_relevant_event(event):
            event.widget.withdraw()
            event.widget.quit()

    def __showKeywordEntryCB(self, event=None) -> None:
        if self.__is_relevant_event(event):
            self.keywordText.set(event.char)
            self.keywordEntry.place(
                relx=0.5, rely=0.5, anchor=tkinter.CENTER, relwidth=0.5
            )
            self.keywordEntry.icursor("end")
            self.keywordEntry.focus_set()

    def __hideKeywordEntry(self) -> None:
        self.keywordEntry.place_forget()
        self.root.focus_set()

    def __setKeywordOutput(self, val) -> None:
        for t in self.keywordOutput:
            t.destroy()
        for t in val.split():
            tempLabel = tkinter.Label(
                self.metadataFrame,
                font=("Arial", self.w // 80),
                bg="black",
                fg="white",
                anchor=tkinter.E,
            )
            tempLabel["text"] = t
            tempLabel.pack(fill="x")
            self.keywordOutput.append(tempLabel)

    def __saveDBCB(self, event=None) -> None:
        if self.__is_relevant_event(event):
            self.db.save()

    def __setRatingCB(self, event=None) -> None:
        if self.__is_relevant_event(event):
            value = ratingvalue[event.char]
            filename = str(self.filelist.current().name)
            if filename in self.db.photo_df.index:
                self.db.photo_df.at[filename, "rating"] = value

            self.__updateDisplay()

    def __matchString(self):
        got = self.keywordText.get()
        return [item for item in self.keywordDictionary if item.startswith(got)]

    def __showHit(self, lst) -> None:
        if len(lst) == 1:
            self.keywordText.set(lst[0])
            self.detect_pressed_filled = True

    def __keywordEntryKeyreleaseCB(self, event) -> None:
        if len(event.keysym) == 1:
            hits = self.__matchString()
            self.__showHit(hits)

    def __keywordEntryKeypressCB(self, event) -> None:
        key = event.char
        if len(key) == 1 and self.detect_pressed_filled is True:
            pos = self.keywordEntry.index(tkinter.INSERT)
            self.keywordEntry.delete(pos, tkinter.END)

    def __keywordEntryAcceptCB(self, _event) -> None:
        df = self.db.photo_df
        filename = str(self.filelist.current().name)
        keywords = re.findall(
            r"[!#@].+?(?=[!#@]|$)", "".join(self.keywordText.get().split())
        )

        for keyword in keywords:
            if keyword[0] != "!":
                keyword = keyword.lower()
            if len(df.at[filename, "keywords"].strip()) > 0:
                curKeywords = df.at[filename, "keywords"].strip().split()
                if keyword in curKeywords:
                    curKeywords.remove(keyword)
                else:
                    curKeywords.append(keyword)
                df.at[filename, "keywords"] = " ".join(curKeywords)
            else:
                df.at[filename, "keywords"] = keyword

            if keyword not in self.keywordDictionary:
                self.keywordDictionary.append(keyword)

        #    print(df.at[f.current(),'keywords'])
        self.__setKeywordOutput(df.at[filename, "keywords"])
        self.__hideKeywordEntry()

    def __keywordEntryCancelCB(self, _event) -> None:
        self.__hideKeywordEntry()


class FileList:
    def __init__(self, recursive=False, first=None, input_filelist=None):
        if not input_filelist:
            input_pathlist = (
                Path.cwd().rglob("*.*") if recursive else Path.cwd().glob("*.*")
            )
        else:
            input_pathlist=(
                Path(file).absolute()
                for file in input_filelist
            )

        self.filelist = [
            file
            for file in sorted(input_pathlist)
            if FileType.getType(file.suffix) != FileType.UNKNOWN
        ]
        self.length = len(self.filelist)
        self.file_index = 0

        if first is not None:
            while Path(first).absolute() > self.current() and self.file_index<self.length-1:
                self.file_index += 1

    def next_file(self) -> Path:
        self.file_index = (self.file_index + 1) % self.length
        return self.current()

    def prev_file(self) -> Path:
        self.file_index = (self.file_index - 1) % self.length
        return self.current()

    def current(self) -> Path:
        return self.filelist[self.file_index]

    def currentType(self) -> FileType:
        return FileType.getType(self.current().suffix)


class PhotoDB:
    def __init__(self, dbFilename):
        self.dbFilename=dbFilename
        if Path(dbFilename).suffix.lower()=='.csv':
            self.googleDB=False
            self.photo_df=pd.read_csv(dbFilename)
            self.photo_df["keywords"] = self.photo_df["keywords"].fillna('').astype("str")
        else:
            self.googleDB=True
            self.gc = pygsheets.authorize(
                client_secret=SECRET_FILE, credentials_directory=SECRET_DIRECTORY
            )
            self.sheet = self.gc.open(dbFilename)

            try:
                worksheet1 = self.sheet.sheet1
            except Exception as e:
                print("Error: sheet non found")
                print(e)
                sys.exit()

            self.photo_df = worksheet1.get_as_df()

        self.photo_df.set_index("filename", inplace=True)
        self.photo_df.index.name = "filename"
        self.photo_df["rating"] = (
            pd.to_numeric(self.photo_df["rating"], errors="coerce")
            .fillna(0)
            .astype("int")
        )
        self.initialKeywords = set()
        self.photo_df["keywords"].str.split().apply(self.initialKeywords.update)

    def save(self) -> None:
        if self.googleDB==True:
            title = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
            worksheet = self.sheet.add_worksheet(title, rows=10, cols=10, index=0)
            worksheet.clear()
            out_tbl = self.photo_df.reset_index()
            worksheet.set_dataframe(out_tbl, "A1", copy_index=False, extend=True)
            print("finished saving")
            oldsheet = self.sheet.worksheet("index", 3)  # What is this?
            self.sheet.del_worksheet(oldsheet)
        else:
            extension = datetime.now().strftime("_%m%d%Y%H%M%S.csv")
            if re.match(r'.*_\d{14}\.csv',self.dbFilename.lower()):
                newcsvfile=re.sub(r'_\d{14}\.csv',extension,self.dbFilename.lower())
            else:
                newcsvfile=re.sub(r'\.csv',extension,self.dbFilename.lower())
            print('Saving: '+newcsvfile)
            self.photo_df.to_csv(newcsvfile)
'''
class MockDB:
    def __init__(self, FileList):
        print(FileList.filelist)
        column_names = ["filename", "rating", "keywords"]

        self.photo_df = pd.DataFrame(columns=column_names)
        # self.photo_df = worksheet1.get_as_df()
        self.photo_df.set_index("filename", inplace=True)
        self.photo_df.index.name = "filename"

        for file in FileList.filelist:
            filename = str(file.absolute())
            print(filename)
            self.photo_df.at[filename, "rating"] = 1
            self.photo_df.at[filename, "keywords"] = ""

        self.photo_df["rating"] = (
            pd.to_numeric(self.photo_df["rating"], errors="coerce")
            .fillna(0)
            .astype("int")
        )
        print(self.photo_df)
        self.initialKeywords = set()
        self.photo_df["keywords"].str.split().apply(self.initialKeywords.update)

    def save(self) -> None:
        print(self.photo_df)
'''

def parse_arguments():
    parser = argparse.ArgumentParser(description="Display images/videos in a slideshow")
    parser.add_argument(
        "-s", 
        "--size", 
        help="display size WxH", 
        action="store", 
        dest="size"
    )
    parser.add_argument(
        "-r",
        "--recursive",
        help="recursively navigate directories",
        action="store_true",
        dest="recursive",
    )
    parser.add_argument(
        "-f",
        "--first",
        help="first file to display",
        action="store",
        dest="first",
        default=None,
    )
    parser.add_argument(
        "-d",
        "--db",
        help="Enable GoogleSheets Database",
        action="store",
        dest="DB",
        default=None,
    )
    parser.add_argument(
        "files",
        help="(optional) list of files to display",
        action="store",
        nargs=argparse.REMAINDER,
    )
    return parser.parse_args()


def print_new_files(f: FileList, photoDB) -> None:
    if photoDB is not None:
        filelist = [p.name for p in f.filelist]
        infile_table = pd.Index(filelist)
        diff = infile_table.difference(photoDB.photo_df.index)
        if len(diff) > 0:
            print("# files not in DB: " + str(len(diff)))
            for d in diff:
                print(d)


def main():
    Gst.init(None)

    args = parse_arguments()

    f = FileList(recursive=args.recursive, first=args.first, input_filelist=args.files)
    photoDB = PhotoDB(args.DB) if args.DB else None
    root = tkinter.Tk()
    if args.size:
        root.geometry("%s+0+0" % args.size)
        root.resizable(False, False)
    else:
        root.attributes("-fullscreen", True)

    root.configure(background="black")
    root.update_idletasks()
    root.focus_set()

    print_new_files(f, photoDB)

    App(root, f, photoDB)
    root.mainloop()


if __name__ == "__main__":
    main()
