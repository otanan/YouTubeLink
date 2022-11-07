#!/usr/bin/env python3
"""Get all videos made by a channel to add them to a channel-specific watch later playlist.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
import sys
from pathlib import Path
import rich.prompt
#--- Google necessary imports ---#
import os
import json
#--- Custom imports ---#
from ytlink.tools.console import *
import ytlink.tools.typing_filter
import ytlink
import ytlink.error
#======================== Fields ========================#
_CHANNELS_DATA_FOLDER = Path(__file__).parent / 'channels_data'
_CHANNELS_FILE = _CHANNELS_DATA_FOLDER / 'channels.json'


#======================== Helper ========================#


def user_confirm(question):
    """ Asks the user to confirm a question through input. """
    return rich.prompt.Confirm.ask(question, default=True)


def _parse_channels_from_results(results):
    """ Parses channels from a search of channels. """
    channels = {}

    for item in results:
        item = item['snippet']

        channels[name] = ytlink.Channel(
            name=item['title'], ID=item['channelId']
        )
    return channels


def _channel_search_request(search):
    """ Takes the user's search keyphrase, searches for channels, parses results, proposes new channels, and takes user confirmation to save to file. """
    # Keyphrase search has been shown to be more accurate than Channels list
        # for this purpose
    results = ytlink.keyphrase_search(search, kind='channel')
    
    search_channels = _parse_channels_from_results(results)
    lower_search = search.lower()
    for channel_name in search_channels:
        if lower_search != channel_name.lower():
            # Names don't match
            continue

        # Names match (case insensitive)
        channel = search_channels[channel_name]
        print(f'Found channel: {channel.link}.')

        if user_confirm('Is this the correct channel?'):
            # Found the correct channel
            return channel

    #--- No matching results, alternative approach ---#
    # Reattempt search by requesting a video ULR
    print('No matching results, taking an alternative approach...')
    video_url = input('Provide a link to a video from the channel: ')
    channel = ytlink.Channel.from_video_url(video_url)
    print(f'Found channel: {channel.link}.')

    if user_confirm('Is this the correct channel?'):
        # Found the correct channel
        return channel

    print('Could not find channel.')
    sys.exit(-1)


def videos_fname(channel):
    """ Gets the filename to the videos file corresponding to a given channel. """
    return Path(__file__).parent / f'channels_data/{channel.name}.txt'


def file_is_empty(path):
    """ Checks whether the path to a given file is empty. """
    return path.stat().st_size == 0


#======================== Reading ========================#


def load_channels():
    """ Loads the channels.json file with saved channels objects. Including their playlist information and IDs. """
    if file_is_empty(_CHANNELS_FILE):
        return {}

    with open(_CHANNELS_FILE, 'r') as f: channels_dict = json.load(f)

    channels = {}
    for name, channel_dict in channels_dict.items():
        # Convert the channel into a ytlink.Channel object
        channel = ytlink.Channel(
            name=name,
            ID=channel_dict['ID'],
            playlists=channel_dict['playlists']
        )
        channels[name] = channel

    return channels


def load_videos_from_channel(channel):
    """ Loads a file containing the list of all videos published by a particular channel if it exists. Generates one if it doesn't. Updates legacy video IDs files to up to date video files.
        
        Args:
            channel (ytlink.Channel): the channel's video files to be loaded.    
    
        Returns:
            (list): list of ytlink.Video's
    
    """
    fname = videos_fname(channel)

    if fname.exists():
        if file_is_empty(fname): return []

        # Video files already exist, read it
        with open(fname, 'r') as f: lines = f.read().splitlines()

        # Test whether the first line is a video JSON line or is a legacy line
            # as simply a video ID
        is_JSON = True
        try:
            json.loads(lines[0])
        except json.JSONDecodeError as e:
            # The lines are not JSON, must load them simply as video IDs
            is_JSON = False

        if is_JSON:
            return [
                ytlink.Video(**json.loads(videojson))
                for videojson in lines
            ]

        #--- Update legacy file ---#
        # Convert the video IDs to videos
        with rstatus('Updating legacy video IDs file...'):
            videos = [ ytlink.Video.from_ID(videoID) for videoID in lines ]


        update_videos_file(channel, videos)
        return videos
        
    #--- File doesn't exist ---#
    print(f'Videos file for {channel.link} does not exist.')

    with rstatus('Generating videos file...'):
        videos = channel.uploads(max_vids=None, chronological=True)

        # Save the videos to a file
        update_videos_file(channel, videos)

    # rstatus line is lost so replace the entire line
    print('Generating videos file... done.')
    return videos


