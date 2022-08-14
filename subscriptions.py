#!/usr/bin/env python3
"""Updates Watch Later playlist with new videos from subscriptions.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
import os
# Command line arguments
import sys
import urllib.error
import commentjson as json
from datetime import datetime, timedelta
from pathlib import Path
import time
#--- Custom imports ---#
from ytlink.tools.console import *
import ytlink
#======================== Fields ========================#
# Flag for testing run
_TESTING_ARG = '--testing'
# Location of last run file
_LAST_RUN_FNAME = Path(__file__).parent / 'last_run.txt'
#======================== Helper ========================#


def load_settings():
    """ Loads user settings with information such as the last run and filters. """
    with open(Path(__file__).parent / 'settings.json', 'r') as f:
        return json.load(f)


def update_last_run():
    with open(_LAST_RUN_FNAME, 'w') as f:
        f.write(str(datetime.now()))


def load_last_run():
    """ Gets the time the script was last run. """
    with open(_LAST_RUN_FNAME, 'r') as f:
        last_run = f.read()

    return datetime.strptime(last_run, '%Y-%m-%d %H:%M:%S.%f')


def filter_video(filters, video):
    """ Compares the video's information based off of filters provided for the given channel and returns the filter if that was triggered or None if the video should not be filtered. """
    channel = video.channel
    if channel.name not in filters: return None

    # Lower case for case insensitive comparison
    lower_name = video.name.lower()
    lower_desc = video.description.lower() if video.description is not None else ''

    for filt in filters[channel.name]:
        lower_filt = filt.lower()
        if lower_filt in lower_name or lower_filt in lower_desc: return filt

    return None


#======================== Entry ========================#


def main():
    settings = load_settings()
    # Playlist ID for watch later playlist
    watch_later_playlist = ytlink.Playlist(
        'Auto Watch Later', settings['watch_laterID']
    )

    # True if in testing mode
    _TESTING_FLAG = _TESTING_ARG in sys.argv

    #--- Get the last successful run of the script ---#
    if _TESTING_FLAG:
        console.rule('[emph]Testing mode...')
        # Act like the last run was 5 days ago
        last_run = datetime.now() - timedelta(days=5)
    else:
        # Get the actual last run
        last_run = load_last_run()

    print( f'Last run: {last_run}\n' )

    youtube = ytlink.init_youtube()
    subscriptions = ytlink.get_subscriptions(youtube)

    # If testing, only check 5 subscriptions to limit hits
    if _TESTING_FLAG: subscriptions = subscriptions[:8]

    #------------- Get newest videos -------------#
    # Multiply the number of days passed by the multiplier to 
        # mitigate number of videos requested
    multiplier = settings['last_run_multiplier']
    last_run_days = (datetime.now() - last_run).days
    # Add one to handle running the script in the same day
    max_vids = (last_run_days + 1) * multiplier

    videos = []
    with Progress('Pulling from subscriptions') as progress:
        for channel in progress.track(subscriptions):

            #--- Attempt to pull videos, handle quota error ---#
            try:
                videos += channel.uploads(after_date=last_run)
            except urllib.error.HTTPError as e:
                # Remove the progress bar
                progress.stop()
                
                if e.code == 403:
                    print('[warning]Quota exceeded, exiting...')
                else:
                    print(f'[warning]Unhandled HTTPError: {e.code}, exiting...')
                    print(e.msg)
                
                sys.exit(-1)

    # Sort videos by date
    videos = sorted(videos, key=lambda video: video.date)

    #------------- Add videos to playlist -------------#
    video_counter = 0
    print('Loading filters...')
    filters = settings['filters']

    with Progress('Adding videos') as progress:
        for video in progress.track(videos):

            # Check whether the video should be skipped according to user filters
            if ( filt := filter_video(filters, video) ) is not None:
                progress.print(
                    f'Skipping [warning]{video.link}[/] from {video.channel.link} '
                    f'to Watch Later playlist; filter: [warning]{filt}[/] '
                    f'published on {video.date}...'
                )
                continue

            progress.print(
                f'Adding [emph]{video.link}[/] from {video.channel.link} to '
                f'Watch Later playlist; published on {video.date}...'
            )
        
            # Skip on testing
            if not _TESTING_FLAG:
                ytlink.add_video_to_playlist(
                    youtube, watch_later_playlist, video
                )
            else:
                # Simulate adding to playlist delay by sleeping
                time.sleep(0.8)

            video_counter += 1


    if video_counter > 0:
        print(f'Updated playlist with {video_counter} videos successfully.')
    else:
        print('No new videos.')

        
    # On success, save the last run
    if not _TESTING_FLAG: update_last_run()

    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('\nKeyboard interrupt.')