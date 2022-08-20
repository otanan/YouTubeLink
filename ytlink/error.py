#!/usr/bin/env python3
"""Handles messages for quota and other types of errors.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
import sys
import urllib.error
import googleapiclient.errors
#--- Custom imports ---#
from ytlink.tools.console import *
#======================== Helper ========================#


def _quota_exceeded(quit):
    """ Handles the "quota exceeded" message. """
    message = '[fail]Quota exceeded[/]'
    message += ', exiting...' if quit else '.'
    print(message)


def parse(error, url=None, quit=True):
    """ Parses the error to identify it as a quota error or some other issue.
        
        Args:
            error: the error to parse.
    
        Kwargs:
            url (str): the url request the lead to the error if applicable.

            quit (bool): whether to exit the program once the error has been parsed.
    
        Returns:
            (None): none
    
    """
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 403:
            # Quota exceeded error.
            _quota_exceeded(quit)
    elif isinstance(error, googleapiclient.errors.HttpError):
        if error.status_code == 403:
            # Quota exceeded error.
            _quota_exceeded(quit)
    else:
        # Unidentified error
        print(error)
        print(f'Error type: {type(error)}.')


    if url is not None:
        print(f'Error [emph]from[/] parsing search request: {url}.')

    if quit: sys.exit(-1)


#======================== Entry ========================#

def main():
    print('errors.py')
    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')