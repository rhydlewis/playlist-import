#!/usr/bin/env python

"""playlist-import

Usage:
  playlist-import.py <import-file> <playlist-name>
  playlist-import.py -h | --help
"""

from docopt import docopt

import logging
import csv
import json
import os
import io
import re
from cursesmenu import *
from pyItunes import *
import itunes
from fuzzywuzzy import fuzz

# encoding=utf8
import sys
reload(sys)
sys.setdefaultencoding('utf8')


# create {artist: [{id, song, album}], }, fuzzy match artist then look for song and album combo,
# if not, get song. Pull ID from iTunes and use this to create script
# If no match remove suspect words remastered live etc ten re check

logging.basicConfig(format='%(asctime)s - %(filename)s[%(lineno)d] [%(levelname)s] %(message)s', level=logging.INFO)

TRACK = 'track'
ALBUM = 'album'
ARTIST = 'artist'
ID = 'id'
URL = 'url'
TRACK_ID = 'tid'
PERSISTENT_ID = 'pid'
EXACT_HIT = 'exact_hit'
PARTIAL_HIT = 'partial_hit'
TRACK_CONFIDENCE = 65
ARTIST_CONFIDENCE = 95
ALBUM_CONFIDENCE = 90
CONFUSING_WORDS = ["(Live)", "(Remastered)", "(Remaster)"]


class PlaylistImport:

    def __init__(self):
        self.opts = docopt(__doc__)
        self.library = load_itunes_lib("./iTunes Music Library.xml")
        self.missing_tracks = []
        playlist_tracks = self.get_playlist_tracks()
        chosen_tracks = self.search_itunes_for_tracks(playlist_tracks)
        playlist_name = self.opts['<playlist-name>']

        if self.missing_tracks:
            logging.info("Add these tracks to your iTunes library: ")

            for track in self.missing_tracks:
                logging.info(track)
                # results = search_for_itunes_track(track[TRACK], track[ARTIST], track[ALBUM])
                # logging.info(results)

        if chosen_tracks > 0:
            script = generate_applescript(chosen_tracks)

            print "\n----\n"
            print script

        # logging.info("Writing to iTunes playlist: {0}".format(playlist_name))

    def get_playlist_tracks(self):
        import_file = self.opts['<import-file>']
        # import_file = "./small.csv"
        logging.debug("Reading import file: {0}".format(import_file))
        tracks = []
        with open(import_file, 'rb') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if len(row) > 0:
                    entry = {ARTIST: row[2], ALBUM: row[3], TRACK: row[1]}
                    tracks.append(entry)
                    # logging.debug(entry)

        return tracks

    def search_itunes_for_tracks(self, playlist):
        chosen_tracks = []

        for entry in playlist:
            track = entry[TRACK]
            artist = entry[ARTIST]

            itunes_track = self.find_corresponding_track(entry)

            if not itunes_track:
                logging.warn("No results found for '{0}' by '{1}'".format(track, artist))
                self.missing_tracks.append(entry)
                continue

            logging.info("Found track: '{0}'".format(itunes_track))
            chosen_tracks.append(itunes_track)
        return chosen_tracks

    def find_corresponding_track(self, entry):
        artist_name = entry[ARTIST]
        track_name = entry[TRACK]

        artist_album = self.find_artist(artist_name)

        hit = None

        if artist_album:
            album_name = entry[ALBUM]

            results = find_song_in_album(artist_album, track_name, album_name)
            exact_hits = results[EXACT_HIT]
            partial_hits = results[PARTIAL_HIT]

            if exact_hits:
                if len(exact_hits) is 1:
                    logging.info("Adding exact hit '{0}' in '{1}'".format(track_name, album_name))
                    hit = exact_hits.pop()
                else:
                    hit = choose_track(exact_hits, artist_name, track_name)
                    logging.info(
                        "Adding user's choice '{0}' in '{1}' instead of '{2}' in '{3}' from list of {4} exact hits".
                        format(hit[TRACK], hit[ALBUM], track_name, album_name, len(exact_hits)))
            elif partial_hits:
                hit = choose_track(partial_hits, artist_name, track_name)
                logging.info(
                    "Adding user's choice '{0}' in '{1}' instead of '{2}' in '{3}' from list of {4} partial hits".
                    format(hit[TRACK], hit[ALBUM], track_name, album_name, len(partial_hits)))

            if hit is None:
                logging.info("User did not choose a song for '{0}' by '{1}'".format(track_name, artist_name))
        # else:
        #     logging.warn("NOT FOUND: '{0}' by '{1}'".format(track_name, artist_name))

        return hit

    def find_artist(self, artist_name):
        hit = None
        if artist_name in self.library:
            logging.debug("Found exact hit for artist '{0}' in iTunes library".format(artist_name))
            hit = self.library[artist_name]
        else:
            for artist in self.library.keys():
                fuzz_result = fuzz.ratio(artist, artist_name)
                if fuzz_result > ARTIST_CONFIDENCE:
                    logging.debug("Found partial hit for artist {0} based on score {1} (instead of {2})".format(
                        artist, fuzz_result, artist_name))
                    hit = self.library[artist]

        return hit


