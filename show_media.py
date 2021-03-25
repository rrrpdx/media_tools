#!/usr/bin/python3
import sys
import os
import tkinter
from PIL import Image, ImageTk, ImageOps
import pyheif
import glob
import gi
import argparse
import pygsheets
import pandas as pd
from datetime import datetime
import re

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

# Needed for set_window_handle():
gi.require_version('GstVideo', '1.0')
from gi.repository import GstVideo

SECRET_FILE='credentials.json'
SECRET_DIRECTORY=os.getenv('HOME')+'/.google'

Image.MAX_IMAGE_PIXELS=None
ratingvalue={
"-":-1,
"0":0,
"1":1,
"2":2,
"3":3,
"4":4,
"5":5,
"6":6,
"7":7,
"8":8,
"9":9,
"+":10,
}
star={}
star[0]='X'
star[1]=''
star[2]='☆'
star[3]='★'
star[4]='★☆'
star[5]='★★'
star[6]='★★☆'
star[7]='★★★'
star[8]='★★★☆'
star[9]='★★★★'
star[10]='★★★★☆'
star[11]='★★★★★'


class App:
    def __init__(self, r, f, db):
        self.root=r
        self.w, self.h = r.winfo_width(), r.winfo_height()
        self.filelist=f
        self.input_image=None
        self.image=None
        self.canvas_image=None
        self.video_player=None
        self.db=db
        self.keywordOutput=[]
        self.createWidgets()
        self.bindRootEvents()
        self.updateDisplay()
        if self.db:
            self.keywordDictionary=list(db.initialKeywords)
        else:
            self.keywordDictionary=[]
        self.detect_pressed_filled=False

    def bindRootEvents(self):
        self.root.bind("<Escape>", self.exitCB)
        self.root.bind("<Right>", self.nextCB)
        self.root.bind("<Left>", self.prevCB)
        self.root.bind("<p>", self.togglePlayCB)
        self.root.bind("<r>", self.restartCB)
        self.root.bind("<t>",self.toggleFilenameCB)
        if self.db:
            self.root.bind("<s>", self.saveDBCB)
            self.root.bind("0",self.setRatingCB)
            self.root.bind("1",self.setRatingCB)
            self.root.bind("2",self.setRatingCB)
            self.root.bind("3",self.setRatingCB)
            self.root.bind("4",self.setRatingCB)
            self.root.bind("5",self.setRatingCB)
            self.root.bind("6",self.setRatingCB)
            self.root.bind("7",self.setRatingCB)
            self.root.bind("8",self.setRatingCB)
            self.root.bind("9",self.setRatingCB)
            self.root.bind("-",self.setRatingCB)
            self.root.bind("+",self.setRatingCB)
            self.root.bind("#",self.showKeywordEntryCB)
            self.root.bind("!",self.showKeywordEntryCB)
            self.root.bind("@",self.showKeywordEntryCB)


    def createWidgets(self):
        self.canvas=tkinter.Canvas(self.root,width=self.w, height=self.h,highlightthickness=0,background="black")
        self.canvas.place(relx = 0, rely = 0, anchor = tkinter.NW, relwidth = 1, relheight = 1)
        self.canvas_visible=True
        self.video_frame = tkinter.Frame(self.root, bg='black')
        self.filename_label=tkinter.Label(self.root,font=("Arial",self.w//80),bg="gray")
        self.filename_visible=False
        self.metadataFrame=tkinter.Frame(self.root,bg='black')
        self.metadataFrame.place(relx=1,rely=0,anchor=tkinter.NE)
        self.rating=tkinter.Label(self.metadataFrame,font=("Arial",self.w//80),bg="black",fg="yellow",anchor=tkinter.E)
        if self.db:
            self.rating.pack(fill='x')
        self.keywordText=tkinter.StringVar()
        self.keywordEntry=tkinter.Entry(self.root,font=("Arial",self.w//80),bg="black",fg="white",insertbackground="white",textvariable=self.keywordText)
        self.keywordEntry.bind('<Return>',self.keywordEntryAcceptCB)
        self.keywordEntry.bind('<Escape>',self.keywordEntryCancelCB)
        self.keywordEntry.bind('<KeyRelease>',self.keywordEntryKeyreleaseCB)
        self.keywordEntry.bind('<Key>',self.keywordEntryKeypressCB)

    def setKeywordOutput(self,val):
        for t in self.keywordOutput:
            t.destroy()
        for t in val.split():
            tempLabel=tkinter.Label(self.metadataFrame,font=("Arial",self.w//80),bg="black",fg="white",anchor=tkinter.E)
            tempLabel['text']=t
            tempLabel.pack(fill='x')
            self.keywordOutput.append(tempLabel)


    def setFrameHandle(self, bus, message, frame_id):
        if not message.get_structure() is None:
            if message.get_structure().get_name() == 'prepare-window-handle':
                video_frame = message.src
                video_frame.set_property('force-aspect-ratio', True)
                video_frame.set_window_handle(frame_id)

    def setVideo(self,filename):
        if self.canvas_visible:
            self.video_frame.place(relx = 0, rely = 0, anchor = tkinter.NW, relwidth = 1, relheight = 1)
            self.frame_id = self.video_frame.winfo_id()
            self.canvas.place_forget()
            self.canvas_visible=False

        if self.video_player is None:    
            self.video_player = Gst.ElementFactory.make('playbin', None)
            self.video_player.set_property('uri', 'file://%s' % os.path.abspath(filename))
            self.video_player.set_state(Gst.State.PLAYING)
            self.bus = self.video_player.get_bus()
            self.bus.enable_sync_message_emission()
            self.bus.connect('sync-message::element', self.setFrameHandle, self.frame_id)
        else:
            self.video_player.set_state(Gst.State.NULL)
            self.video_player.set_property('uri', 'file://%s' % os.path.abspath(filename))
            self.video_player.set_state(Gst.State.PLAYING)


    def setImage(self,filename):
        try:
            extension=os.path.splitext(filename)[1].lower()
            if extension=='.heic':
                heif_file=pyheif.read(filename)
                self.input_image=Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride
                )
            else:        
                self.input_image=Image.open(filename)
                self.input_image=ImageOps.exif_transpose(self.input_image)
        except:
            print("error loading image:"+filename)

    def showImage(self):
        if not self.canvas_visible:
            if self.video_player is not None:
                self.video_player.set_state(Gst.State.PAUSED)
            self.canvas.place(relx = 0, rely = 0, anchor = tkinter.NW, relwidth = 1, relheight = 1)
            self.video_frame.place_forget()
            self.canvas_visible=True
        imgWidth, imgHeight = self.input_image.size
        if imgWidth > self.w or imgHeight > self.h:
            ratio = min(self.w/imgWidth, self.h/imgHeight)
            imgWidth = int(imgWidth*ratio)
            imgHeight = int(imgHeight*ratio)
            scaled_image = self.input_image.resize((imgWidth,imgHeight), Image.ANTIALIAS)
        else:
            scaled_image=self.input_image
        self.image = ImageTk.PhotoImage(scaled_image)
        if self.canvas_image is None:
            self.canvas_image=self.canvas.create_image(self.w/2,self.h/2,image=self.image)
        else:
            self.canvas.itemconfig(self.canvas_image,image=self.image)


    def updateDisplay(self):
        self.filename_label['text']=self.filelist.current()
        if not self.root.attributes('-fullscreen'):
            self.root.title(self.filelist.current())

        if self.db:
            if self.filelist.current() in self.db.photo_tbl.index:
                numstars=int(self.db.photo_tbl.loc[self.filelist.current()]['rating'])
                if (numstars >=-1 and numstars <=10):
                    self.rating['text']=star[numstars+1]
                self.setKeywordOutput(self.db.photo_tbl.at[self.filelist.current(),'keywords'])
                print('Filename: ' + self.filelist.current())
                print('Stars: ' + str(numstars))
                print('Keywords: ' + self.db.photo_tbl.loc[self.filelist.current()]['keywords'])
            else:
                self.rating['text']=star[1]
                self.setKeywordOutput("")


        if (self.filelist.currentType()=='IMAGE'):
            self.setImage(self.filelist.current())
            self.showImage()
        elif(self.filelist.currentType()=='VIDEO'):
            self.setVideo(self.filelist.current())

    def toggleFilenameCB(self,event=None):
        if (event.widget == self.root):
            if self.filename_visible:
                self.filename_label.place_forget()
                self.filename_visible=False
            else:
                self.filename_label.place(relx=0.5,rely=0,anchor=tkinter.N)
                self.filename_visible=True

    def showKeywordEntryCB(self, event=None):
        if (event.widget==self.root):
            self.keywordText.set(event.char)
            self.keywordEntry.place(relx=0.5,rely=0.5,anchor=tkinter.CENTER,relwidth=0.5)
            self.keywordEntry.icursor("end")
            self.keywordEntry.focus_set()

    def hideKeywordEntry(self):
        self.keywordEntry.place_forget()
        self.root.focus_set()

    def togglePlayCB(self,event=None):
        if (event.widget == self.root):
            if (f.currentType()=='VIDEO'):
                (_ret,temp_state,_pending_state)=self.video_player.get_state(timeout=Gst.SECOND)
                if temp_state==Gst.State.PLAYING:
                    self.video_player.set_state(Gst.State.PAUSED)                    
                elif temp_state==Gst.State.PAUSED:
                    self.video_player.set_state(Gst.State.PLAYING)

    def restartCB(self,event=None):                    
        if (event.widget == self.root):
            if (f.currentType()=='VIDEO'):
                self.video_player.set_state(Gst.State.NULL)
                self.video_player.set_state(Gst.State.PLAYING)

    def nextCB(self,event=None):
        if (event.widget == self.root):
            self.filelist.next()
            self.updateDisplay()

    def prevCB(self,event=None):
        if (event.widget == self.root):
            self.filelist.prev()
            self.updateDisplay()

    def exitCB(self, event=None):
        if (event.widget == self.root):
            event.widget.withdraw()
            event.widget.quit()

    def saveDBCB(self,event=None):
        if (event.widget == self.root):
            self.db.save()

    def setRatingCB(self,event=None):
        if (event.widget == self.root):
            value=ratingvalue[event.char]
            if self.filelist.current() in self.db.photo_tbl.index:
                self.db.photo_tbl.at[self.filelist.current(),'rating']=value
            self.updateDisplay()

    def matchString(self):
        hits = []
        got = self.keywordText.get()
        for item in self.keywordDictionary:
            if item.startswith(got):
                hits.append(item)
        return hits    

    def showHit(self,lst):
        if len(lst) == 1:
            self.keywordText.set(lst[0])
            self.detect_pressed_filled = True

    def keywordEntryKeyreleaseCB(self,event):
        if len(event.keysym) == 1:
            hits = self.matchString()
            self.showHit(hits)

    def keywordEntryKeypressCB(self,event):    
        key = event.char
        if len(key) == 1 and self.detect_pressed_filled is True:
            pos = self.keywordEntry.index(tkinter.INSERT)
            self.keywordEntry.delete(pos, tkinter.END)

    def keywordEntryAcceptCB(self,event):
        keywords=re.findall(r'[!#@].+?(?=[!#@]|$)',''.join(self.keywordText.get().split()))
        print(keywords)
        for keyword in keywords:
            if keyword[0] != '!':
                keyword=keyword.lower()
            if len(self.db.photo_tbl.at[self.filelist.current(),'keywords'].strip()) > 0:
                curKeywords=self.db.photo_tbl.at[self.filelist.current(),'keywords'].strip().split()
                if keyword in curKeywords:
                    curKeywords.remove(keyword)
                else:
                    curKeywords.append(keyword)
                self.db.photo_tbl.at[self.filelist.current(),'keywords']=' '.join(curKeywords)
            else:
                self.db.photo_tbl.at[self.filelist.current(),'keywords']=keyword

            if keyword not in self.keywordDictionary:
                self.keywordDictionary.append(keyword)

    #    print(self.db.photo_tbl.at[f.current(),'keywords'])
        self.setKeywordOutput(self.db.photo_tbl.at[self.filelist.current(),'keywords'])
        self.hideKeywordEntry()


    def keywordEntryCancelCB(self,event):
        self.hideKeywordEntry()

class FileList:
    def __init__(self,recursive=False,first=None,input_filelist=None):
        if not input_filelist:
            self.filelist=sorted(glob.glob('*.*', recursive=recursive))
        else:
            self.filelist=sorted(input_filelist)

        self.count=len(self.filelist)
        self.filenum=0
        if first is not None:
            while first>self.filelist[self.filenum]:
                self.filenum=self.filenum+1
    def next(self):
        self.filenum=(self.filenum+1)%self.count
        return(self.filelist[self.filenum])        

    def prev(self):
        self.filenum=(self.filenum-1)%self.count
        return(self.filelist[self.filenum])        

    def current(self):
        return(self.filelist[self.filenum])

    def currentType(self):
        extension=os.path.splitext(self.current())[1].lower()
        if extension=='.jpg' or extension=='.png' or extension=='.bmp' or extension=='.heic':
            return('IMAGE')
        elif extension=='.mp4' or extension=='.mpg' or extension=='.avi' or extension=='.mov':
            return('VIDEO')
        else:
            return(None)


class PhotoDB:
    def __init__(self,dbFilename):
        self.gc=pygsheets.authorize(client_secret=SECRET_FILE, credentials_directory=SECRET_DIRECTORY)
        self.sheet=self.gc.open(dbFilename)

        try: 
            worksheet1=self.sheet.sheet1
        except:
            print('Error: sheet non found')
            sys.exit()

        self.photo_tbl=worksheet1.get_as_df()
        self.photo_tbl.set_index('filename',inplace=True)
        self.photo_tbl.index.name='filename'
        self.photo_tbl['rating']=pd.to_numeric(self.photo_tbl['rating'],errors='coerce').fillna(0).astype('int')
        self.initialKeywords=set()
        self.photo_tbl['keywords'].str.split().apply(self.initialKeywords.update)
        
    def save(self):
        worksheet=self.sheet.add_worksheet(datetime.now().strftime("%m/%d/%Y %H:%M:%S"),rows=10,cols=10,index=0)
        worksheet.clear()
        out_tbl=self.photo_tbl.reset_index()
        worksheet.set_dataframe(out_tbl,'A1',copy_index=False,extend=True)
        print('finished saving')
        oldsheet=self.sheet.worksheet('index',3)
        self.sheet.del_worksheet(oldsheet)

def main():
    Gst.init(None)

    parser=argparse.ArgumentParser(description='Display images/videos in a slideshow')
    parser.add_argument("-s", "--size",help='display size WxH',action="store",dest="size" )
    parser.add_argument("-r", "--recursive",help='recursively navigate directories',action="store_true",dest="recursive" )
    parser.add_argument("-f", "--first",help='first file to display',action="store",dest="first",default=None )
    parser.add_argument("-d", "--db",help='Enable GoogleSheets Database',action="store",dest="DB",default=None)
    parser.add_argument("files",help='(optional) list of files to display',action="store",nargs=argparse.REMAINDER )
    args=parser.parse_args()

    if args.DB:
        photoDB=PhotoDB(args.DB)
    else:
        photoDB=None

    root = tkinter.Tk()
    if args.size:
        root.geometry("%s+0+0" % args.size)
        root.resizable(False,False)
    else:
        root.attributes("-fullscreen",True)

    root.configure(background='black')
    root.update_idletasks()
    root.focus_set()
    f=FileList(recursive=args.recursive,first=args.first,input_filelist=args.files)

    if photoDB:
        infile_table=pd.Index(f.filelist)
        diff=infile_table.difference(photoDB.photo_tbl.index)
        if len(diff)>0:
            print('# files not in DB: '+str(len(diff)))
            for d in diff:
                print(d)

    App(root,f,photoDB)
    root.mainloop()

if __name__=="__main__":
    main()
