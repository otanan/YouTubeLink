#!/usr/bin/env python3
"""Provides functionality for gathering data from YouTube and writing data.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
import sys
import json
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
#--- Google necessary imports ---#
import os
import google_auth_oauthlib.flow, googleapiclient.discovery
import urllib.request
#--- Custom imports ---#
from ytlink.tools.console import *
import ytlink.error
#======================== Fields ========================#


def init_youtube():
    print('Initializing YouTube object...')
    # Make a new screen for providing the authentication credentials
    with console.screen():
        # Disable OAuthlib's HTTPS verification when running locally.
        # *DO NOT* leave this option enabled in production.
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

        client_secrets_fname = Path(__file__).parent / 'config/client_secrets.json'
        # Get credentials and create an API client
        app_flow = google_auth_oauthlib.flow.InstalledAppFlow
        credentials = app_flow.from_client_secrets_file(
            client_secrets_fname,
            'https://www.googleapis.com/auth/youtube'
        ).run_console()
        youtube = googleapiclient.discovery.build(
            'youtube', 'v3', credentials=credentials
        )

    print('Successfully initialized YouTube object.\n')
    return youtube


#======================== Objects ========================#


class YTObj(ABC):
    """ Abstract YouTube Object class that all other objects inherit from.
        
        Attributes:
            name: the name of the video/playlist/channel
            ID: the name of the video/playlist/channel
    """
    def __init__(self, name, ID):
        self.name = name
        self.ID = ID

        # Get the rich markup for a hyperlink to this object's url.
        self.link = f'[link={self.url}]{self.name}[/]'

    def dict(self):
        """ Converts self to dict for saving as JSON. """
        return { 'name': self.name, 'ID': self.ID }

    @property
    @abstractmethod
    def url(self): pass

    @staticmethod
    @abstractmethod
    def from_ID(ID):
        """ Generates the YTObj from the ID alone. """
        pass


class Video(YTObj):
    def __init__(self, name, ID, date, channelID, description=None):
        super().__init__(name, ID)
        if 'T' in date:
            # Use the YouTube formatting parser
            self.date = datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ')
        else:
            # Use the datetime formatting parser
            self.date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')

        self._channelID = channelID
        self.description = description

    @property
    def url(self):
        return f'https://www.youtube.com/watch?v={self.ID}'

    def dict(self):
        """ Converts self to dict for saving. """
        return {
            'name': self.name, 'ID': self.ID,
            'date': str(self.date), 'description': self.description,
            'channelID': self._channelID
        }

    def json(self):
        """ Converts self to JSON for saving. """
        return json.dumps(self.dict())

    @staticmethod
    def ID_from_url(url):
        return url.split('watch?v=')[-1]

    @staticmethod
    def from_ID(ID):
        info = search('videos', part='snippet', id=ID)['items'][0]['snippet']
        return Video(
            name=info['title'], ID=ID,
            date=info['publishedAt'], description=info['description'],
            channelID=info['channelId']
        )

    @property
    def channel(self):
        """ Gets the channel that uploaded this video. """
        try:
            # See if the attribute exists
            return self._channel
        except AttributeError:
            # The channel hasn't been loaded yet
            self._channel = Channel.from_ID(self._channelID)

        return self.channel


class Playlist(YTObj):
    def __init__(self, name, ID):
        super().__init__(name, ID)

    @property
    def url(self): return f'https://www.youtube.com/playlist?list={self.ID}'

    @staticmethod
    def from_ID(ID):
        results = search(api='playlists', part='snippet', id=ID)['items'][0]
        name = results['snippet']['title']
        return Playlist(name=name, ID=ID)

    @property
    def channel(self):
        """ Gets the channel that created this playlist. """
        try:
            # See if the attribute exists
            return self._channel
        except AttributeError:
            # The channel hasn't been loaded yet
            snippet = search(
                api='playlists', part='snippet', id=self.ID
            )['items'][0]['snippet']
            name = snippet['channelTitle']
            channelID = snippet['channelId']
            playlists = {self.name: self}
            self._channel = Channel(
                name=name, ID=channelID, playlists=playlists
            )

        return self.channel

    def videos(self, max_vids=10, after_date=None, chronological=False):
        """ Gets the playlist's uploaded videos.
        
            Kwargs:
                max_vids (int/None): the maximum number of videos to get. None if there should be no maximum (9999).

                after_date (datetime.datetime): only get the videos after the given date. Ignores the max_vids parameter.

                chronological (bool): whether to return the videos in chronological order or not.
        
            Returns:
                (list): list of ytlink.Video's.
        
        """
        # Ignore max_vids if None is provided or an after_date is provided.
        if max_vids is None or after_date is not None: max_vids = 9999
        
        # Don't search for more than 50 results at a time
        max_results = max_vids if max_vids <= 50 else 50

        # To be updated with next_page_token
        search_keys = {
            'api': 'playlistItems',
            'part': 'snippet',
            'playlistId': self.ID,
            'order': 'date',
            'maxResults': max_results
        }

        videos = []
        # Flag to continue searching through videos
        cont_search_flag = True
        while cont_search_flag:
            # The response will get videos newest first
            response = search(**search_keys)

            # Run through the page of responses
            for video_data in response['items']:
                video_data = video_data['snippet']

                if video_data['resourceId']['kind'] != 'youtube#video':
                    # This is not a YouTube video
                    continue

                video = Video(
                    name=video_data['title'],
                    ID=video_data['resourceId']['videoId'],
                    date=video_data['publishedAt'],
                    channelID=video_data['channelId'],
                    description=video_data['description'],
                )
                # Save time on the channel computation
                video._channel = self.channel

                if after_date is not None and video.date < after_date:
                    # This video is too old now, break out.
                    cont_search_flag = False
                    break

                videos.append(video)

                if len(videos) >= max_vids:
                    # We have enough videos, break out
                    cont_search_flag = False


            if 'nextPageToken' in response:
                search_keys['pageToken'] = response['nextPageToken']
            else:
                # There are no more pages of videos to parse, break out
                cont_search_flag = False
            

        # List of videos will be in reverse chronological order
        # Reverse it to put it into chronological order
        return videos[::-1] if chronological else videos


class Channel(YTObj):
    def __init__(self, name, ID, playlists=None):
        super().__init__(name, ID)

        if playlists is None:
            self.playlists = {}
        else:
            self.playlists = {
                playlist_name: Playlist(playlist_name, playlistID)
                for playlist_name, playlistID in playlists.items()
            }

    @property
    def url(self): return f'https://www.youtube.com/channel/{self.ID}'

    @staticmethod
    def from_ID(ID):
        response = search(api='channels', part='snippet', id=channelID, maxResults=1)
        info = response['items'][0]['snippet']
        return Channel(name=info['title'], ID=ID)

    @staticmethod
    def ID_from_videoID(videoID):
        """ Gets the channel ID from the channel that posted a given video. """
        response = search(api='videos', part='snippet', id=videoID)
        return response['items'][0]['snippet']['channelId']

    @staticmethod
    def from_videoID(ID):
        """ Generates Channel information from video ID. """
        return Channel.from_ID(Channel.ID_from_videoID(videoID))

    @staticmethod
    def from_video_url(url):
        """ Generates Channel information from video URL. """
        return Channel.from_videoID(Video.ID_from_url(url))

    @property
    def uploads_playlist(self):
        """ Gets the uploads playlist for this channel if not stored. Saves it otherwise. """
        if 'uploads' not in self.playlists:
            # Uploads has never been found before
            uploadsID = search(
                api='channels', part='contentDetails',
                id=self.ID, maxResults=1
            )['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            self.playlists['uploads'] = Playlist('Uploads', uploadsID)

        return self.playlists['uploads']

    def dict(self):
        """ Converts self to JSON for saving. """
        # Convert dictionary of playlists into a dictionary of JSON
        playlists_JSON = {
            playlist.name: playlist.ID 
            for playlist in self.playlists.values()
        }

        return {
            'name': self.name,
            'ID': self.ID,
            'playlists': playlists_JSON
        }

    def uploads(self, max_vids=10, after_date=None, chronological=False):
        """ Gets the channel's uploaded videos.
        
            Kwargs:
                max_vids (int/None): the maximum number of videos to get. None if there should be no maximum (9999).

                after_date (datetime.datetime): only get the videos after the given date. Ignores the max_vids parameter.

                chronological (bool): whether to return the videos in chronological order or not.
        
            Returns:
                (list): list of ytlink.Video's.
        
        """
        return self.uploads_playlist.videos(max_vids=max_vids, after_date=after_date, chronological=chronological)


#======================== Helper ========================#


def api_key():
    """ Load the API key once. Save it for future usage once loaded. """
    # Load the key for the first time
    with open(Path(__file__).parent / 'config/api_key.txt', 'r') as f:
        key = f.read()

    global api_key
    # Overwrite this loading function with a simple return of the key
    api_key = lambda : key
    # Actually provide the key for this first run
    return key


#======================== Reading ========================#


def search(api, **kwargs):
    """ General search function for formatting keywords and requesting results from Google API.
        
        Args:
            api (str): the Google API to use.
    
        Kwargs:
            **kwargs: additional search parameters.
    
        Returns:
            (None): none
    
    """
    # Replace spaces in search phrase if applicable
    if 'q' in kwargs: kwargs['q'] = kwargs['q'].replace(' ', '%20')

    # Base API URL for making HTTP requests
    url = 'https://www.googleapis.com/youtube/v3'
    url = f'{url}/{api}?key={api_key()}' + ''.join([
        f'&{key}={value}'
        for key, value in kwargs.items()
    ])

    try:
        response = urllib.request.urlopen(url)
    except urllib.error.HTTPError as e:
        ytlink.error.parse(e, url=url)

    return json.load(response)


def keyphrase_search(keyphrase, kind=None):
    """ Performs a search and filters results based on the kind provided.    
    
        Returns:
            (list): unformatted list of dictionary results
    
    """
    items = search(api='search', part='snippet', q=keyphrase)['items']

    if not kind:
        # No filter, just return all results
        return items

    # Filter out results
    results = []
    kind = f'youtube#{kind}'
    for item in items:
        if item['id']['kind'] == kind:
            results.append(item)

    return results


#------------- User reading -------------#

def get_subscriptions(youtube):
    """ Constructs a dictionary of subscriptions related to the user linked to the YouTube object. """
    subscriptions = []

    #--- Get the first page of subscriptions ---#
    kwargs = { 'part': 'snippet,contentDetails', 'mine': True }

    while True:
        response = youtube.subscriptions().list(**kwargs).execute()

        # Save the subscription information
        for sub in response['items']:
            snippet = sub['snippet']
            subscriptions.append(Channel(
                name=snippet['title'],
                ID=snippet['resourceId']['channelId']
            ))

        # There is no other page of subscriptions
        if 'nextPageToken' not in response: break

        # Pull next page of subscriptions
        kwargs['pageToken'] = response['nextPageToken']
    
    return subscriptions


#======================== YouTube Writing ========================#


def create_playlist(youtube, name, description=''):
    """ Creates a new playlist and returns the playlist ID. """
    response = youtube.playlists().insert(
        part='snippet,status',
        body={
            'snippet': {
                'title': name,
                'description': description,
            },
            'status': {
                'privacyStatus': 'private',
            }
        }
    ).execute()

    return Playlist(name, response['id'])


def add_video_to_playlist(youtube, playlist, video):
    youtube.playlistItems().insert(
        part='snippet',
        body={
            'snippet': {
                'playlistId': playlist.ID, 
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': video.ID
                }
            }
        }
    ).execute()


#======================== Entry ========================#

def main():
    print('ytlink.py')
    
    # print(search(api='search', part='snippet', q='Rushfaster'))
    
    # Get Max Tech videos
    # print(search(api='playlistItems', part='snippet', playlistId='UUptwuAv0XQHo1OQUSaO6NHw', order='date', maxResults=10))

    # print(search(api='playlists', part='snippet', id='PLraFbwCoisJC1o7RyhE38wetdQTBy_gF_'))
    
    # video = Video('An Actual Review of Elden Ring', 'HFNt9qrISd4')
    # video = Video.from_ID('HFNt9qrISd4')
    # print( f'video: {video.name}' )
    
    

if __name__ == '__main__':
    main()