def generate_applescript(tracks):
    applescript = "set new_playlist to {"
    for track in tracks:
        applescript += "{{track_name:\"{0}\", ".format(track[TRACK])
        applescript += "p_id:\"{0}\"}}".format(track[PERSISTENT_ID])
        applescript += ", "

    applescript = applescript.rstrip(", ")
    applescript += "}"

    return applescript


def clean_up_title(title):
    for word in CONFUSING_WORDS:
        if word.lower() in title.lower():
            old_name = title
            title = re.sub("(?i)" + word, "", title)
            logging.error("Removed confusing word {0} from name {1} = {2}".format(word, old_name, title))

    return title.strip().lower()


def find_song_in_album(artist_album, title, album_name):
    logging.debug("Searching for '{0}' in '{1}'".format(title, album_name))
    exact_hits = []
    partial_hits = []

    title = clean_up_title(title)

    for artist_track in artist_album:
        track_match = fuzz.partial_ratio(title, artist_track[TRACK])
        album_match = fuzz.ratio(album_name, artist_track[ALBUM])

        if track_match >= TRACK_CONFIDENCE and album_match >= ALBUM_CONFIDENCE:
            logging.info(u"Found exact hit for track '{0}' in '{1}' ({2} & {3})".
                         format(artist_track[TRACK], artist_track[ALBUM], track_match, album_match))
            exact_hits.append(artist_track)
        elif track_match >= TRACK_CONFIDENCE and album_match < ALBUM_CONFIDENCE:
            logging.debug(u"Found partial hit for track using '{0}' in '{1}' ({2} & {3})".
                          format(artist_track[TRACK], artist_track[ALBUM], track_match, album_match))
            partial_hits.append(artist_track)
        else:
            logging.debug(u"No match for track '{0}' in '{1}' ({2} & {3})".
                          format(artist_track[TRACK], artist_track[ALBUM], track_match, album_match))

    return {EXACT_HIT: exact_hits, PARTIAL_HIT: partial_hits}

    # def find_song_ignoring_album(self, artist, track_name):
    #     logging.debug("Widening search for '{0}' to all albums".format(track_name))
    # else:
    #
    #     for lib_track in lib:
    #         track_match = fuzz.ratio(track, lib_track[TRACK])
    #         artist_match = fuzz.ratio(artist, lib_track[ARTIST])
    #         if track_match > confidence and artist_match > confidence:
    #             track_exists = True
    #             break

    # if not track_exists and e_album:
    #     logging.debug("Didn't find exact match, searching for any '{0}' by '{1}' instead".format(track, artist))
    #     track_exists = find_corresponding_track(lib, track, artist)


def search_for_itunes_track(track, artist, album=None):
    if album:
        logging.debug("Searching for '{0}' by '{1}' in '{2}'".format(track, artist, album))
        results = itunes.search("{0} {1} {2}".format(artist, album, track), "music")
    else:
        logging.debug("Searching for '{0}' by '{1}'".format(track, artist))
        results = itunes.search("{0} {1}".format(artist, track), "music")

    return results


def choose_track(hits, artist_name, track_name):
    options = []
    for hit in hits:
        options.append("'{0}' in '{1}' / ({2})".format(hit[TRACK], hit[ALBUM], hit[TRACK_ID]))

    menu = SelectionMenu(options, "Select version of {0} by {1} for playlist".format(track_name, artist_name))
    menu.show()
    menu.join()

    selection = None
    if menu.selected_option is not menu.exit_item:
        selection = hits[menu.selected_option]

    return selection


def load_itunes_lib(filepath):
    save_file = './itunes.json'
    if not os.path.exists(save_file):
        logging.info("Parsing iTunes library at '{0}'".format(filepath))
        l = Library(filepath)
        logging.info("Finished parsing iTunes library".format(filepath))
        lib = {}
        for _id, song in l.songs.items():
            artist = song.artist
            track = song.name
            album = song.album
            persistent_id = song.persistent_id
            track_id = song.track_id

            if artist not in lib:
                lib[artist] = []

            lib[artist].append({ALBUM: album, TRACK: track, TRACK_ID: track_id, PERSISTENT_ID: persistent_id})

        with io.open(save_file, 'w', encoding='utf-8') as f:
            f.write(unicode(json.dumps(lib, ensure_ascii=False)))
    else:
        with open(save_file) as json_data:
            lib = json.load(json_data)

    return lib


if __name__ == '__main__':
    app = PlaylistImport()