#======================== Writing ========================#


def update_channels(channels):
    # Convert to a dictionary of channels
    channelsdict = {
        channel.name: channel.dict()
        for channel in channels.values()
    }

    with open(_CHANNELS_FILE, 'w') as f:
        json.dump(channelsdict, f, indent=4)
    # print(f'{_CHANNELS_FILE.name} file updated.')
    print('Channels updated.')


def update_videos_file(channel, videos):
    """ Update the videos file for a given channel. """
    with open(videos_fname(channel), 'w') as f:
        # Convert the video objects to their JSON formatting
        f.write('\n'.join( [video.json() for video in videos] ))


#======================== Entry ========================#

def main():
    # True if in testing mode
    _NO_ADD_FLAG = '--no-add' in sys.argv

    # Initialize YouTube object variable for usage later
    youtube = None
    channels = load_channels()

    #------------- Channel information -------------#
    # channel_name = input('Channel name: ')
    channel_name = ytlink.tools.typing_filter.launch(
        options=list(channels),
        header='Press Escape to perform a search. Press Ctrl + C to quit...'
    )

    if channel_name is None:
        channel_name = input('Search online for channel: ').strip()

        if channel_name == '':
            print('[fail]Search canceled.')
            # No search requested, exit.
            sys.exit()

        # Found the channel
        channel = _channel_search_request(channel_name)
        channels[channel.name] = channel
        # Save the results to file
        update_channels(channels)
    else:    
        channel = channels[channel_name]


    #------------- Get videos -------------#

    # Get the videos associated to the channel
    videos = load_videos_from_channel(channel)

    if not videos:
        # The videos file exists but is empty, this channel must be complete.
        print(f'All [emph]{channel.name}[/] videos have already been added.')
        sys.exit()


    if _NO_ADD_FLAG:
        # Don't add videos. End the script here.
        return

    #------------- Playlist information -------------#
    if 'watch_later' not in channel.playlists:
        # No playlist made for this channel.
        if not user_confirm(
            'No playlist found for channel. '
            'Make a new playlist?'
        ):
            # User does not want to make a new playlist
            sys.exit()

        # Make a new playlist
        youtube = ytlink.init_youtube()
        playlist_name = f'Watch: {channel.name}'
        playlist = ytlink.create_playlist(youtube, playlist_name)
        print(f'New playlist: {playlist.url}.')

        # Update the channels
        channel.playlists['watch_later'] = playlist
        update_channels(channels)
    else:
        # Playlist already exists
        playlist = channel.playlists['watch_later']


    #------------- Add videos to playlist -------------#

    if not youtube:
        # YouTube object has not been initialized
        youtube = ytlink.init_youtube()

    # Go through each video with rich progress bar
    counter = 0
    with Progress() as progress:
        for _ in progress.track(range(len(videos))):
            video = videos.pop(0)
            progress.print(f'Adding video: [emph]{video.link}[/].')

            try:
                ytlink.add_video_to_playlist(youtube, playlist, video)
                counter += 1
                # Update the videos file since it was successful
                update_videos_file(channel, videos)
                
            except Exception as e:
                progress.stop()
                ytlink.error.parse(e, quit=False)
                print() # Padding
                break

    # Update the videos file
    print(f'{counter} videos added to playlist.')



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('\nKeyboard interrupt.')