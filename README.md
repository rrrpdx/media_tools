# media_tools
Tools for manipulating/viewing images and videos

## show_media
show_media is a python script that allows you to view images and videos as well as add ratings and keywords that will be stored in a Google Sheets spreadsheet. 

### Usage:

```
show_media --size <size> --recursive --first <file> --db <db> {files}
    --size <size>: WxH -- If no size is given, app will display fullscreen
    --recursive: if no {files} are given, will recursively find/display all media in current (and sub)directories
    --first: Will start displaying with the given filenmame
    --db <db>: name of a Google Sheet to read rating/keyword data from.
    {files} optional list of files to display
```
### Examples:
#### Display all files in current directory
`show_media`
#### Display all JPGs in current directory
`show_media *.JPG`
#### Display all files in current directory in an 800x600 window
`show_media -s 800x600`
#### Display all files in current directory (and subdirectories) in an 800x600 window
`show_media -s 800x600 -r`
#### Display all files in current directory and sync rating/keywords to GoogleSheet named photodb
`show_media -s 800x600 -d photodb`

### Syncing with Google Sheets
This script allows you to store rating and keyword metadata in Google Sheets. You will need to create a credentials file as described here: https://pygsheets.readthedocs.io/en/stable/authorization.html. This file should be saved in `$HOME/.google/credentials.json`.

Currently, it is assumed that you have a Google Sheet already created that contains the following columns in Row 1:
`filename, hash, size, directory, rating, keywords`
The filenames should be unique as well as the hashes. Filenames, rating, and keywords are currently used. Other fields are for future use. If a file being displayed exists in the sheet, you will be able to modify its rating or keywords. Ratings can be from -1 to 10. They are displayed with half as many stars (so a rating of 10 is 5 stars, 5 is 2.5 stars, etc).

### Media Navigation
| Key | Action | 
|-----|--------|
| `Left Arrow` | View previous image/video | 
| `Right Arrow` | View next image/video |
| `t` | Toggle display of title |
| `p` | Toggle Play/Pause of video |
| `r` | Restart current video |
| `s`| Save state of database* |
| `0`-`9` | Rate image from 0-9* |
| `-` | Rate image -1* |
| `+` | Rate image/video 10* |
| `!@#` | Start entering keyword (keywords must begin with symbol)* |
| `Return` | While entering keyword, will accept and either add/remove keyword from list |
| `Escape` | While entering keyword, will cancel. Or will exit app |

 \* These keys are only active if the Google Sheets Database has been enabled at the commmand line
