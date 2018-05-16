import csv
import musicbrainzngs
import json

albums = {}
musicbrainzngs.set_useragent("Example music app", "0.1", "http://example.com/music")

out = open("./years.log", "a", 0)

with open("./lastfm.csv", 'rb') as f:
    reader = csv.reader(f, delimiter=',')
    for row in reader:
        artist = row[0]
        album = row[1]
        key = artist + " - " + album

        if not albums.has_key(key):
            artist_results = musicbrainzngs.search_artists(strict=True, artist=artist)
            year = 2020
            for artist_result in artist_results['artist-list']:

                found_name = artist_result['name']
                if found_name.lower() == artist.lower():
                    _id = artist_result['id']
                    results = musicbrainzngs.search_recordings(strict=True, arid=_id, release=album)

                    if results.has_key('recording-list'):
                        rec_list = results['recording-list']
                        for recording in rec_list:
                            if recording.has_key('release-list'):
                                for release in recording['release-list']:
                                    if release.has_key('date') and release.has_key('title'):
                                        title = release['title']
                                        date = release['date']
                                        if title.lower() == album.lower():
                                            release_year = int(date[0:4])
                                            if release_year < year:
                                                # print "Changing year from {0} to {1}".format(year, release_year)
                                                # print release
                                                year = release_year

                # print "Year for {0} is {1}".format(found_name, year)

            albums[key] = year
            out.write("{0}\t{1}\t{2}\n".format(artist, album, year))

out.close()



